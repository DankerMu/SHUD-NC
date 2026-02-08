#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


class ConfigError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"Config not found: {path}") from exc
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ConfigError(f"YAML root must be a mapping: {path}")
    return data


def _get(obj: Dict[str, Any], dotted: str, *, required: bool = True) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            if required:
                raise ConfigError(f"Missing config key: {dotted}")
            return None
        cur = cur[part]
    return cur


def _as_int(value: Any, *, key: str) -> int:
    try:
        return int(value)
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"Expected integer for {key}, got: {value!r}") from exc


def _as_float(value: Any, *, key: str) -> float:
    try:
        return float(value)
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"Expected number for {key}, got: {value!r}") from exc


def _as_str(value: Any, *, key: str) -> str:
    if value is None:
        raise ConfigError(f"Missing required config value: {key}")
    if isinstance(value, str):
        s = value.strip()
    else:
        s = str(value).strip()
    if not s:
        raise ConfigError(f"Empty string for config value: {key}")
    return s


def _resolve_path(repo_root: Path, path_value: str) -> Path:
    p = Path(path_value)
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def _to_posix(path_str: str) -> str:
    return path_str.replace("\\", "/")


def _relpath(from_dir: Path, to_path: Path) -> str:
    try:
        rel = os.path.relpath(to_path, start=from_dir)
        return _to_posix(rel)
    except ValueError:
        # Windows: different drive letters etc. Fall back to absolute path.
        return _to_posix(str(to_path))


@dataclass(frozen=True)
class AutoShudConfig:
    prjname: str
    start_year: int
    end_year: int
    dir_out: Path
    forcing_code: float
    forcing_dir_ldas: Path
    forcing_csv_dir: Path
    soil_code: float
    soil_dir: Path
    landuse_code: float
    landuse_file: Path
    wbd: Path
    stm: Path
    dem: Path
    crs_ref: Optional[Path]
    lake: Optional[Path]
    params: Dict[str, Any]

    def render(self, *, repo_root: Path, autoshud_dir: Path) -> str:
        def rel(p: Path) -> str:
            return _relpath(autoshud_dir, p)

        lines: List[Tuple[str, str]] = []

        lines.append(("prjname", self.prjname))
        lines.append(("startyear", str(self.start_year)))
        lines.append(("endyear", str(self.end_year)))
        lines.append(("dir.out", rel(self.dir_out)))

        crs_path = self.crs_ref or self.wbd
        lines.append(("fsp.crs", rel(crs_path)))
        lines.append(("fsp.wbd", rel(self.wbd)))
        lines.append(("fsp.stm", rel(self.stm)))
        lines.append(("fr.dem", rel(self.dem)))
        if self.lake is not None:
            lines.append(("fsp.lake", rel(self.lake)))

        lines.append(("Forcing", str(self.forcing_code)))
        lines.append(("dir.ldas", rel(self.forcing_dir_ldas)))
        lines.append(("dout.forc", rel(self.forcing_csv_dir)))

        lines.append(("Soil", str(self.soil_code)))
        if self.soil_code < 1:
            lines.append(("dir.soil", rel(self.soil_dir)))
        else:
            raise ConfigError("Local soil mode (Soil >= 1) is not implemented in shudnc.py yet.")

        lines.append(("Landuse", str(self.landuse_code)))
        if self.landuse_code < 1:
            lines.append(("fn.landuse", rel(self.landuse_file)))
        else:
            raise ConfigError("Local landuse mode (Landuse >= 1) is not implemented in shudnc.py yet.")

        # Parameters: follow AutoSHUD key names
        def add_param(key: str, value: Any) -> None:
            if value is None:
                return
            lines.append((key, str(value)))

        add_param("NumCells", self.params.get("NumCells"))
        add_param("AqDepth", self.params.get("AqDepth"))
        add_param("MaxArea", self.params.get("MaxArea_km2"))
        add_param("MinAngle", self.params.get("MinAngle"))
        add_param("tol.wb", self.params.get("tol_wb"))
        add_param("tol.rivlen", self.params.get("tol_rivlen"))
        add_param("RivWidth", self.params.get("RivWidth"))
        add_param("RivDepth", self.params.get("RivDepth"))
        add_param("DistBuffer", self.params.get("DistBuffer_m"))
        add_param("flowpath", self.params.get("flowpath"))
        add_param("QuickMode", self.params.get("QuickMode"))
        add_param("MAX_SOLVER_STEP", self.params.get("MAX_SOLVER_STEP"))
        add_param("CRYOSPHERE", self.params.get("CRYOSPHERE"))
        add_param("STARTDAY", self.params.get("STARTDAY"))
        add_param("ENDDAY", self.params.get("ENDDAY"))

        header = [
            "# Auto-generated by tools/shudnc.py",
            "# NOTE: Relative paths are relative to AutoSHUD/ (the working directory).",
            "",
        ]
        body = [f"{k} {v}" for (k, v) in lines]
        return "\n".join(header + body + [""])


def _autoshud_config_from_yaml(
    cfg: Dict[str, Any],
    *,
    repo_root: Path,
    profile: str,
) -> AutoShudConfig:
    prjname = _get(cfg, "project.name")
    start_year = _as_int(_get(cfg, "time.start_year"), key="time.start_year")
    end_year = _as_int(_get(cfg, "time.end_year"), key="time.end_year")

    profile_cfg = _get(cfg, f"profiles.{profile}")
    run_dir = _resolve_path(repo_root, _as_str(_get(profile_cfg, "run_dir"), key=f"profiles.{profile}.run_dir"))

    auto_cfg = _get(profile_cfg, "autoshud", required=False)
    baseline_auto_cfg = _get(cfg, "profiles.baseline.autoshud", required=False)
    if auto_cfg is None:
        if baseline_auto_cfg is None:
            raise ConfigError(
                f"Missing profiles.{profile}.autoshud and no profiles.baseline.autoshud fallback is available."
            )
        auto_cfg = baseline_auto_cfg

    forcing_cfg = _get(auto_cfg, "forcing", required=False) or {}
    forcing_code_val = forcing_cfg.get("code")
    if forcing_code_val is None and isinstance(baseline_auto_cfg, dict):
        forcing_code_val = _get(baseline_auto_cfg, "forcing.code", required=False)
    forcing_code = _as_float(forcing_code_val, key=f"profiles.{profile}.autoshud.forcing.code")

    forcing_dir_val = forcing_cfg.get("dir_ldas")
    # For NetCDF profile, prefer using the SHUD forcing `dir` if provided.
    shud_cfg = _get(profile_cfg, "shud", required=False) or {}
    forcing_mode = str(shud_cfg.get("forcing_mode", "csv")).strip().lower()
    shud_forcing_cfg = _get(shud_cfg, "forcing", required=False) or {}
    if forcing_mode == "netcdf" and isinstance(shud_forcing_cfg, dict) and isinstance(shud_forcing_cfg.get("dir"), str):
        forcing_dir_val = shud_forcing_cfg.get("dir")
    if forcing_dir_val is None and isinstance(baseline_auto_cfg, dict):
        forcing_dir_val = _get(baseline_auto_cfg, "forcing.dir_ldas", required=False)
    if forcing_dir_val is None:
        raise ConfigError(
            "Missing forcing directory for AutoSHUD config. Provide either:\n"
            f"- profiles.{profile}.autoshud.forcing.dir_ldas\n"
            f"- (NetCDF forcing) profiles.{profile}.shud.forcing.dir\n"
            "- or profiles.baseline.autoshud.forcing.dir_ldas for fallback"
        )
    forcing_dir = _resolve_path(
        repo_root,
        _as_str(
            forcing_dir_val,
            key=f"profiles.{profile}.autoshud.forcing.dir_ldas (or profiles.{profile}.shud.forcing.dir when forcing_mode=netcdf)",
        ),
    )

    forcing_csv_dir_val = forcing_cfg.get("csv_dir")
    if forcing_csv_dir_val is None and _get(profile_cfg, "autoshud", required=False) is None:
        forcing_csv_dir_val = str(run_dir / "forcing")
    if forcing_csv_dir_val is None and isinstance(baseline_auto_cfg, dict):
        forcing_csv_dir_val = _get(baseline_auto_cfg, "forcing.csv_dir", required=False)
    if forcing_csv_dir_val is None:
        raise ConfigError(
            "Missing forcing csv_dir for AutoSHUD config. Provide either:\n"
            f"- profiles.{profile}.autoshud.forcing.csv_dir\n"
            "- or profiles.baseline.autoshud.forcing.csv_dir for fallback"
        )
    forcing_csv_dir = _resolve_path(
        repo_root, _as_str(forcing_csv_dir_val, key=f"profiles.{profile}.autoshud.forcing.csv_dir")
    )

    soil_cfg = _get(cfg, "datasets.soil")
    soil_code = _as_float(_get(soil_cfg, "code"), key="datasets.soil.code")
    soil_dir = _resolve_path(repo_root, _as_str(_get(soil_cfg, "dir"), key="datasets.soil.dir"))

    landuse_cfg = _get(cfg, "datasets.landuse")
    landuse_code = _as_float(_get(landuse_cfg, "code"), key="datasets.landuse.code")
    landuse_file = _resolve_path(repo_root, _as_str(_get(landuse_cfg, "file"), key="datasets.landuse.file"))

    spatial_cfg = _get(cfg, "spatial")
    wbd = _resolve_path(repo_root, _as_str(_get(spatial_cfg, "wbd"), key="spatial.wbd"))
    stm = _resolve_path(repo_root, _as_str(_get(spatial_cfg, "stm"), key="spatial.stm"))
    dem = _resolve_path(repo_root, _as_str(_get(spatial_cfg, "dem"), key="spatial.dem"))
    crs_ref_val = _get(spatial_cfg, "crs_ref", required=False)
    crs_ref = _resolve_path(repo_root, crs_ref_val) if isinstance(crs_ref_val, str) else None
    lake_val = _get(spatial_cfg, "lake", required=False)
    lake = _resolve_path(repo_root, lake_val) if isinstance(lake_val, str) else None

    params = dict(_get(cfg, "autoshud.parameters", required=False) or {})
    # Explicitly bind days to project time unless overridden
    params.setdefault("STARTDAY", _as_int(_get(cfg, "time.start_day"), key="time.start_day"))
    params.setdefault("ENDDAY", _as_int(_get(cfg, "time.end_day"), key="time.end_day"))

    return AutoShudConfig(
        prjname=str(prjname),
        start_year=start_year,
        end_year=end_year,
        dir_out=run_dir,
        forcing_code=forcing_code,
        forcing_dir_ldas=forcing_dir,
        forcing_csv_dir=forcing_csv_dir,
        soil_code=soil_code,
        soil_dir=soil_dir,
        landuse_code=landuse_code,
        landuse_file=landuse_file,
        wbd=wbd,
        stm=stm,
        dem=dem,
        crs_ref=crs_ref,
        lake=lake if (lake is not None and lake.exists()) else None,
        params=params,
    )


def _run(cmd: List[str], *, cwd: Path, dry_run: bool) -> None:
    cmd_str = " ".join(cmd)
    print(f"$ (cd {cwd} && {cmd_str})")
    if dry_run:
        return
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _run_shud(
    *,
    shud_bin: Path,
    prjname: str,
    run_dir: Path,
    dry_run: bool,
) -> None:
    if not shud_bin.exists():
        raise ConfigError(f"SHUD binary not found: {shud_bin}")
    if not os.access(shud_bin, os.X_OK):
        raise ConfigError(f"SHUD binary not executable: {shud_bin}")

    logs_dir = run_dir / "logs"
    log_file = logs_dir / f"shud_{prjname}.log"

    print(f"$ (cd {run_dir} && {shud_bin} {prjname} | tee {log_file})")
    if dry_run:
        return

    logs_dir.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(
            [str(shud_bin), prjname],
            cwd=str(run_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            f.write(line)
        rc = proc.wait()
        if rc != 0:
            raise ConfigError(f"SHUD exited with code {rc}. See log: {log_file}")


def _validate(cfg: Dict[str, Any], *, repo_root: Path, profile: str) -> None:
    # Minimal validation: resolve paths and check key inputs exist.
    auto = _autoshud_config_from_yaml(cfg, repo_root=repo_root, profile=profile)
    profile_cfg = _get(cfg, f"profiles.{profile}")
    shud_cfg = _get(profile_cfg, "shud", required=False) or {}
    forcing_mode = str(shud_cfg.get("forcing_mode", "csv")).strip().lower()
    output_mode = str(shud_cfg.get("output_mode", "legacy")).strip().lower()

    missing: List[Path] = []
    for p in [auto.wbd, auto.stm, auto.dem]:
        if not p.exists():
            missing.append(p)
    if auto.lake is not None and not auto.lake.exists():
        missing.append(auto.lake)
    if auto.soil_code < 1:
        if not auto.soil_dir.exists():
            missing.append(auto.soil_dir)
        # Known dataset checks (avoid over-validating unknown products).
        if auto.soil_code == 0.1:
            for p in [auto.soil_dir / "hwsd.bil", auto.soil_dir / "hwsd.dbf"]:
                if not p.exists():
                    missing.append(p)
    if auto.landuse_code < 1:
        if not auto.landuse_file.exists():
            missing.append(auto.landuse_file)

    # AutoSHUD forcing inputs: keep strict checks for baseline CSV mode,
    # but avoid assuming CMFD directory layout when SHUD forcing is NetCDF.
    if not auto.forcing_dir_ldas.exists():
        missing.append(auto.forcing_dir_ldas)
    elif forcing_mode != "netcdf" and auto.forcing_code == 0.5:
        for var_dir in ["Prec", "Temp", "SHum", "SRad", "Wind", "Pres"]:
            p = auto.forcing_dir_ldas / var_dir
            if not p.exists():
                missing.append(p)

    # NetCDF forcing config checks (profile.shud.forcing)
    if forcing_mode == "netcdf":
        forcing_cfg = _get(shud_cfg, "forcing")
        data_root = _resolve_path(repo_root, _get(forcing_cfg, "dir"))
        adapter_path = _resolve_path(repo_root, _get(forcing_cfg, "adapter"))
        if not data_root.exists():
            missing.append(data_root)
        if not adapter_path.exists():
            missing.append(adapter_path)
        else:
            adapter = _load_yaml(adapter_path)
            layout = adapter.get("layout")
            if not (isinstance(layout, dict) and isinstance(layout.get("file_pattern"), str)):
                raise ConfigError(f"Invalid adapter YAML (missing layout.file_pattern): {adapter_path}")

    # NetCDF output config checks (profile.shud.output)
    if output_mode in ("netcdf", "both"):
        output_cfg = _get(shud_cfg, "output")
        schema_path = _resolve_path(repo_root, _get(output_cfg, "schema"))
        if not schema_path.exists():
            missing.append(schema_path)

    if missing:
        msg = "\n".join([f"- {p}" for p in missing])
        raise ConfigError(f"Missing required files/dirs:\n{msg}")


def _format_kv_cfg(*, header: List[str], kv: List[Tuple[str, str]]) -> str:
    lines: List[str] = []
    lines.extend([f"# {h}" if h else "" for h in header])
    for k, v in kv:
        lines.append(f"{k} {v}")
    return "\n".join(lines + [""])


def _normalize_enum(value: Any, *, key: str) -> str:
    if value is None:
        raise ConfigError(f"Missing config key: {key}")
    if not isinstance(value, str):
        raise ConfigError(f"Expected string for {key}, got: {value!r}")
    return value.strip().lower()


def _flatten_adapter_cfg(adapter: Dict[str, Any]) -> List[Tuple[str, str]]:
    # Render a minimal subset of adapter YAML into a KEY VALUE cfg that can be
    # parsed by SHUD without YAML support.
    kv: List[Tuple[str, str]] = []

    layout = adapter.get("layout") or {}
    if isinstance(layout, dict):
        year_subdir = layout.get("year_subdir")
        if isinstance(year_subdir, bool):
            kv.append(("LAYOUT_YEAR_SUBDIR", "1" if year_subdir else "0"))
        file_pattern = layout.get("file_pattern")
        if isinstance(file_pattern, str):
            kv.append(("LAYOUT_FILE_PATTERN", file_pattern))
        variables_dir = layout.get("variables_dir")
        if isinstance(variables_dir, dict):
            for k, v in sorted(variables_dir.items()):
                if isinstance(k, str) and isinstance(v, str):
                    kv.append((f"LAYOUT_VAR_DIR_{k.upper()}", v))

    netcdf = adapter.get("netcdf") or {}
    if isinstance(netcdf, dict):
        dims = netcdf.get("dims")
        if isinstance(dims, dict):
            for k, v in sorted(dims.items()):
                if isinstance(k, str) and isinstance(v, str):
                    kv.append((f"NC_DIM_{k.upper()}", v))
        var_names = netcdf.get("var_names")
        if isinstance(var_names, dict):
            for k, v in sorted(var_names.items()):
                if isinstance(k, str) and isinstance(v, str):
                    kv.append((f"NC_VAR_{k.upper()}", v))

    conversion = adapter.get("conversion") or {}
    if isinstance(conversion, dict):
        rn = conversion.get("rn") or {}
        if isinstance(rn, dict):
            radiation_kind = rn.get("radiation_kind")
            if isinstance(radiation_kind, str):
                kv.append(("RADIATION_KIND", radiation_kind))

    return kv


def _render_shud_forcing_cfg(
    cfg: Dict[str, Any],
    *,
    repo_root: Path,
    profile: str,
    run_dir: Path,
) -> Tuple[Optional[Path], Optional[str]]:
    profile_cfg = _get(cfg, f"profiles.{profile}")
    shud_cfg = _get(profile_cfg, "shud", required=False) or {}
    forcing_mode = _normalize_enum(shud_cfg.get("forcing_mode", "csv"), key=f"profiles.{profile}.shud.forcing_mode")
    if forcing_mode != "netcdf":
        return None, None

    forcing_cfg = _get(shud_cfg, "forcing")
    product = _normalize_enum(_get(forcing_cfg, "product"), key=f"profiles.{profile}.shud.forcing.product")
    data_root = _resolve_path(repo_root, _get(forcing_cfg, "dir"))
    adapter_path = _resolve_path(repo_root, _get(forcing_cfg, "adapter"))

    adapter = _load_yaml(adapter_path)
    kv: List[Tuple[str, str]] = []
    kv.append(("PRODUCT", product.upper()))
    kv.append(("DATA_ROOT", _relpath(run_dir, data_root)))
    kv.extend(_flatten_adapter_cfg(adapter))

    prjname = str(_get(cfg, "project.name"))
    out_path = run_dir / "input" / prjname / f"{prjname}.cfg.forcing"
    header = [
        "Auto-generated by tools/shudnc.py (render-shud-cfg)",
        f"Profile: {profile}",
        f"Adapter: {_relpath(run_dir, adapter_path)}",
        "",
        "KEY VALUE format; do not edit manually.",
    ]
    return out_path, _format_kv_cfg(header=header, kv=kv)


def _render_shud_ncoutput_cfg(
    cfg: Dict[str, Any],
    *,
    repo_root: Path,
    profile: str,
    run_dir: Path,
) -> Tuple[Optional[Path], Optional[str]]:
    profile_cfg = _get(cfg, f"profiles.{profile}")
    shud_cfg = _get(profile_cfg, "shud", required=False) or {}
    output_mode = _normalize_enum(shud_cfg.get("output_mode", "legacy"), key=f"profiles.{profile}.shud.output_mode")
    if output_mode not in ("netcdf", "both"):
        return None, None

    # Placeholder: stage B will define the full schema/keys. For now, capture
    # only basic wiring and keep format KEY VALUE.
    output_cfg = _get(shud_cfg, "output", required=False) or {}
    schema_path_val = output_cfg.get("schema")
    out_dir_val = output_cfg.get("dir")

    kv: List[Tuple[str, str]] = []
    if isinstance(schema_path_val, str):
        schema_path = _resolve_path(repo_root, schema_path_val)
        kv.append(("SCHEMA", _relpath(run_dir, schema_path)))
    if isinstance(out_dir_val, str):
        out_dir = _resolve_path(repo_root, out_dir_val)
        kv.append(("OUT_DIR", _relpath(run_dir, out_dir)))

    prjname = str(_get(cfg, "project.name"))
    out_path = run_dir / "input" / prjname / f"{prjname}.cfg.ncoutput"
    header = [
        "Auto-generated by tools/shudnc.py (render-shud-cfg)",
        f"Profile: {profile}",
        "",
        "KEY VALUE format; placeholder for stage B.",
    ]
    return out_path, _format_kv_cfg(header=header, kv=kv)


def _patch_kv_cfg_file(path: Path, *, updates: Dict[str, str], dry_run: bool) -> None:
    if dry_run:
        print(f"# would patch: {path}")
        for k, v in updates.items():
            print(f"#   set: {k} {v}")
        return

    if not path.exists():
        raise ConfigError(
            f"SHUD cfg.para not found for patching: {path}\n"
            "Hint: run AutoSHUD Step3 to generate SHUD inputs first, or point run_dir to an existing run."
        )

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    out_lines: List[str] = []

    # Replace keys and remove duplicates for idempotency.
    desired = {k.upper(): v for k, v in updates.items()}
    seen: set[str] = set()

    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue

        parts = stripped.split(None, 1)
        key = parts[0].upper()
        if key not in desired:
            out_lines.append(line)
            continue

        if key in seen:
            # Drop duplicate occurrences.
            continue

        out_lines.append(f"{key} {desired[key]}")
        seen.add(key)

    remaining = {k: v for k, v in desired.items() if k not in seen}
    if remaining:
        out_lines.append("")
        out_lines.append("# Added by tools/shudnc.py (render-shud-cfg)")
        for k, v in sorted(remaining.items()):
            out_lines.append(f"{k} {v}")

    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def _render_shud_cfg_overlays(cfg: Dict[str, Any], *, repo_root: Path, profile: str, run_dir: Path, dry_run: bool) -> None:
    prjname = str(_get(cfg, "project.name"))
    input_dir = run_dir / "input" / prjname

    forcing_path, forcing_text = _render_shud_forcing_cfg(cfg, repo_root=repo_root, profile=profile, run_dir=run_dir)
    ncoutput_path, ncoutput_text = _render_shud_ncoutput_cfg(cfg, repo_root=repo_root, profile=profile, run_dir=run_dir)

    profile_cfg = _get(cfg, f"profiles.{profile}")
    shud_cfg = _get(profile_cfg, "shud", required=False) or {}
    forcing_mode = _normalize_enum(shud_cfg.get("forcing_mode", "csv"), key=f"profiles.{profile}.shud.forcing_mode")
    output_mode = _normalize_enum(shud_cfg.get("output_mode", "legacy"), key=f"profiles.{profile}.shud.output_mode")

    para_updates: Dict[str, str] = {"FORCING_MODE": forcing_mode.upper(), "OUTPUT_MODE": output_mode.upper()}
    if forcing_mode == "netcdf":
        para_updates["FORCING_CFG"] = f"{prjname}.cfg.forcing"
    if output_mode in ("netcdf", "both"):
        para_updates["NCOUTPUT_CFG"] = f"{prjname}.cfg.ncoutput"

    if not dry_run:
        input_dir.mkdir(parents=True, exist_ok=True)

    if forcing_path is not None and forcing_text is not None:
        if dry_run:
            print(f"# would write: {forcing_path}")
        else:
            forcing_path.write_text(forcing_text, encoding="utf-8")
            print(f"Wrote: {forcing_path}")

    if ncoutput_path is not None and ncoutput_text is not None:
        if dry_run:
            print(f"# would write: {ncoutput_path}")
        else:
            ncoutput_path.write_text(ncoutput_text, encoding="utf-8")
            print(f"Wrote: {ncoutput_path}")

    para_path = input_dir / f"{prjname}.cfg.para"
    _patch_kv_cfg_file(para_path, updates=para_updates, dry_run=dry_run)
    if not dry_run:
        print(f"Patched: {para_path}")


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="SHUD-NC meta runner (shud.yaml as single entry)")
    parser.add_argument("config", help="Path to projects/<case>/shud.yaml (relative to repo root or absolute)")
    parser.add_argument(
        "command",
        choices=["validate", "render-autoshud", "render-shud-cfg", "autoshud", "run"],
        help="Action to perform",
    )
    parser.add_argument("--profile", default="baseline", help="Profile under profiles/<name> (default: baseline)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")

    args = parser.parse_args(argv)

    repo_root = _repo_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve()

    cfg = _load_yaml(config_path)

    profile = args.profile
    if _get(cfg, f"profiles.{profile}", required=False) is None:
        raise ConfigError(f"Profile not found: {profile}")

    autoshud_dir = _resolve_path(repo_root, _get(cfg, "paths.autoshud_dir", required=False) or "AutoSHUD")
    shud_bin = _resolve_path(repo_root, _get(cfg, "paths.shud_bin", required=False) or "SHUD/shud")

    prjname = _get(cfg, "project.name")
    profile_cfg = _get(cfg, f"profiles.{profile}")
    run_dir = _resolve_path(repo_root, _get(profile_cfg, "run_dir"))

    if args.command == "validate":
        _validate(cfg, repo_root=repo_root, profile=profile)
        print("OK")
        return 0

    if args.command == "render-shud-cfg":
        _render_shud_cfg_overlays(cfg, repo_root=repo_root, profile=profile, run_dir=run_dir, dry_run=args.dry_run)
        return 0

    auto = _autoshud_config_from_yaml(cfg, repo_root=repo_root, profile=profile)
    autoshud_text = auto.render(repo_root=repo_root, autoshud_dir=autoshud_dir)

    if args.command == "render-autoshud":
        sys.stdout.write(autoshud_text)
        return 0

    # Write generated AutoSHUD config into the run directory (ignored by git).
    gen_dir = run_dir / "config"
    gen_file = gen_dir / "autoshud.generated.txt"
    if not args.dry_run:
        gen_dir.mkdir(parents=True, exist_ok=True)
        gen_file.write_text(autoshud_text, encoding="utf-8")
    else:
        print(f"# would write: {gen_file}")

    if args.command in ("autoshud", "run"):
        steps = _get(profile_cfg, "autoshud.steps", required=False) or [1, 2, 3]
        step_map = {1: "Step1_RawDataProcessng.R", 2: "Step2_DataSubset.R", 3: "Step3_BuidModel.R"}
        for step in steps:
            step_i = _as_int(step, key=f"profiles.{profile}.autoshud.steps[]")
            script = step_map.get(step_i)
            if script is None:
                raise ConfigError(f"Unsupported AutoSHUD step: {step_i}")
            _run(["Rscript", script, str(gen_file)], cwd=autoshud_dir, dry_run=args.dry_run)

    if args.command == "run":
        # For NetCDF profile, render SHUD cfg overlays after AutoSHUD Step3 has
        # generated the base SHUD inputs under run_dir/input/<prj>/.
        shud_cfg = _get(profile_cfg, "shud", required=False) or {}
        forcing_mode = str(shud_cfg.get("forcing_mode", "csv")).strip().lower()
        output_mode = str(shud_cfg.get("output_mode", "legacy")).strip().lower()
        if forcing_mode == "netcdf" or output_mode in ("netcdf", "both"):
            _render_shud_cfg_overlays(
                cfg,
                repo_root=repo_root,
                profile=profile,
                run_dir=run_dir,
                dry_run=args.dry_run,
            )

        shud_cfg = _get(profile_cfg, "shud", required=False) or {}
        if bool(shud_cfg.get("run", False)):
            _run_shud(shud_bin=shud_bin, prjname=str(prjname), run_dir=run_dir, dry_run=args.dry_run)
        else:
            print("# SHUD run disabled for this profile (profiles.<name>.shud.run=false)")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
