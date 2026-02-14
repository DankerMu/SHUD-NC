#!/usr/bin/env python3
"""
Generate CSV forcing baseline by sampling a NetCDF forcing product at the
forcing stations defined by an existing SHUD run directory.

Purpose
-------
For regression testing "CSV forcing vs NetCDF forcing" (Phase A), we want a
baseline set of per-station forcing CSV files that matches SHUD's NetCDF forcing
provider (conversion + quantization semantics), so that:
  - tools/compare_forcing.py can verify max_abs_diff ~= 0
  - SHUD legacy *.dat outputs match byte-for-byte between CSV and NetCDF runs

This tool reads:
  - <run_dir>/input/<prj>/<prj>.tsd.forc        (stations + forcing path + ForcStartTime)
  - <run_dir>/input/<prj>/<prj>.cfg.para        (START/END days -> simulation interval)
  - <nc_run>/input/<prj>/<prj>.cfg.forcing      (PRODUCT/DATA_ROOT/layout/var mapping)

and writes:
  - <run_dir>/<path-from-tsd.forc>/<station>.csv

Supported products:
  - PRODUCT=ERA5   (daily files, hourly; tp/ssr accumulated -> forward-diff increments)
  - PRODUCT=GLDAS  (per-timestep files, 3-hourly; includes _FillValue remap like SHUD)

Notes
-----
This is not a general-purpose forcing exporter; it's intentionally tailored to
match SHUD's NetcdfForcingProvider behavior for regression comparisons.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _eprint(msg: str) -> None:
    import sys

    print(msg, file=sys.stderr)


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
        idx0 = len(stations)
        lon = float(parts[1])
        lat = float(parts[2])
        filename = parts[6]
        stations.append(ForcStation(idx0=idx0, lon_deg=lon, lat_deg=lat, filename=filename))

    if len(stations) != num_forc:
        raise ValueError(f"NumForc mismatch in {path}: header={num_forc}, parsed={len(stations)}")

    return TsdForc(num_forc=num_forc, forc_start_yyyymmdd=forc_start, rel_path=rel_path, stations=stations)


def _parse_yyyymmdd(v: int) -> dt.datetime:
    y = v // 10000
    m = (v // 100) % 100
    d = v % 100
    return dt.datetime(y, m, d, 0, 0, 0, tzinfo=dt.timezone.utc)


def _dt_from_forc_start(forc_start_yyyymmdd: int, t_min: float) -> dt.datetime:
    return _parse_yyyymmdd(forc_start_yyyymmdd) + dt.timedelta(minutes=float(t_min))


def _zfill(v: int, w: int) -> str:
    return str(v).zfill(w)


def _doy_3(t: dt.datetime) -> str:
    return _zfill(int(t.timetuple().tm_yday), 3)


def _floor_dt_to_minute_step(t: dt.datetime, step_min: int) -> dt.datetime:
    if step_min <= 0:
        raise ValueError(f"invalid step_min: {step_min}")
    base = dt.datetime(t.year, t.month, t.day, 0, 0, 0, tzinfo=dt.timezone.utc)
    mins = int((t - base).total_seconds() // 60)
    mins = (mins // int(step_min)) * int(step_min)
    return base + dt.timedelta(minutes=int(mins))


def _format_gldas_path(file_pattern: str, *, t: dt.datetime) -> str:
    yyyymmdd = t.strftime("%Y%m%d")
    year = t.strftime("%Y")
    doy = _doy_3(t)
    hhmm = t.strftime("%H%M")
    return (
        file_pattern.replace("{year}", year)
        .replace("{yyyy}", year)
        .replace("{doy}", doy)
        .replace("{yyyymmdd}", yyyymmdd)
        .replace("{hhmm}", hhmm)
    )


def _require_netCDF4() -> Any:
    try:
        import netCDF4  # type: ignore

        return netCDF4
    except Exception as e:
        raise RuntimeError(
            "Python package 'netCDF4' is required.\n"
            "Install:\n"
            "  python3 -m pip install netCDF4 numpy\n"
        ) from e


def _read_para_start_end_min(path: str) -> Tuple[float, float]:
    start_day: Optional[float] = None
    end_day: Optional[float] = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0].strip().upper()
            val = parts[1].strip()
            if key == "START":
                start_day = float(val)
            elif key == "END":
                end_day = float(val)
    if start_day is None or end_day is None:
        raise ValueError(f"Missing START/END in cfg.para: {path}")
    return float(start_day) * 1440.0, float(end_day) * 1440.0


def _write_station_csv(
    path: str,
    *,
    forc_start_yyyymmdd: int,
    times_min: Sequence[float],
    prec_mm_day: Sequence[float],
    temp_c: Sequence[float],
    rh_1: Sequence[float],
    wind_ms: Sequence[float],
    rn_wm2: Sequence[float],
) -> None:
    if not times_min:
        raise ValueError("empty time axis for station csv")
    n = len(times_min)
    if not (
        len(prec_mm_day) == len(temp_c) == len(rh_1) == len(wind_ms) == len(rn_wm2) == n
    ):
        raise ValueError("length mismatch in station csv arrays")

    # Match rSHUD::write.tsd header format used by AutoSHUD:
    #   nrow ncol start_yyyymmdd end_yyyymmdd dt_sec
    # ncol includes the time column.
    t0 = _dt_from_forc_start(forc_start_yyyymmdd, float(times_min[0]))
    t1 = _dt_from_forc_start(forc_start_yyyymmdd, float(times_min[-1]))
    header = f"{n}\t6\t{forc_start_yyyymmdd}\t{t1.strftime('%Y%m%d')}\t86400\n"

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("Time_interval\tPrecip_mm.d\tTemp_C\tRH_1\tWind_m.s\tRN_w.m2\n")
        for i in range(n):
            # Use repr(time_day) so timeDay*1440 round-trips cleanly for step-function pointer logic.
            time_day = float(times_min[i]) / 1440.0
            f.write(
                f"{repr(time_day)}\t"
                f"{float(prec_mm_day[i]):.4f}\t"
                f"{float(temp_c[i]):.2f}\t"
                f"{float(rh_1[i]):.4f}\t"
                f"{float(wind_ms[i]):.2f}\t"
                f"{float(rn_wm2[i]):.0f}\n"
            )


def _quantize_prec_mm_day(x: float) -> float:
    if not math.isfinite(float(x)) or float(x) < 0.0:
        x = 0.0
    # SHUD uses nearbyint(x*1e4)/1e4 (ties-to-even); Python round matches ties-to-even.
    x = round(float(x), 4)
    if float(x) < 0.0001:
        x = 0.0
    return float(x)


def _quantize_temp_c(x: float) -> float:
    if not math.isfinite(float(x)):
        x = 0.0
    return float(round(float(x), 2))


def _quantize_rh_1(x: float) -> float:
    if not math.isfinite(float(x)):
        x = 0.0
    x = max(0.0, min(1.0, float(x)))
    x = round(float(x), 4)
    x = max(0.0, min(1.0, float(x)))
    return float(x)


def _quantize_wind_ms(x: float) -> float:
    if not math.isfinite(float(x)):
        x = 0.0
    x = abs(float(x))
    x = round(float(x), 2)
    if x < 0.05:
        x = 0.05
    return float(x)


def _quantize_rn_wm2(x: float) -> float:
    if not math.isfinite(float(x)):
        x = 0.0
    if float(x) < 0.0:
        x = 0.0
    return float(round(float(x), 0))


def _era5_rh_from_dewpoint(*, temp_c: float, dew_c: float) -> float:
    # Same as SHUD NetcdfForcingProvider (ERA5).
    es = 6.112 * math.exp(17.67 * float(temp_c) / (float(temp_c) + 243.5))
    ea = 6.112 * math.exp(17.67 * float(dew_c) / (float(dew_c) + 243.5))
    rh = 0.0
    if math.isfinite(float(es)) and float(es) > 0.0 and math.isfinite(float(ea)):
        rh = float(ea) / float(es)
    if not math.isfinite(float(rh)):
        rh = 0.0
    rh = max(0.0, min(1.0, float(rh)))
    return float(rh)


def _era5_resolve_day_file(
    forcing_cfg: Dict[str, str],
    *,
    day_dt: dt.datetime,
) -> str:
    data_root = forcing_cfg["DATA_ROOT"]
    file_pattern = forcing_cfg["LAYOUT_FILE_PATTERN"]
    year_subdir = forcing_cfg.get("LAYOUT_YEAR_SUBDIR", "0").strip() not in ("", "0", "FALSE", "false")

    yyyymmdd = day_dt.strftime("%Y%m%d")
    fn = file_pattern.replace("{yyyymmdd}", yyyymmdd)
    if year_subdir:
        return os.path.join(data_root, f"{day_dt.year:04d}", fn)
    return os.path.join(data_root, fn)


def _generate_era5(
    *,
    forcing_cfg: Dict[str, str],
    tsd: TsdForc,
    sim_start_min: float,
    sim_end_min: float,
    out_dir: str,
) -> None:
    netCDF4 = _require_netCDF4()
    import numpy as np  # type: ignore

    v_tp = forcing_cfg["NC_VAR_TP"]
    v_t2m = forcing_cfg["NC_VAR_T2M"]
    v_d2m = forcing_cfg["NC_VAR_D2M"]
    v_u10 = forcing_cfg["NC_VAR_U10"]
    v_v10 = forcing_cfg["NC_VAR_V10"]
    v_ssr = forcing_cfg["NC_VAR_SSR"]

    lat_var = forcing_cfg.get("LAT_VAR", forcing_cfg.get("NC_DIM_LAT", "latitude"))
    lon_var = forcing_cfg.get("LON_VAR", forcing_cfg.get("NC_DIM_LON", "longitude"))

    # Output time axis: dt = 60 min (ERA5 hourly).
    dt_min = 60.0
    n_steps = max(1, int(math.ceil(float(sim_end_min) / dt_min)))
    times_out = [float(k) * dt_min for k in range(n_steps)]  # last record covers +dt_min

    # Boundary times needed for accumulated forward-diff increments.
    times_bound = [float(k) * dt_min for k in range(n_steps + 1)]

    base = _parse_yyyymmdd(tsd.forc_start_yyyymmdd)
    last_bound_dt = _dt_from_forc_start(tsd.forc_start_yyyymmdd, times_bound[-1])
    max_day = int((last_bound_dt - base).total_seconds() // 86400)

    # Open the first day file to read grid coords and build station->grid mapping.
    first_day = base
    f0 = _era5_resolve_day_file(forcing_cfg, day_dt=first_day)
    with netCDF4.Dataset(f0, "r") as ds0:
        lat_arr = np.array(ds0.variables[lat_var][:], dtype=float)
        lon_arr = np.array(ds0.variables[lon_var][:], dtype=float)
    lon_min = float(lon_arr.min())
    lon_max = float(lon_arr.max())
    lon_0360 = lon_min >= 0.0 and lon_max > 180.0

    st_lon = np.array([s.lon_deg for s in tsd.stations], dtype=float)
    st_lat = np.array([s.lat_deg for s in tsd.stations], dtype=float)
    if lon_0360:
        st_lon = np.where(st_lon < 0.0, st_lon + 360.0, st_lon)
        st_lon = np.mod(st_lon, 360.0)

    # Nearest-neighbor mapping (ties pick the first index, matching argmin).
    lon_idx = np.array([int(np.abs(lon_arr - float(x)).argmin()) for x in st_lon], dtype=int)
    lat_idx = np.array([int(np.abs(lat_arr - float(y)).argmin()) for y in st_lat], dtype=int)

    lon_lo = int(lon_idx.min())
    lon_hi = int(lon_idx.max())
    lat_lo = int(lat_idx.min())
    lat_hi = int(lat_idx.max())
    lon_off = lon_idx - lon_lo
    lat_off = lat_idx - lat_lo

    nst = len(tsd.stations)
    n_bound = len(times_bound)

    raw_tp = np.zeros((nst, n_bound), dtype=float)
    raw_ssr = np.zeros((nst, n_bound), dtype=float)
    raw_t2m = np.zeros((nst, n_bound), dtype=float)
    raw_d2m = np.zeros((nst, n_bound), dtype=float)
    raw_u10 = np.zeros((nst, n_bound), dtype=float)
    raw_v10 = np.zeros((nst, n_bound), dtype=float)

    # Load per-day subsets.
    for day in range(0, max_day + 1):
        day_dt = base + dt.timedelta(days=int(day))
        fn = _era5_resolve_day_file(forcing_cfg, day_dt=day_dt)
        if not os.path.exists(fn):
            raise FileNotFoundError(fn)
        with netCDF4.Dataset(fn, "r") as ds:
            tp = ds.variables[v_tp][:, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            ssr = ds.variables[v_ssr][:, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            t2m = ds.variables[v_t2m][:, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            d2m = ds.variables[v_d2m][:, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            u10 = ds.variables[v_u10][:, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            v10 = ds.variables[v_v10][:, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]

            for h in range(24):
                k = day * 24 + h
                if k >= n_bound:
                    break
                raw_tp[:, k] = np.array(tp[h, :, :], dtype=float)[lat_off, lon_off]
                raw_ssr[:, k] = np.array(ssr[h, :, :], dtype=float)[lat_off, lon_off]
                raw_t2m[:, k] = np.array(t2m[h, :, :], dtype=float)[lat_off, lon_off]
                raw_d2m[:, k] = np.array(d2m[h, :, :], dtype=float)[lat_off, lon_off]
                raw_u10[:, k] = np.array(u10[h, :, :], dtype=float)[lat_off, lon_off]
                raw_v10[:, k] = np.array(v10[h, :, :], dtype=float)[lat_off, lon_off]

    # Convert to SHUD 5-var forcing (match SHUD NetcdfForcingProvider).
    dt_sec = 3600.0

    prec = np.zeros((nst, n_steps), dtype=float)
    temp = np.zeros((nst, n_steps), dtype=float)
    rh = np.zeros((nst, n_steps), dtype=float)
    wind = np.zeros((nst, n_steps), dtype=float)
    rn = np.zeros((nst, n_steps), dtype=float)

    for k in range(n_steps):
        tp0 = raw_tp[:, k]
        tp1 = raw_tp[:, k + 1]
        d_tp = tp1 - tp0
        tp_tol = np.maximum(1e-5, 1e-4 * np.maximum(np.abs(tp0), np.abs(tp1)))
        tp_inc_m = np.where(d_tp >= -tp_tol, np.maximum(0.0, d_tp), np.maximum(0.0, tp1))

        ssr0 = raw_ssr[:, k]
        ssr1 = raw_ssr[:, k + 1]
        d_ssr = ssr1 - ssr0
        ssr_tol = np.maximum(1000.0, 1e-4 * np.maximum(np.abs(ssr0), np.abs(ssr1)))
        ssr_inc = np.where(d_ssr >= -ssr_tol, np.maximum(0.0, d_ssr), np.maximum(0.0, ssr1))

        # Precip (mm/day)
        prec_k = tp_inc_m * 1000.0 * (86400.0 / dt_sec)
        # Quantize + threshold (scalar helper, but vectorized loop is cheap here)
        prec[:, k] = np.array([_quantize_prec_mm_day(float(x)) for x in prec_k], dtype=float)

        # RN (W/m2)
        rn_k = ssr_inc / dt_sec
        rn[:, k] = np.array([_quantize_rn_wm2(float(x)) for x in rn_k], dtype=float)

        # Temp (C), quantize 2 decimals before RH calc (match SHUD).
        temp_c = raw_t2m[:, k] - 273.15
        temp[:, k] = np.array([_quantize_temp_c(float(x)) for x in temp_c], dtype=float)

        # RH (0-1) from dewpoint + quantized temperature.
        dew_c = raw_d2m[:, k] - 273.15
        rh_k = [_era5_rh_from_dewpoint(temp_c=float(temp[i, k]), dew_c=float(dew_c[i])) for i in range(nst)]
        rh[:, k] = np.array([_quantize_rh_1(float(x)) for x in rh_k], dtype=float)

        # Wind (m/s)
        wind_k = np.sqrt(raw_u10[:, k] * raw_u10[:, k] + raw_v10[:, k] * raw_v10[:, k])
        wind[:, k] = np.array([_quantize_wind_ms(float(x)) for x in wind_k], dtype=float)

    # Write per-station CSV.
    _eprint(f"Writing ERA5 forcing CSV: stations={nst}, steps={n_steps}, out_dir={out_dir}")
    for i, st in enumerate(tsd.stations):
        out_path = os.path.join(out_dir, st.filename)
        _write_station_csv(
            out_path,
            forc_start_yyyymmdd=tsd.forc_start_yyyymmdd,
            times_min=times_out,
            prec_mm_day=prec[i, :].tolist(),
            temp_c=temp[i, :].tolist(),
            rh_1=rh[i, :].tolist(),
            wind_ms=wind[i, :].tolist(),
            rn_wm2=rn[i, :].tolist(),
        )


def _gldas_is_valid(
    *,
    temp_var: Any,
    time_idx: int,
    lat_idx: int,
    lon_idx: int,
    fill: Optional[float],
    missing: Optional[float],
) -> bool:
    try:
        v = temp_var[time_idx, lat_idx, lon_idx]
        import numpy as np  # type: ignore

        if isinstance(v, np.ma.MaskedArray):
            if bool(np.ma.is_masked(v)):
                return False
            v = v.item()
        elif hasattr(v, "item"):
            v = v.item()
        x = float(v)
    except Exception:
        return False
    if not math.isfinite(float(x)):
        return False
    if fill is not None and float(x) == float(fill):
        return False
    if missing is not None and float(x) == float(missing):
        return False
    return True


def _generate_gldas(
    *,
    forcing_cfg: Dict[str, str],
    tsd: TsdForc,
    sim_start_min: float,
    sim_end_min: float,
    out_dir: str,
) -> None:
    netCDF4 = _require_netCDF4()
    import numpy as np  # type: ignore

    file_pattern = forcing_cfg["LAYOUT_FILE_PATTERN"]
    data_root = forcing_cfg["DATA_ROOT"]

    dim_lat = forcing_cfg.get("NC_DIM_LAT", "lat")
    dim_lon = forcing_cfg.get("NC_DIM_LON", "lon")

    v_prec = forcing_cfg["NC_VAR_PREC"]
    v_temp = forcing_cfg["NC_VAR_TEMP"]
    v_shum = forcing_cfg["NC_VAR_SHUM"]
    v_pres = forcing_cfg["NC_VAR_PRES"]
    v_wind = forcing_cfg["NC_VAR_WIND"]
    v_srad = forcing_cfg["NC_VAR_SRAD"]

    dt_min = 180.0
    n_steps = max(1, int(math.ceil(float(sim_end_min) / dt_min)))
    times_out = [float(k) * dt_min for k in range(n_steps)]  # last record covers +dt_min

    # Use SHUD's t0 file for water-mask remap: first timestep used by the simulation.
    start_step = int(math.floor(float(sim_start_min) / dt_min))
    t0_min = float(start_step) * dt_min
    t0_dt = _dt_from_forc_start(tsd.forc_start_yyyymmdd, t0_min)
    t0_file = os.path.join(data_root, _format_gldas_path(file_pattern, t=t0_dt))
    if not os.path.exists(t0_file):
        raise FileNotFoundError(t0_file)

    st_lon = [s.lon_deg for s in tsd.stations]
    st_lat = [s.lat_deg for s in tsd.stations]
    nst = len(tsd.stations)

    with netCDF4.Dataset(t0_file, "r") as ds0:
        lat_arr = np.array(ds0.variables[dim_lat][:], dtype=float)
        lon_arr = np.array(ds0.variables[dim_lon][:], dtype=float)
        temp_var = ds0.variables[v_temp]
        fill = getattr(temp_var, "_FillValue", None)
        missing = getattr(temp_var, "missing_value", None)
        fill_f = float(fill) if fill is not None else None
        missing_f = float(missing) if missing is not None else None

        lon_min = float(lon_arr.min())
        lon_max = float(lon_arr.max())
        lon_0360 = lon_min >= 0.0 and lon_max > 180.0

        st_lon_adj = list(st_lon)
        if lon_0360:
            st_lon_adj = [x + 360.0 if x < 0.0 else x for x in st_lon_adj]
            st_lon_adj = [x % 360.0 for x in st_lon_adj]

        # Initial nearest mapping.
        lon_idx0 = [int(np.abs(lon_arr - float(x)).argmin()) for x in st_lon_adj]
        lat_idx0 = [int(np.abs(lat_arr - float(y)).argmin()) for y in st_lat]

        # Remap off invalid cells (match SHUD: max_r=10, dist2 in lon/lat degrees).
        lon_idx: List[int] = []
        lat_idx: List[int] = []
        remapped = 0
        for i in range(nst):
            j0 = int(lon_idx0[i])
            k0 = int(lat_idx0[i])
            if _gldas_is_valid(
                temp_var=temp_var,
                time_idx=0,
                lat_idx=k0,
                lon_idx=j0,
                fill=fill_f,
                missing=missing_f,
            ):
                lon_idx.append(j0)
                lat_idx.append(k0)
                continue

            best: Optional[Tuple[int, int]] = None
            best_dist2 = float("inf")
            max_r = 10
            for r in range(1, max_r + 1):
                found = False
                k_lo = max(0, k0 - r)
                k_hi = min(int(len(lat_arr)) - 1, k0 + r)
                j_lo = max(0, j0 - r)
                j_hi = min(int(len(lon_arr)) - 1, j0 + r)
                for kk in range(k_lo, k_hi + 1):
                    for jj in range(j_lo, j_hi + 1):
                        if not _gldas_is_valid(
                            temp_var=temp_var,
                            time_idx=0,
                            lat_idx=kk,
                            lon_idx=jj,
                            fill=fill_f,
                            missing=missing_f,
                        ):
                            continue
                        dlon = abs(float(lon_arr[jj]) - float(st_lon_adj[i]))
                        if lon_0360:
                            dlon = min(dlon, 360.0 - dlon)
                        dlat = abs(float(lat_arr[kk]) - float(st_lat[i]))
                        dist2 = dlon * dlon + dlat * dlat
                        if dist2 < best_dist2:
                            best_dist2 = dist2
                            best = (kk, jj)
                            found = True
                if found:
                    break
            if best is None:
                raise RuntimeError(
                    f"GLDAS remap failed for station[{i}] lon={st_lon[i]} lat={st_lat[i]} (nearest idx_lat={k0} idx_lon={j0})"
                )
            kk, jj = best
            lat_idx.append(int(kk))
            lon_idx.append(int(jj))
            remapped += 1

    if remapped > 0:
        _eprint(f"GLDAS remap: {remapped}/{nst} stations moved off _FillValue grid cells (using t0 file).")

    lon_idx_np = np.array(lon_idx, dtype=int)
    lat_idx_np = np.array(lat_idx, dtype=int)
    lon_lo = int(lon_idx_np.min())
    lon_hi = int(lon_idx_np.max())
    lat_lo = int(lat_idx_np.min())
    lat_hi = int(lat_idx_np.max())
    lon_off = lon_idx_np - lon_lo
    lat_off = lat_idx_np - lat_lo

    prec = np.zeros((nst, n_steps), dtype=float)
    temp = np.zeros((nst, n_steps), dtype=float)
    rh = np.zeros((nst, n_steps), dtype=float)
    wind = np.zeros((nst, n_steps), dtype=float)
    rn = np.zeros((nst, n_steps), dtype=float)

    for ti, tmin in enumerate(times_out):
        step_dt = _floor_dt_to_minute_step(_dt_from_forc_start(tsd.forc_start_yyyymmdd, tmin), 180)
        rel = _format_gldas_path(file_pattern, t=step_dt)
        fn = os.path.join(data_root, rel)
        if not os.path.exists(fn):
            raise FileNotFoundError(fn)
        with netCDF4.Dataset(fn, "r") as ds:
            # One file contains all variables; time dim length=1.
            pr = ds.variables[v_prec][0, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            tk = ds.variables[v_temp][0, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            shum = ds.variables[v_shum][0, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            pres = ds.variables[v_pres][0, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            wi = ds.variables[v_wind][0, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]
            sr = ds.variables[v_srad][0, lat_lo : lat_hi + 1, lon_lo : lon_hi + 1]

            pr_v = np.array(pr, dtype=float)[lat_off, lon_off]
            tk_v = np.array(tk, dtype=float)[lat_off, lon_off]
            shum_v = np.array(shum, dtype=float)[lat_off, lon_off]
            pres_v = np.array(pres, dtype=float)[lat_off, lon_off]
            wi_v = np.array(wi, dtype=float)[lat_off, lon_off]
            sr_v = np.array(sr, dtype=float)[lat_off, lon_off]

        # Precip: kg/m^2/s -> mm/day
        prec_mm_day = pr_v * 86400.0
        prec[:, ti] = np.array([_quantize_prec_mm_day(float(x)) for x in prec_mm_day], dtype=float)

        # Temp
        temp_c = tk_v - 273.15
        temp[:, ti] = np.array([_quantize_temp_c(float(x)) for x in temp_c], dtype=float)

        # RH (same as CMFD2/GLDAS in SHUD)
        rh_percent = 0.263 * pres_v * shum_v / np.exp(17.67 * (tk_v - 273.15) / (tk_v - 29.65))
        rh_percent = np.clip(rh_percent, 0.0, 100.0)
        rh_1 = rh_percent / 100.0
        rh[:, ti] = np.array([_quantize_rh_1(float(x)) for x in rh_1], dtype=float)

        # Wind
        wind[:, ti] = np.array([_quantize_wind_ms(float(x)) for x in wi_v], dtype=float)

        # RN
        rn[:, ti] = np.array([_quantize_rn_wm2(float(x)) for x in sr_v], dtype=float)

    _eprint(f"Writing GLDAS forcing CSV: stations={nst}, steps={n_steps}, out_dir={out_dir}")
    for i, st in enumerate(tsd.stations):
        out_path = os.path.join(out_dir, st.filename)
        _write_station_csv(
            out_path,
            forc_start_yyyymmdd=tsd.forc_start_yyyymmdd,
            times_min=times_out,
            prec_mm_day=prec[i, :].tolist(),
            temp_c=temp[i, :].tolist(),
            rh_1=rh[i, :].tolist(),
            wind_ms=wind[i, :].tolist(),
            rn_wm2=rn[i, :].tolist(),
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Generate CSV forcing baseline for regression vs NetCDF forcing")
    p.add_argument("--run", required=True, help="Target run_dir (contains input/<prj>/<prj>.tsd.forc)")
    p.add_argument("--nc-run", required=True, help="NetCDF run_dir (contains input/<prj>/<prj>.cfg.forcing)")
    p.add_argument("--prj", required=True, help="Project name (e.g. qhh)")
    args = p.parse_args(list(argv) if argv is not None else None)

    run_dir = os.path.abspath(args.run)
    nc_run = os.path.abspath(args.nc_run)
    prj = str(args.prj)

    tsd_path = os.path.join(run_dir, "input", prj, f"{prj}.tsd.forc")
    para_path = os.path.join(run_dir, "input", prj, f"{prj}.cfg.para")
    cfg_forcing_path = os.path.join(nc_run, "input", prj, f"{prj}.cfg.forcing")

    tsd = _read_tsd_forc(tsd_path)
    sim_start_min, sim_end_min = _read_para_start_end_min(para_path)

    forcing_cfg = _read_kv_cfg(cfg_forcing_path)
    if not forcing_cfg.get("PRODUCT"):
        raise ValueError(f"Missing PRODUCT in cfg.forcing: {cfg_forcing_path}")

    # DATA_ROOT in cfg.forcing may be relative to nc_run.
    if "DATA_ROOT" in forcing_cfg and not os.path.isabs(forcing_cfg["DATA_ROOT"]):
        forcing_cfg["DATA_ROOT"] = os.path.normpath(os.path.join(nc_run, forcing_cfg["DATA_ROOT"]))

    rel = tsd.rel_path.strip()
    out_dir = rel if os.path.isabs(rel) else os.path.normpath(os.path.join(run_dir, rel))
    os.makedirs(out_dir, exist_ok=True)

    product = forcing_cfg["PRODUCT"].strip().upper()
    if product == "ERA5":
        _generate_era5(
            forcing_cfg=forcing_cfg,
            tsd=tsd,
            sim_start_min=float(sim_start_min),
            sim_end_min=float(sim_end_min),
            out_dir=out_dir,
        )
    elif product == "GLDAS":
        _generate_gldas(
            forcing_cfg=forcing_cfg,
            tsd=tsd,
            sim_start_min=float(sim_start_min),
            sim_end_min=float(sim_end_min),
            out_dir=out_dir,
        )
    else:
        raise ValueError(f"Unsupported PRODUCT for baseline generation: {product!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

