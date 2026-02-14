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


def _dt_from_forc_start(forc_start_yyyymmdd: int, t_min: float) -> dt.datetime:
    base = _parse_yyyymmdd(forc_start_yyyymmdd)
    return base + dt.timedelta(minutes=float(t_min))


def _floor_dt_to_minute_step(t: dt.datetime, step_min: int) -> dt.datetime:
    if step_min <= 0:
        raise ValueError(f"invalid step_min: {step_min}")
    base = dt.datetime(t.year, t.month, t.day, 0, 0, 0, tzinfo=dt.timezone.utc)
    mins = int(round((t - base).total_seconds() / 60.0))
    mins = (mins // int(step_min)) * int(step_min)
    return base + dt.timedelta(minutes=int(mins))


def _doy_3(dt_utc: dt.datetime) -> str:
    return _zfill(int(dt_utc.timetuple().tm_yday), 3)


def _format_gldas_path(file_pattern: str, *, t: dt.datetime) -> str:
    yyyymmdd = t.strftime("%Y%m%d")
    year = t.strftime("%Y")
    doy = _doy_3(t)
    hhmm = t.strftime("%H%M")
    return (
        file_pattern.replace("{year}", year)
        .replace("{doy}", doy)
        .replace("{yyyymmdd}", yyyymmdd)
        .replace("{hhmm}", hhmm)
    )


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
    # SHUD resolves tsd.forc's "path" line relative to the model working directory
    # (run_dir), not relative to the tsd.forc file's directory.
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


def _cmfd2_precip_units_kind_from_cfg(forcing_cfg: Dict[str, str], *, units_attr: str) -> str:
    # Mirror NetcdfForcingProvider's CMFD_PRECIP_UNITS override behavior.
    raw = forcing_cfg.get("CMFD_PRECIP_UNITS", "").strip().upper()
    if not raw or raw == "AUTO":
        return _cmfd2_precip_units_kind(units_attr)
    if raw == "KG_M2_S":
        return "KG_M2_S"
    if raw in ("MM_HR", "MM/HR", "MM_H-1"):
        return "MM_HR"
    if raw in ("MM_DAY", "MM/DAY", "MM_D-1"):
        return "MM_DAY"
    raise ValueError(f"Invalid CMFD_PRECIP_UNITS override: {raw!r}")


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
        kind = _cmfd2_precip_units_kind_from_cfg(forcing_cfg, units_attr=(units if isinstance(units, str) else ""))
        if kind == "KG_M2_S":
            prcp_mm_day = prec_raw * 86400.0
        elif kind == "MM_HR":
            prcp_mm_day = prec_raw * 24.0
        elif kind == "MM_DAY":
            prcp_mm_day = prec_raw
        else:
            raise ValueError(f"unknown CMFD2 precip units: {units!r}")

        # Match NetcdfForcingProvider / AutoSHUD baseline forcing semantics:
        # quantize first, then threshold.
        if not math.isfinite(float(prcp_mm_day)) or prcp_mm_day < 0.0:
            prcp_mm_day = 0.0
        prcp_mm_day = round(float(prcp_mm_day), 4)
        if prcp_mm_day < 0.0001:
            prcp_mm_day = 0.0

        temp_c = temp_k - 273.15
        if not math.isfinite(float(temp_c)):
            temp_c = 0.0
        temp_c = round(float(temp_c), 2)
        rh_percent = 0.263 * pres * shum / math.exp(17.67 * (temp_k - 273.15) / (temp_k - 29.65))
        rh_percent = max(0.0, min(100.0, float(rh_percent)))
        rh_1 = rh_percent / 100.0
        rh_1 = round(float(rh_1), 4)
        rh_1 = max(0.0, min(1.0, float(rh_1)))

        wind_ms = abs(wind)
        wind_ms = 0.0 if not math.isfinite(float(wind_ms)) else float(wind_ms)
        wind_ms = round(float(wind_ms), 2)
        if wind_ms < 0.05:
            wind_ms = 0.05

        rn_wm2 = srad
        rn_wm2 = 0.0 if not math.isfinite(float(rn_wm2)) else float(rn_wm2)
        if rn_wm2 < 0.0:
            rn_wm2 = 0.0
        rn_wm2 = float(round(float(rn_wm2), 0))

        return {
            "Precip_mm_day": float(prcp_mm_day),
            "Temp_C": float(temp_c),
            "RH_1": float(rh_1),
            "Wind_m_s": float(wind_ms),
            "RN_W_m2": float(rn_wm2),
        }


def _era5_rh_from_dewpoint(*, temp_c: float, dew_c: float) -> float:
    # Ratio 0-1, computed from dewpoint (Td) and temperature (T).
    #
    # es = 6.112 * exp(17.67*T /(T + 243.5))
    # ea = 6.112 * exp(17.67*Td/(Td + 243.5))
    # rh = clamp(ea/es, 0, 1)
    def esat(tc: float) -> float:
        return 6.112 * math.exp(17.67 * float(tc) / (float(tc) + 243.5))

    es = esat(temp_c)
    if not math.isfinite(float(es)) or es <= 0.0:
        return 0.0
    ea = esat(dew_c)
    if not math.isfinite(float(ea)) or ea < 0.0:
        ea = 0.0
    rh = float(ea) / float(es)
    if not math.isfinite(float(rh)):
        rh = 0.0
    rh = max(0.0, min(1.0, float(rh)))
    return rh


def _era5_netcdf_at(
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
    if product != "ERA5":
        raise ValueError(f"Only PRODUCT=ERA5 is supported here (got {product!r})")

    data_root = forcing_cfg["DATA_ROOT"]
    file_pattern = forcing_cfg["LAYOUT_FILE_PATTERN"]
    year_subdir = forcing_cfg.get("LAYOUT_YEAR_SUBDIR", "0").strip() not in ("", "0", "FALSE", "false")

    dim_time = forcing_cfg.get("NC_DIM_TIME", "time")
    dim_lat = forcing_cfg.get("NC_DIM_LAT", "latitude")
    dim_lon = forcing_cfg.get("NC_DIM_LON", "longitude")

    time_var = forcing_cfg.get("TIME_VAR", dim_time)
    lat_var = forcing_cfg.get("LAT_VAR", dim_lat)
    lon_var = forcing_cfg.get("LON_VAR", dim_lon)

    v_tp = forcing_cfg["NC_VAR_TP"]
    v_t2m = forcing_cfg["NC_VAR_T2M"]
    v_d2m = forcing_cfg["NC_VAR_D2M"]
    v_u10 = forcing_cfg["NC_VAR_U10"]
    v_v10 = forcing_cfg["NC_VAR_V10"]
    v_ssr = forcing_cfg["NC_VAR_SSR"]

    # Step-function semantics for t_min: select the last hourly record at/before t_min (with tolerance),
    # then compute accumulated-field increments using the forward-difference [i, i+1).
    forc_base = _parse_yyyymmdd(forc_start_yyyymmdd)
    target_dt = _dt_from_forc_start(forc_start_yyyymmdd, float(t_min))
    t0 = _floor_dt_to_minute_step(target_dt, 60)
    t1 = t0 + dt.timedelta(hours=1)

    def resolve(day_dt: dt.datetime) -> str:
        yyyymmdd = day_dt.strftime("%Y%m%d")
        fn = file_pattern.replace("{yyyymmdd}", yyyymmdd)
        if year_subdir:
            return os.path.join(data_root, f"{day_dt.year:04d}", fn)
        return os.path.join(data_root, fn)

    f0 = resolve(t0)
    f1 = resolve(t1)

    # Open file(s)
    with netCDF4.Dataset(f0, "r") as ds0:
        lat_arr = ds0.variables[lat_var][:]
        lon_arr = ds0.variables[lon_var][:]
        lon_min = float(lon_arr.min())
        lon_max = float(lon_arr.max())
        lon_0360 = lon_min >= 0.0 and lon_max > 180.0

        slon = float(station_lon_deg)
        if lon_0360:
            if slon < 0.0:
                slon += 360.0
            while slon >= 360.0:
                slon -= 360.0

        lat_idx = int(abs(lat_arr - float(station_lat_deg)).argmin())
        lon_idx = int(abs(lon_arr - slon).argmin())

        time_vals0 = ds0.variables[time_var][:]
        units0 = getattr(ds0.variables[time_var], "units", None)
        if not isinstance(units0, str) or not units0.strip():
            raise ValueError(f"time variable missing units: {f0}:{time_var}")
        factor_min0, base_dt0 = _parse_units_since(units0)

        def to_dt(base_dt: dt.datetime, factor_min: float, v: float) -> dt.datetime:
            return base_dt + dt.timedelta(minutes=float(v) * float(factor_min))

        # Build absolute datetimes for time axis (small; 24 per file) and find t0/t1 indices.
        t0_abs = t0
        t1_abs = t1
        tol = float(time_tol_min)
        times0 = [to_dt(base_dt0, factor_min0, float(v)) for v in time_vals0]
        if not times0:
            raise ValueError(f"empty time axis: {f0}:{time_var}")
        if any(times0[j] < times0[j - 1] for j in range(1, len(times0))):
            raise ValueError(f"non-monotonic time axis: {f0}:{time_var}")

        def idx_of(target: dt.datetime) -> int:
            # step-function: last <= target (within tolerance)
            tmins = [(tt - forc_base).total_seconds() / 60.0 for tt in times0]
            tgt_min = (target - forc_base).total_seconds() / 60.0
            first = float(tmins[0])
            last = float(tmins[-1])
            if tgt_min < first - tol:
                if clamp:
                    return 0
                raise ValueError(
                    f"t_min out of range (< first): t_min={tgt_min} first={first} tol={tol} file={f0}"
                )
            if tgt_min > last + tol:
                if clamp:
                    return len(tmins) - 1
                raise ValueError(
                    f"t_min out of range (> last): t_min={tgt_min} last={last} tol={tol} file={f0}"
                )
            i = bisect.bisect_right(tmins, float(tgt_min) + tol) - 1
            if i < 0:
                i = 0
            if i >= len(tmins):
                i = len(tmins) - 1
            return int(i)

        i0 = idx_of(t0_abs)

        # Read current-step instantaneous variables at i0
        tp0 = _read_netcdf_point(
            ds0,
            var_name=v_tp,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=i0,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        ssr0 = _read_netcdf_point(
            ds0,
            var_name=v_ssr,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=i0,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        t2m_k = _read_netcdf_point(
            ds0,
            var_name=v_t2m,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=i0,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        d2m_k = _read_netcdf_point(
            ds0,
            var_name=v_d2m,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=i0,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        u10 = _read_netcdf_point(
            ds0,
            var_name=v_u10,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=i0,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        v10 = _read_netcdf_point(
            ds0,
            var_name=v_v10,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=i0,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )

        # Read next-step accumulated vars at t1 (may cross a day boundary)
        if os.path.abspath(f1) == os.path.abspath(f0):
            i1 = i0 + 1
            if i1 >= len(times0):
                raise ValueError(f"need lookahead beyond file time axis: {f0} i0={i0} nt={len(times0)}")
            tp1 = _read_netcdf_point(
                ds0,
                var_name=v_tp,
                dim_time=dim_time,
                dim_lat=dim_lat,
                dim_lon=dim_lon,
                time_idx=i1,
                lat_idx=lat_idx,
                lon_idx=lon_idx,
            )
            ssr1 = _read_netcdf_point(
                ds0,
                var_name=v_ssr,
                dim_time=dim_time,
                dim_lat=dim_lat,
                dim_lon=dim_lon,
                time_idx=i1,
                lat_idx=lat_idx,
                lon_idx=lon_idx,
            )
            dt_sec = float((times0[i1] - times0[i0]).total_seconds())
        else:
            with netCDF4.Dataset(f1, "r") as ds1:
                time_vals1 = ds1.variables[time_var][:]
                units1 = getattr(ds1.variables[time_var], "units", None)
                if not isinstance(units1, str) or not units1.strip():
                    raise ValueError(f"time variable missing units: {f1}:{time_var}")
                factor_min1, base_dt1 = _parse_units_since(units1)
                times1 = [to_dt(base_dt1, factor_min1, float(v)) for v in time_vals1]
                if not times1:
                    raise ValueError(f"empty time axis: {f1}:{time_var}")
                i1 = 0
                tp1 = _read_netcdf_point(
                    ds1,
                    var_name=v_tp,
                    dim_time=dim_time,
                    dim_lat=dim_lat,
                    dim_lon=dim_lon,
                    time_idx=i1,
                    lat_idx=lat_idx,
                    lon_idx=lon_idx,
                )
                ssr1 = _read_netcdf_point(
                    ds1,
                    var_name=v_ssr,
                    dim_time=dim_time,
                    dim_lat=dim_lat,
                    dim_lon=dim_lon,
                    time_idx=i1,
                    lat_idx=lat_idx,
                    lon_idx=lon_idx,
                )
                dt_sec = float((times1[i1] - times0[i0]).total_seconds())

    if dt_sec <= 0.0 or not math.isfinite(float(dt_sec)):
        raise ValueError(f"invalid dt_sec for ERA5 increment: {dt_sec}")

    # Reset-tolerant forward differences for accumulated variables.
    # Mirror SHUD/src/classes/NetcdfForcingProvider.cpp (ERA5):
    # - accumulated fields can reset across stitching boundaries
    # - float quantization can create small negative deltas even when the true series is constant
    tp_diff = float(tp1) - float(tp0)
    tp_tol = max(1e-5, 1e-4 * max(abs(float(tp0)), abs(float(tp1))))  # meters
    if tp_diff >= -tp_tol:
        tp_inc_m = max(0.0, float(tp_diff))
    else:
        tp_inc_m = max(0.0, float(tp1))

    ssr_diff = float(ssr1) - float(ssr0)
    ssr_tol = max(1000.0, 1e-4 * max(abs(float(ssr0)), abs(float(ssr1))))  # J/m^2
    if ssr_diff >= -ssr_tol:
        ssr_inc_jm2 = max(0.0, float(ssr_diff))
    else:
        ssr_inc_jm2 = max(0.0, float(ssr1))

    prcp_mm_day = tp_inc_m * 1000.0 * (86400.0 / float(dt_sec))
    if not math.isfinite(float(prcp_mm_day)) or prcp_mm_day < 0.0:
        prcp_mm_day = 0.0
    prcp_mm_day = round(float(prcp_mm_day), 4)
    if prcp_mm_day < 0.0001:
        prcp_mm_day = 0.0

    temp_c = float(t2m_k) - 273.15
    if not math.isfinite(float(temp_c)):
        temp_c = 0.0
    temp_c = round(float(temp_c), 2)

    dew_c = float(d2m_k) - 273.15
    rh_1 = _era5_rh_from_dewpoint(temp_c=float(temp_c), dew_c=float(dew_c))
    rh_1 = round(float(rh_1), 4)
    rh_1 = max(0.0, min(1.0, float(rh_1)))

    wind_ms = math.sqrt(float(u10) * float(u10) + float(v10) * float(v10))
    wind_ms = 0.0 if not math.isfinite(float(wind_ms)) else float(wind_ms)
    wind_ms = round(float(wind_ms), 2)
    if wind_ms < 0.05:
        wind_ms = 0.05

    rn_wm2 = ssr_inc_jm2 / float(dt_sec)
    rn_wm2 = 0.0 if not math.isfinite(float(rn_wm2)) else float(rn_wm2)
    if rn_wm2 < 0.0:
        rn_wm2 = 0.0
    rn_wm2 = float(round(float(rn_wm2), 0))

    return {
        "Precip_mm_day": float(prcp_mm_day),
        "Temp_C": float(temp_c),
        "RH_1": float(rh_1),
        "Wind_m_s": float(wind_ms),
        "RN_W_m2": float(rn_wm2),
    }


def _gldas_precip_units_kind(units: str) -> str:
    u = units.strip().lower()
    if "kg" in u and ("m-2" in u or "m**-2" in u) and ("s-1" in u or "s**-1" in u):
        return "KG_M2_S"
    if "mm" in u and ("s-1" in u or "s**-1" in u):
        return "MM_S"
    if "mm" in u and ("day" in u or "d-1" in u or "d**-1" in u):
        return "MM_DAY"
    return "UNKNOWN"


def _gldas_netcdf_at(
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
    if product != "GLDAS":
        raise ValueError(f"Only PRODUCT=GLDAS is supported here (got {product!r})")

    data_root = forcing_cfg["DATA_ROOT"]
    file_pattern = forcing_cfg["LAYOUT_FILE_PATTERN"]

    dim_time = forcing_cfg.get("NC_DIM_TIME", "time")
    dim_lat = forcing_cfg.get("NC_DIM_LAT", "lat")
    dim_lon = forcing_cfg.get("NC_DIM_LON", "lon")

    v_prec = forcing_cfg["NC_VAR_PREC"]
    v_temp = forcing_cfg["NC_VAR_TEMP"]
    v_shum = forcing_cfg["NC_VAR_SHUM"]
    v_pres = forcing_cfg["NC_VAR_PRES"]
    v_wind = forcing_cfg["NC_VAR_WIND"]
    v_srad = forcing_cfg["NC_VAR_SRAD"]

    # GLDAS NOAH025_3H: one file per 3-hour step.
    target_dt = _dt_from_forc_start(forc_start_yyyymmdd, float(t_min))
    step_dt = _floor_dt_to_minute_step(target_dt, 180)

    rel = _format_gldas_path(file_pattern, t=step_dt)
    fn = os.path.join(data_root, rel)

    with netCDF4.Dataset(fn, "r") as ds:
        lat_arr = ds.variables[dim_lat][:]
        lon_arr = ds.variables[dim_lon][:]

        lon_min = float(lon_arr.min())
        lon_max = float(lon_arr.max())
        lon_0360 = lon_min >= 0.0 and lon_max > 180.0
        slon = float(station_lon_deg)
        if lon_0360:
            if slon < 0.0:
                slon += 360.0
            while slon >= 360.0:
                slon -= 360.0

        # Nearest grid cell, with optional remap off _FillValue cells (mirrors SHUD's GLDAS behavior).
        lat_idx0 = int(abs(lat_arr - float(station_lat_deg)).argmin())
        lon_idx0 = int(abs(lon_arr - slon).argmin())

        def is_valid(ilat: int, ilon: int) -> bool:
            try:
                _ = _read_netcdf_point(
                    ds,
                    var_name=v_temp,  # SHUD uses TEMP for GLDAS water-mask remap
                    dim_time=dim_time,
                    dim_lat=dim_lat,
                    dim_lon=dim_lon,
                    time_idx=0,
                    lat_idx=int(ilat),
                    lon_idx=int(ilon),
                )
                return True
            except Exception:
                return False

        lat_idx = lat_idx0
        lon_idx = lon_idx0
        if not is_valid(lat_idx0, lon_idx0):
            max_r = 10  # up to ~2.5 degrees in each direction for 0.25deg grids
            best_dist2 = float("inf")
            best: Optional[Tuple[int, int]] = None
            nlat = int(len(lat_arr))
            nlon = int(len(lon_arr))
            for r in range(1, max_r + 1):
                found = False
                k_lo = max(0, int(lat_idx0) - r)
                k_hi = min(nlat - 1, int(lat_idx0) + r)
                j_lo = max(0, int(lon_idx0) - r)
                j_hi = min(nlon - 1, int(lon_idx0) + r)
                for kk in range(k_lo, k_hi + 1):
                    for jj in range(j_lo, j_hi + 1):
                        if not is_valid(kk, jj):
                            continue
                        dlon = abs(float(lon_arr[jj]) - float(slon))
                        if lon_0360:
                            dlon = min(float(dlon), 360.0 - float(dlon))
                        dlat = abs(float(lat_arr[kk]) - float(station_lat_deg))
                        dist2 = float(dlon) * float(dlon) + float(dlat) * float(dlat)
                        if dist2 < best_dist2:
                            best_dist2 = dist2
                            best = (kk, jj)
                            found = True
                if found:
                    break
            if best is None:
                raise ValueError(
                    "GLDAS forcing grid cell is missing (_FillValue) for a forcing station "
                    f"(station lon={station_lon_deg} lat={station_lat_deg}; nearest idx_lat={lat_idx0} idx_lon={lon_idx0}; file={fn})."
                )
            lat_idx, lon_idx = best
        time_idx = 0

        prec_raw = _read_netcdf_point(
            ds,
            var_name=v_prec,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=time_idx,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        temp_k = _read_netcdf_point(
            ds,
            var_name=v_temp,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=time_idx,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        shum = _read_netcdf_point(
            ds,
            var_name=v_shum,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=time_idx,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        pres = _read_netcdf_point(
            ds,
            var_name=v_pres,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=time_idx,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        wind = _read_netcdf_point(
            ds,
            var_name=v_wind,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=time_idx,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )
        srad = _read_netcdf_point(
            ds,
            var_name=v_srad,
            dim_time=dim_time,
            dim_lat=dim_lat,
            dim_lon=dim_lon,
            time_idx=time_idx,
            lat_idx=lat_idx,
            lon_idx=lon_idx,
        )

        units = getattr(ds.variables[v_prec], "units", "")
        kind = _gldas_precip_units_kind(units if isinstance(units, str) else "")
        if kind in ("KG_M2_S", "MM_S"):
            prcp_mm_day = float(prec_raw) * 86400.0
        elif kind == "MM_DAY":
            prcp_mm_day = float(prec_raw)
        else:
            raise ValueError(f"unknown GLDAS precip units: {units!r}")

        if not math.isfinite(float(prcp_mm_day)) or prcp_mm_day < 0.0:
            prcp_mm_day = 0.0
        prcp_mm_day = round(float(prcp_mm_day), 4)
        if prcp_mm_day < 0.0001:
            prcp_mm_day = 0.0

        temp_c = float(temp_k) - 273.15
        if not math.isfinite(float(temp_c)):
            temp_c = 0.0
        temp_c = round(float(temp_c), 2)

        rh_percent = 0.263 * float(pres) * float(shum) / math.exp(17.67 * (float(temp_k) - 273.15) / (float(temp_k) - 29.65))
        rh_percent = max(0.0, min(100.0, float(rh_percent)))
        rh_1 = rh_percent / 100.0
        rh_1 = round(float(rh_1), 4)
        rh_1 = max(0.0, min(1.0, float(rh_1)))

        wind_ms = abs(float(wind))
        wind_ms = 0.0 if not math.isfinite(float(wind_ms)) else float(wind_ms)
        wind_ms = round(float(wind_ms), 2)
        if wind_ms < 0.05:
            wind_ms = 0.05

        rn_wm2 = float(srad)
        rn_wm2 = 0.0 if not math.isfinite(float(rn_wm2)) else float(rn_wm2)
        if rn_wm2 < 0.0:
            rn_wm2 = 0.0
        rn_wm2 = float(round(float(rn_wm2), 0))

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
    p = argparse.ArgumentParser(description="Sampled forcing compare: baseline CSV vs NetCDF (CMFD2/ERA5/GLDAS)")
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

    forcing_cfg_path = os.path.join(nc_run, "input", prj, f"{prj}.cfg.forcing")

    forcing_cfg = _read_kv_cfg(forcing_cfg_path)
    # DATA_ROOT is rendered relative to run_dir; resolve here for tool usage.
    if not os.path.isabs(forcing_cfg.get("DATA_ROOT", "")):
        forcing_cfg["DATA_ROOT"] = os.path.normpath(os.path.join(nc_run, forcing_cfg["DATA_ROOT"]))

    samples: List[Dict[str, Any]] = []

    for sidx in stations_idx:
        st = tsd.stations[sidx]
        csv_path = _resolve_station_csv_path(baseline_run, tsd.rel_path, st.filename)
        for tmin in times_min:
            base_vals = _read_station_csv_at(csv_path, tmin)
            base_map = {
                "Precip_mm_day": base_vals[0],
                "Temp_C": base_vals[1],
                "RH_1": base_vals[2],
                "Wind_m_s": base_vals[3],
                "RN_W_m2": base_vals[4],
            }
            product = forcing_cfg.get("PRODUCT", "").upper()
            if product == "CMFD2":
                nc_map = _cmfd2_netcdf_at(
                    forcing_cfg=forcing_cfg,
                    forc_start_yyyymmdd=forc_start,
                    station_lon_deg=st.lon_deg,
                    station_lat_deg=st.lat_deg,
                    t_min=tmin,
                    clamp=bool(args.clamp),
                    time_tol_min=float(args.time_tol_min),
                )
            elif product == "ERA5":
                nc_map = _era5_netcdf_at(
                    forcing_cfg=forcing_cfg,
                    forc_start_yyyymmdd=forc_start,
                    station_lon_deg=st.lon_deg,
                    station_lat_deg=st.lat_deg,
                    t_min=tmin,
                    clamp=bool(args.clamp),
                    time_tol_min=float(args.time_tol_min),
                )
            elif product == "GLDAS":
                nc_map = _gldas_netcdf_at(
                    forcing_cfg=forcing_cfg,
                    forc_start_yyyymmdd=forc_start,
                    station_lon_deg=st.lon_deg,
                    station_lat_deg=st.lat_deg,
                    t_min=tmin,
                    clamp=bool(args.clamp),
                    time_tol_min=float(args.time_tol_min),
                )
            else:
                raise ValueError(f"Unsupported PRODUCT in cfg.forcing: {product!r} ({forcing_cfg_path})")
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
