#!/usr/bin/env python3
"""
Sampled output regression compare: legacy (binary/ASCII) vs NetCDF.

The NetCDF output contract is still evolving (Phase B). This tool focuses on:
- parsing SHUD legacy binary output (*.dat) deterministically
- comparing sampled (time, index) points against NetCDF variables
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import struct
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _parse_int_list(s: str) -> List[int]:
    out: List[int] = []
    for part in (p.strip() for p in s.split(",")):
        if not part:
            continue
        out.append(int(part))
    return out


def _parse_float_list(s: str) -> List[float]:
    out: List[float] = []
    for part in (p.strip() for p in s.split(",")):
        if not part:
            continue
        out.append(float(part))
    return out


def _require_netCDF4() -> Any:
    try:
        import netCDF4  # type: ignore

        return netCDF4
    except Exception as e:
        raise RuntimeError(
            "Python package 'netCDF4' is required for NetCDF output comparison.\n"
            "Install:\n"
            "  python3 -m pip install netCDF4 numpy\n"
        ) from e


@dataclasses.dataclass
class LegacyBin:
    start_time: float
    num_var: int
    icol_1based: List[int]
    times_min: List[float]
    values: List[List[float]]  # rows: [num_var]


def _read_legacy_bin(path: str) -> LegacyBin:
    with open(path, "rb") as f:
        header = f.read(1024)
        if len(header) != 1024:
            raise ValueError(f"Invalid legacy bin header size: {path}")

        start_time = struct.unpack("d", f.read(8))[0]
        num_var = int(struct.unpack("d", f.read(8))[0])
        icol = list(struct.unpack(f"{num_var}d", f.read(8 * num_var)))
        icol_1based = [int(round(x)) for x in icol]

        times: List[float] = []
        rows: List[List[float]] = []
        rec_size = 8 * (1 + num_var)
        while True:
            blob = f.read(rec_size)
            if not blob:
                break
            if len(blob) != rec_size:
                raise ValueError(f"Truncated legacy bin record: {path}")
            t = struct.unpack_from("d", blob, 0)[0]
            vals = list(struct.unpack_from(f"{num_var}d", blob, 8))
            times.append(float(t))
            rows.append([float(x) for x in vals])

    return LegacyBin(
        start_time=float(start_time),
        num_var=num_var,
        icol_1based=icol_1based,
        times_min=times,
        values=rows,
    )


def _find_time_index(times: Sequence[float], t_min: float, tol: float) -> int:
    best = -1
    best_err = float("inf")
    for i, t in enumerate(times):
        err = abs(float(t) - float(t_min))
        if err < best_err:
            best = i
            best_err = err
    if best < 0 or best_err > tol:
        raise ValueError(f"time not found within tol={tol}: t_min={t_min}, best_err={best_err}")
    return best


def _read_netcdf_value(nc_path: str, var_name: str, time_idx: int, obj_idx0: int, time_dim: str, obj_dim: str) -> float:
    netCDF4 = _require_netCDF4()
    with netCDF4.Dataset(nc_path, "r") as ds:
        if var_name not in ds.variables:
            raise ValueError(f"var not found in NetCDF: {nc_path}: {var_name}")
        var = ds.variables[var_name]
        dims = list(var.dimensions)
        if time_dim not in dims or obj_dim not in dims:
            raise ValueError(f"var dims do not include {time_dim}/{obj_dim}: {var_name} dims={dims}")
        index: List[int] = []
        for d in dims:
            if d == time_dim:
                index.append(int(time_idx))
            elif d == obj_dim:
                index.append(int(obj_idx0))
            else:
                index.append(0)
        v = var[tuple(index)]
        try:
            import numpy as np  # type: ignore

            if isinstance(v, np.ma.MaskedArray):
                if bool(np.ma.is_masked(v)):
                    raise ValueError(f"masked value for var={var_name} at idx={index}")
                v = v.item()
            elif hasattr(v, "item"):
                v = v.item()
        except Exception:
            pass
        if v is None or not math.isfinite(float(v)):
            raise ValueError(f"non-finite value for var={var_name} at idx={index}")
        return float(v)


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description="Sampled output compare: legacy *.dat vs NetCDF variable")
    ap.add_argument("--legacy-bin", required=True, help="Legacy binary output file (*.dat)")
    ap.add_argument("--netcdf", required=True, help="NetCDF output file (*.nc)")
    ap.add_argument("--var", required=True, help="NetCDF variable name to compare")
    ap.add_argument("--time-dim", default="time", help="NetCDF time dimension name (default: time)")
    ap.add_argument("--obj-dim", default="", help="NetCDF object dimension name (required if not inferable)")
    ap.add_argument("--times-min", default="", help="Sample times (minutes), comma-separated; default: first 2 records")
    ap.add_argument("--indices", default="", help="Sample full indices (1-based), comma-separated; default: first 3 icol[]")
    ap.add_argument("--time-tol", type=float, default=1e-6, help="Time match tolerance (minutes)")
    ap.add_argument("--out-json", default="", help="Write JSON report (optional)")

    args = ap.parse_args(list(argv))
    legacy_path = os.path.abspath(args.legacy_bin)
    nc_path = os.path.abspath(args.netcdf)

    legacy = _read_legacy_bin(legacy_path)

    if not args.times_min:
        times_min = legacy.times_min[:2]
    else:
        times_min = _parse_float_list(args.times_min)

    if not args.indices:
        indices_1based = legacy.icol_1based[:3]
    else:
        indices_1based = _parse_int_list(args.indices)

    # Infer obj_dim if possible
    obj_dim = args.obj_dim.strip()
    if not obj_dim:
        netCDF4 = _require_netCDF4()
        with netCDF4.Dataset(nc_path, "r") as ds:
            dims = list(ds.variables[args.var].dimensions)
            cand = [d for d in dims if d != args.time_dim]
            if len(cand) == 1:
                obj_dim = cand[0]
            else:
                raise ValueError(f"Cannot infer obj_dim from dims={dims}; pass --obj-dim")

    samples: List[Dict[str, Any]] = []

    # Map legacy icol -> column index
    col_of_index: Dict[int, int] = {idx: j for j, idx in enumerate(legacy.icol_1based)}

    for t in times_min:
        ti = _find_time_index(legacy.times_min, float(t), tol=float(args.time_tol))
        for idx1 in indices_1based:
            if idx1 not in col_of_index:
                continue
            col = col_of_index[idx1]
            legacy_v = float(legacy.values[ti][col])
            nc_v = _read_netcdf_value(
                nc_path,
                var_name=args.var,
                time_idx=ti,
                obj_idx0=int(idx1) - 1,
                time_dim=args.time_dim,
                obj_dim=obj_dim,
            )
            samples.append(
                {
                    "t_min": float(legacy.times_min[ti]),
                    "index_1based": int(idx1),
                    "legacy": legacy_v,
                    "netcdf": nc_v,
                    "diff": legacy_v - nc_v,
                }
            )

    diffs = [abs(float(s["diff"])) for s in samples]
    report = {
        "legacy_bin": legacy_path,
        "netcdf": nc_path,
        "var": args.var,
        "time_dim": args.time_dim,
        "obj_dim": obj_dim,
        "samples": samples,
        "summary": {"count": len(samples), "max_abs": max(diffs) if diffs else 0.0, "mean_abs": sum(diffs) / len(diffs) if diffs else 0.0},
    }

    print("== Output compare summary (legacy - netcdf) ==")
    print(f"- samples: {report['summary']['count']}")
    print(f"- max_abs: {report['summary']['max_abs']:.6g}")
    print(f"- mean_abs: {report['summary']['mean_abs']:.6g}")

    if args.out_json:
        out_path = os.path.abspath(args.out_json)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

