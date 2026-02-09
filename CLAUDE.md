# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SHUD-NC is a **meta-repo** orchestrating the SHUD hydrological solver and its toolchain. It manages three git submodules and coordinates a two-phase NetCDF migration:

- **Phase A (Forcing)**: SHUD reads raw forcing NetCDF directly (CMFD2/ERA5), bypassing CSV
- **Phase B (Output)**: SHUD writes CF/UGRID-compliant NetCDF output
- **Baseline preservation**: Original AutoSHUD→SHUD (CSV forcing + legacy output) must always work

## Repository Structure

```
SHUD-NC/                    # Parent meta-repo (this repo)
├── SHUD/                   # Submodule: C++14 solver (SUNDIALS/CVODE)
│   └── src/{classes,Model,ModelData,Equations}/
├── AutoSHUD/               # Submodule: R pipeline (Step1–Step5)
├── rSHUD/                  # Submodule: R package (GIS/NetCDF utilities)
├── tools/                  # Python meta-runner + comparison scripts
├── projects/<case>/        # Per-case YAML config (single entry point)
├── configs/{forcing,output}/ # Reusable adapter configs
├── openspec/               # Spec-driven development (proposals, specs, changes)
├── testdata/               # Small sample data for CI/tests (committed)
├── Data/                   # Large external data (NOT committed)
└── runs/                   # Generated outputs (NOT committed)
```

## Build & Run Commands

### SHUD solver (C++)

```bash
cd SHUD
./configure                          # Install SUNDIALS/CVODE to ~/sundials
make clean && make shud              # Standard build
make shud NETCDF=1                   # Build with NetCDF support
make shud_omp                        # Build with OpenMP
./shud <project_name>                # Run (e.g., ./shud ccw)
```

Prerequisites: SUNDIALS/CVODE 6.x (`~/sundials`), optionally netcdf-c (for `NETCDF=1`), OpenMP.

### Meta-runner (Python)

```bash
python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile baseline
python3 tools/shudnc.py projects/qhh/shud.yaml run --profile baseline
python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile nc
```

Dependencies: `pip install pyyaml` (core), `pip install netCDF4 numpy` (comparison tools).

### Comparison / validation

```bash
# Forcing comparison (CSV vs NetCDF)
python3 tools/compare_forcing.py --baseline-run runs/qhh/baseline --nc-run runs/qhh/nc --prj qhh --stations 0,1,2 --t-min 0,180 --out-json runs/qhh/compare/forcing.json

# TSR validation (in SHUD/)
bash validation/tsr/run_tsr.sh
python3 validation/tsr/py/compare_tsr.py output/ccw.tsr --tol 1e-10
python3 -m unittest discover -s validation/tsr/py -p 'test_*.py'
python3 -m coverage run -m unittest discover -s validation/tsr/py -p 'test_*.py' && python3 -m coverage report --fail-under=90
```

### CI

CI runs on every PR and push to `main`:
- `openspec validate --all --strict --no-interactive` (spec validation)
- Python syntax check on `tools/*.py`

## Architecture: Key Patterns

### Forcing abstraction (`SHUD/src/classes/ForcingProvider.hpp`)
Abstract base class with `CsvForcingProvider` (baseline) and `NetcdfForcingProvider` (Phase A). Contract: 5 variables — Precip(mm/day), Temp(°C), RH(0–1), Wind(m/s), RN(W/m²). Step-function semantics via `movePointer(t_min)` / `get(station, column)`.

### Output sink pattern (`SHUD/src/Equations/print.cpp`)
`Print_Ctrl` buffer/interval semantics extended with a "sink" mechanism for NetCDF output. Legacy output remains untouched; NetCDF is an additional channel.

### Configuration layering
- User entry point: `projects/<case>/shud.yaml` (YAML, parent repo only)
- SHUD-side config: `.cfg` KEY VALUE files (no YAML in SHUD — avoids dependency)
- `render-shud-cfg` in `tools/shudnc.py` bridges YAML → `.cfg`

## Submodule Workflow

Code lives in personal forks; parent repo only tracks gitlink SHAs:
- `SHUD/` → `DankerMu/SHUD-up` (fork), upstream `SHUD-System/SHUD`
- `AutoSHUD/` → `DankerMu/AutoSHUD`
- `rSHUD/` → `DankerMu/rSHUD`

After submodule changes: `git add SHUD AutoSHUD rSHUD && git commit -m "Update submodule refs"`

Branch naming: `feat/<topic>` (submodules), `codex/<topic>` (parent repo).

## Critical Constraints

1. **Never break baseline**: default behavior = CSV forcing + legacy output
2. **No YAML in SHUD**: new SHUD config uses `.cfg` KEY VALUE only
3. **Fail-fast on bad data**: missing coverage, wrong units, FillValue → clear error with file/var/time/station
4. **Interpolation default**: NEAREST (regression consistency first)
5. **Submodule hygiene**: don't `git add SHUD/` as a directory; it's managed by `.gitmodules`

## OpenSpec (Spec-Driven Development)

This repo uses OpenSpec for planning changes. Key commands:
```bash
openspec list                          # Active changes
openspec list --specs                  # Current specifications
openspec validate <change-id> --strict # Validate before PR
openspec archive <change-id> --yes     # After deployment
```

Specs live in `openspec/specs/<capability>/spec.md`. Change proposals go in `openspec/changes/<id>/`. See `openspec/AGENTS.md` for full workflow.

## Domain Notes

- SHUD internal time axis: minutes relative to `ForcStartTime (YYYYMMDD)` in `<prj>.tsd.forc`
- NetCDF output target: CF/UGRID, time axis = left endpoint (consistent with `Print_Ctrl`)
- AutoSHUD pipeline: Step0 (delineation) → Step1 (raw data) → Step2 (subset) → Step3 (build model) → Step4 (run SHUD) → Step5 (visualization)
