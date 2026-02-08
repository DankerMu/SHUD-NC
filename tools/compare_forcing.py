#!/usr/bin/env python3
"""
Sampled forcing regression compare: baseline CSV vs NetCDF forcing.

This tool is intentionally sampled (not full-grid/full-time) to keep comparisons
fast and reviewable.
"""

from __future__ import annotations

import argparse
import bisect
import dataclasses
import datetime as dt
import glob
import json
import math
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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


def _zfill(v: int, w: int) -> str:
    return str(v).zfill(w)


def _parse_yyyymmdd(v: int) -> dt.datetime:
    y = v // 10000
    m = (v // 100) % 100
    d = v % 100
    return dt.datetime(y, m, d, 0, 0, 0, tzinfo=dt.timezone.utc)


def _yyyymm_from_forc_start(forc_start_yyyymmdd: int, t_min: float) -> str:
    base = _parse_yyyymmdd(forc_start_yyyymmdd)
    t = base + dt.timedelta(minutes=float(t_min))
    return f"{t.year:04d}{t.month:02d}"


def _read_kv_cfg(path: str) -> Dict[str, str]:
    kv: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                raise ValueError(f"Invalid KEY VALUE line at {path}:{line_no}: {raw!r}")
            key = parts[0].strip().upper()
            val = parts[1].strip()
            kv[key] = val
    return kv


@dataclasses.dataclass(frozen=True)
class ForcStation:
    idx0: int
    lon_deg: float
    lat_deg: float
    filename: str


@dataclasses.dataclass(frozen=True)
class TsdForc:
    num_forc: int
    forc_start_yyyymmdd: int
    rel_path: str
    stations: List[ForcStation]


def _read_tsd_forc(path: str) -> TsdForc:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    if not lines:
        raise ValueError(f"Empty tsd.forc: {path}")

    head = lines[0].split()
    if len(head) < 2:
        raise ValueError(f"Invalid tsd.forc header: {path}: {lines[0]!r}")
    num_forc = int(head[0])
    forc_start = int(head[1])

    rel_path = ""
    if len(lines) >= 2:
        rel_path = lines[1].strip()

    stations: List[ForcStation] = []
    for raw in lines[3:]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 7:
            raise ValueError(f"Invalid station record in {path}: {raw!r}")
        # ID Lon Lat X Y Z Filename
        idx0 = len(stations)
        lon = float(parts[1])
        lat = float(parts[2])
        filename = parts[6]
        stations.append(ForcStation(idx0=idx0, lon_deg=lon, lat_deg=lat, filename=filename))

    if len(stations) != num_forc:
        raise ValueError(f"NumForc mismatch in {path}: header={num_forc}, parsed={len(stations)}")

    return TsdForc(num_forc=num_forc, forc_start_yyyymmdd=forc_start, rel_path=rel_path, stations=stations)


def _resolve_station_csv_path(tsd_dir: str, rel_path: str, filename: str) -> str:
    if rel_path:
        return os.path.normpath(os.path.join(tsd_dir, rel_path, filename))
    return os.path.normpath(os.path.join(tsd_dir, filename))


def _read_station_csv_at(path: str, t_min: float) -> Tuple[float, float, float, float, float]:
    # CSV format:
    # line1: nrow ncol start_yyyymmdd [end_yyyymmdd]
    # line2: header
    # data: time_day 5vars...
    with open(path, "r", encoding="utf-8") as f:
        _ = f.readline()
        _ = f.readline()

        prev_t: Optional[float] = None
        prev_vals: Optional[Tuple[float, float, float, float, float]] = None

        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 6:
                raise ValueError(f"Invalid forcing csv row: {path}: {raw!r}")
            time_day = float(parts[0])
            tt = time_day * 1440.0
            vals = tuple(float(x) for x in parts[1:6])

            if tt > t_min + 1e-9:
                if prev_vals is not None:
                    return prev_vals
                return vals  # t_min before first data row

            prev_t = tt
            prev_vals = vals

        if prev_vals is None:
            raise ValueError(f"No data rows in forcing csv: {path}")
        return prev_vals


def _require_netCDF4() -> Any:
    try:
        import netCDF4  # type: ignore

        return netCDF4
    except Exception as e:
        raise RuntimeError(
            "Python package 'netCDF4' is required for NetCDF forcing comparison.\n"
            "Install:\n"
            "  python3 -m pip install netCDF4 numpy\n"
        ) from e


def _resolve_single_glob(pattern: str) -> str:
    matches = sorted(glob.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Glob must match exactly 1 file, got {len(matches)}: {pattern}")
    return matches[0]


def _parse_units_since(units: str) -> Tuple[float, dt.datetime]:
    # e.g. "hours since 1900-01-01 00:00:0.0"
    u = units.strip().lower()
    if "since" not in u:
        raise ValueError(f"Unsupported time units (missing since): {units!r}")
    unit_part, base_part = u.split("since", 1)
    unit_part = unit_part.strip()
    base_part = base_part.strip().replace("t", " ")

    if unit_part.startswith("second"):
        factor_min = 1.0 / 60.0
    elif unit_part.startswith("minute"):
        factor_min = 1.0
    elif unit_part.startswith("hour"):
        factor_min = 60.0
    elif unit_part.startswith("day"):
        factor_min = 1440.0
    else:
        raise ValueError(f"Unsupported time unit: {units!r}")

    # base date
    date_s = base_part.split()[0]
    time_s = base_part.split()[1] if len(base_part.split()) >= 2 else "00:00:00"
    y, m, d = (int(x) for x in date_s.split("-"))

    hh, mm, ss = 0, 0, 0
    tparts = time_s.split(":")
    if len(tparts) >= 2:
        hh = int(tparts[0])
        mm = int(tparts[1])
        # ignore seconds fractional
        if len(tparts) >= 3:
            try:
                ss = int(float(tparts[2]))
            except Exception:
                ss = 0
    base = dt.datetime(y, m, d, hh, mm, ss, tzinfo=dt.timezone.utc)
    return factor_min, base


def _cmfd2_precip_units_kind(units: str) -> str:
    u = units.strip().lower()
    if "kg" in u and ("m-2" in u or "m**-2" in u) and ("s-1" in u or "s**-1" in u):
        return "KG_M2_S"
    if "mm" in u and ("hr" in u or "h-1" in u or "h**-1" in u):
        return "MM_HR"
    if "mm" in u and ("day" in u or "d-1" in u or "d**-1" in u):
        return "MM_DAY"
    return "UNKNOWN"


def _read_netcdf_point(
    ds: Any,
    *,
    var_name: str,
    dim_time: str,
    dim_lat: str,
    dim_lon: str,
    time_idx: int,
    lat_idx: int,
    lon_idx: int,
) -> float:
    var = ds.variables[var_name]
    dims = list(var.dimensions)
    index: List[int] = []
    for d in dims:
        if d == dim_time:
            index.append(time_idx)
        elif d == dim_lat:
            index.append(lat_idx)
        elif d == dim_lon:
            index.append(lon_idx)
        else:
            index.append(0)
    v = var[tuple(index)]
    # netCDF4 may return masked arrays
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


def _cmfd2_netcdf_at(
    *,
    forcing_cfg: Dict[str, str],
    forc_start_yyyymmdd: int,
    station_lon_deg: float,
    station_lat_deg: float,
    t_min: float,
    clamp: bool,
    time_tol_min: float,
) -> Dict[str, float]:
    netCDF4 = _require_netCDF4()

    product = forcing_cfg.get("PRODUCT", "").upper()
    if product != "CMFD2":
        raise ValueError(f"Only PRODUCT=CMFD2 is supported for now (got {product!r})")

    data_root = forcing_cfg["DATA_ROOT"]
    file_pattern = forcing_cfg["LAYOUT_FILE_PATTERN"]

    dim_time = forcing_cfg.get("NC_DIM_TIME", "time")
    dim_lat = forcing_cfg.get("NC_DIM_LAT", "lat")
    dim_lon = forcing_cfg.get("NC_DIM_LON", "lon")

    time_var = forcing_cfg.get("TIME_VAR", dim_time)
    lat_var = forcing_cfg.get("LAT_VAR", dim_lat)
    lon_var = forcing_cfg.get("LON_VAR", dim_lon)

    yyyymm = _yyyymm_from_forc_start(forc_start_yyyymmdd, t_min)

    def resolve(var_key: str) -> Tuple[str, str]:
        vname = forcing_cfg[f"NC_VAR_{var_key}"]
        vdir = forcing_cfg[f"LAYOUT_VAR_DIR_{var_key}"]
        pat = file_pattern.replace("{var_lower}", vname.lower()).replace("{yyyymm}", yyyymm)
        full = os.path.join(data_root, vdir, pat)
        return _resolve_single_glob(full), vname

    f_prec, v_prec = resolve("PREC")
    f_temp, v_temp = resolve("TEMP")
    f_shum, v_shum = resolve("SHUM")
    f_srad, v_srad = resolve("SRAD")
    f_wind, v_wind = resolve("WIND")
    f_pres, v_pres = resolve("PRES")

    with netCDF4.Dataset(f_prec, "r") as ds_grid:
        lat_arr = ds_grid.variables[lat_var][:]
        lon_arr = ds_grid.variables[lon_var][:]
        lon_min = float(lon_arr.min())
        lon_max = float(lon_arr.max())
        lon_0360 = lon_min >= 0.0 and lon_max > 180.0

        slon = float(station_lon_deg)
        if lon_0360:
            if slon < 0.0:
                slon += 360.0
            while slon >= 360.0:
                slon -= 360.0

        # nearest search
        lat_idx = int(abs(lat_arr - station_lat_deg).argmin())
        lon_idx = int(abs(lon_arr - slon).argmin())

        # time index (step function)
        time_vals = ds_grid.variables[time_var][:]
        units = getattr(ds_grid.variables[time_var], "units", None)
        if not isinstance(units, str) or not units.strip():
            raise ValueError(f"time variable missing units: {f_prec}:{time_var}")
        factor_min, base_dt = _parse_units_since(units)
        forc_base = _parse_yyyymmdd(forc_start_yyyymmdd)

        tmins = [
            (base_dt + dt.timedelta(minutes=float(v) * factor_min) - forc_base).total_seconds() / 60.0 for v in time_vals
        ]
        if not tmins:
            raise ValueError(f"empty time axis: {f_prec}:{time_var}")
        if any(float(tmins[j]) < float(tmins[j - 1]) - 1e-9 for j in range(1, len(tmins))):
            raise ValueError(f"non-monotonic time axis: {f_prec}:{time_var}")

        tmin_f = float(t_min)
        first = float(tmins[0])
        last = float(tmins[-1])
        tol = float(time_tol_min)

        if tmin_f < first - tol:
            if clamp:
                i = 0
            else:
                raise ValueError(f"t_min out of range (< first): t_min={tmin_f} first={first} tol={tol} file={f_prec}")
        elif tmin_f > last + tol:
            if clamp:
                i = len(tmins) - 1
            else:
                raise ValueError(f"t_min out of range (> last): t_min={tmin_f} last={last} tol={tol} file={f_prec}")
        else:
            # Step-function semantics: select the last record at/before t_min (within tolerance).
            i = bisect.bisect_right(tmins, tmin_f + tol) - 1
            if i < 0:
                i = 0
            if i >= len(tmins):
                i = len(tmins) - 1

    # open per-var files for point reads
    with netCDF4.Dataset(f_temp, "r") as ds_temp, netCDF4.Dataset(f_shum, "r") as ds_shum, netCDF4.Dataset(
        f_srad, "r"
    ) as ds_srad, netCDF4.Dataset(f_wind, "r") as ds_wind, netCDF4.Dataset(f_pres, "r") as ds_pres, netCDF4.Dataset(
        f_prec, "r"
    ) as ds_prec:
        prec_raw = _read_netcdf_point(
            ds_prec, var_name=v_prec, dim_time=dim_time, dim_lat=dim_lat, dim_lon=dim_lon, time_idx=i, lat_idx=lat_idx, lon_idx=lon_idx
        )
        temp_k = _read_netcdf_point(
            ds_temp, var_name=v_temp, dim_time=dim_time, dim_lat=dim_lat, dim_lon=dim_lon, time_idx=i, lat_idx=lat_idx, lon_idx=lon_idx
        )
        shum = _read_netcdf_point(
            ds_shum, var_name=v_shum, dim_time=dim_time, dim_lat=dim_lat, dim_lon=dim_lon, time_idx=i, lat_idx=lat_idx, lon_idx=lon_idx
        )
        srad = _read_netcdf_point(
            ds_srad, var_name=v_srad, dim_time=dim_time, dim_lat=dim_lat, dim_lon=dim_lon, time_idx=i, lat_idx=lat_idx, lon_idx=lon_idx
        )
        wind = _read_netcdf_point(
            ds_wind, var_name=v_wind, dim_time=dim_time, dim_lat=dim_lat, dim_lon=dim_lon, time_idx=i, lat_idx=lat_idx, lon_idx=lon_idx
        )
        pres = _read_netcdf_point(
            ds_pres, var_name=v_pres, dim_time=dim_time, dim_lat=dim_lat, dim_lon=dim_lon, time_idx=i, lat_idx=lat_idx, lon_idx=lon_idx
        )

        # precip units auto-detect
        units = getattr(ds_prec.variables[v_prec], "units", "")
        kind = _cmfd2_precip_units_kind(units if isinstance(units, str) else "")
        if kind == "KG_M2_S":
            prcp_mm_day = prec_raw * 86400.0
        elif kind == "MM_HR":
            prcp_mm_day = prec_raw * 24.0
        elif kind == "MM_DAY":
            prcp_mm_day = prec_raw
        else:
            raise ValueError(f"unknown CMFD2 precip units: {units!r}")

        # match AutoSHUD min threshold behavior
        if prcp_mm_day < 0.0001:
            prcp_mm_day = 0.0
        if prcp_mm_day < 0.0:
            prcp_mm_day = 0.0

        temp_c = temp_k - 273.15
        rh_percent = 0.263 * pres * shum / math.exp(17.67 * (temp_k - 273.15) / (temp_k - 29.65))
        rh_percent = max(0.0, min(100.0, float(rh_percent)))
        rh_1 = rh_percent / 100.0
        wind_ms = abs(wind)
        rn_wm2 = srad

        return {
            "Precip_mm_day": float(prcp_mm_day),
            "Temp_C": float(temp_c),
            "RH_1": float(rh_1),
            "Wind_m_s": float(wind_ms),
            "RN_W_m2": float(rn_wm2),
        }


def _summarize_diffs(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    vars_ = ["Precip_mm_day", "Temp_C", "RH_1", "Wind_m_s", "RN_W_m2"]
    summary: Dict[str, Any] = {}
    for v in vars_:
        diffs = [float(s["diff"][v]) for s in samples]
        absdiffs = [abs(x) for x in diffs]
        summary[v] = {
            "max_abs": max(absdiffs) if absdiffs else 0.0,
            "mean": sum(diffs) / len(diffs) if diffs else 0.0,
            "mean_abs": sum(absdiffs) / len(absdiffs) if absdiffs else 0.0,
        }
    return summary


def main(argv: Sequence[str]) -> int:
    p = argparse.ArgumentParser(description="Sampled forcing compare: baseline CSV vs NetCDF (CMFD2)")
    p.add_argument("--baseline-run", required=True, help="Baseline run_dir (contains input/<prj>/<prj>.tsd.forc)")
    p.add_argument("--nc-run", required=True, help="NC run_dir (contains input/<prj>/<prj>.cfg.forcing)")
    p.add_argument("--prj", required=True, help="Project name (e.g. qhh)")
    p.add_argument("--stations", default="0,1,2", help="0-based station indices, comma-separated (default: 0,1,2)")
    p.add_argument("--t-min", default="0,180", help="Sample times in minutes since ForcStartTime, comma-separated (default: 0,180)")
    p.add_argument(
        "--clamp",
        action="store_true",
        help="Allow clamping t_min outside NetCDF coverage (legacy behavior). Default: strict bounds.",
    )
    p.add_argument(
        "--time-tol-min",
        type=float,
        default=1e-3,
        help="Time tolerance (minutes) used for bounds checks and index selection (default: 1e-3).",
    )
    p.add_argument("--out-json", default="", help="Write JSON report to this path (optional)")
    p.add_argument("--fail-max-abs", type=float, default=math.inf, help="Fail if any variable max_abs exceeds this")

    args = p.parse_args(list(argv))

    baseline_run = os.path.abspath(args.baseline_run)
    nc_run = os.path.abspath(args.nc_run)
    prj = str(args.prj)

    stations_idx = _parse_int_list(args.stations)
    times_min = _parse_float_list(args.t_min)

    baseline_tsd_forc = os.path.join(baseline_run, "input", prj, f"{prj}.tsd.forc")
    tsd = _read_tsd_forc(baseline_tsd_forc)
    forc_start = tsd.forc_start_yyyymmdd

    baseline_input_dir = os.path.join(baseline_run, "input", prj)
    forcing_cfg_path = os.path.join(nc_run, "input", prj, f"{prj}.cfg.forcing")

    forcing_cfg = _read_kv_cfg(forcing_cfg_path)
    # DATA_ROOT is rendered relative to run_dir; resolve here for tool usage.
    if not os.path.isabs(forcing_cfg.get("DATA_ROOT", "")):
        forcing_cfg["DATA_ROOT"] = os.path.normpath(os.path.join(nc_run, forcing_cfg["DATA_ROOT"]))

    samples: List[Dict[str, Any]] = []

    for sidx in stations_idx:
        st = tsd.stations[sidx]
        csv_path = _resolve_station_csv_path(baseline_input_dir, tsd.rel_path, st.filename)
        for tmin in times_min:
            base_vals = _read_station_csv_at(csv_path, tmin)
            base_map = {
                "Precip_mm_day": base_vals[0],
                "Temp_C": base_vals[1],
                "RH_1": base_vals[2],
                "Wind_m_s": base_vals[3],
                "RN_W_m2": base_vals[4],
            }
            nc_map = _cmfd2_netcdf_at(
                forcing_cfg=forcing_cfg,
                forc_start_yyyymmdd=forc_start,
                station_lon_deg=st.lon_deg,
                station_lat_deg=st.lat_deg,
                t_min=tmin,
                clamp=bool(args.clamp),
                time_tol_min=float(args.time_tol_min),
            )
            diff = {k: float(base_map[k]) - float(nc_map[k]) for k in base_map.keys()}
            samples.append(
                {
                    "station_idx0": sidx,
                    "t_min": float(tmin),
                    "station_lon_deg": float(st.lon_deg),
                    "station_lat_deg": float(st.lat_deg),
                    "baseline": base_map,
                    "nc": nc_map,
                    "diff": diff,
                }
            )

    summary = _summarize_diffs(samples)
    report = {
        "baseline_run": baseline_run,
        "nc_run": nc_run,
        "prj": prj,
        "forc_start_yyyymmdd": forc_start,
        "stations_idx0": stations_idx,
        "times_min": times_min,
        "summary": summary,
        "samples": samples,
    }

    # Print a compact summary
    print("== Forcing compare summary (baseline - nc) ==")
    for v, s in summary.items():
        print(f"- {v}: max_abs={s['max_abs']:.6g} mean={s['mean']:.6g} mean_abs={s['mean_abs']:.6g}")

    # Optional JSON output
    if args.out_json:
        out_path = os.path.abspath(args.out_json)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Wrote: {out_path}")

    # Optional threshold failure
    max_over = []
    for v, s in summary.items():
        if float(s["max_abs"]) > float(args.fail_max_abs):
            max_over.append((v, s["max_abs"]))
    if max_over:
        _eprint("ERROR: max_abs diff exceeded threshold:")
        for v, mx in max_over:
            _eprint(f"- {v}: {mx}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
