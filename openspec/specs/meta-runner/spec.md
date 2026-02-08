# Spec: Meta-Runner (`tools/shudnc.py`)

## Purpose
定义父仓库编排层（meta-runner）的行为：以 `projects/<case>/shud.yaml` 为单入口，串联 AutoSHUD 与 SHUD，支撑 baseline 与后续 nc profile。
## Requirements
### Requirement: Single entry config
The runner SHALL support profiles that do not require forcing CSV generation (e.g., NetCDF forcing mode), while still running AutoSHUD static-input steps when configured.

#### Scenario: `profiles.nc` without `autoshud.forcing`
- **GIVEN** a profile with `shud.forcing_mode=netcdf`
- **WHEN** validating/running the profile
- **THEN** the runner does not require `autoshud.forcing.*` keys and instead validates NetCDF forcing inputs

### Requirement: Render AutoSHUD config into `runs/.../config/`
The runner SHALL generate an AutoSHUD `*.autoshud.txt` file into `<run_dir>/config/` and run the requested AutoSHUD steps in `AutoSHUD/`.

#### Scenario: Dry-run prints commands only
- **GIVEN** `--dry-run`
- **WHEN** the runner is invoked
- **THEN** it prints commands but does not execute them or write files

### Requirement: Validate required inputs
The runner SHALL validate required inputs (paths and known datasets) for the selected profile and fail fast with a list of missing files/dirs.

#### Scenario: Missing soil dataset fails validation
- **GIVEN** the configured HWSD directory is missing
- **WHEN** user runs `validate`
- **THEN** the runner exits non-zero and prints missing paths

### Requirement: Render SHUD cfg overlays
The meta-runner SHALL be able to render SHUD `.cfg` overlay files from `projects/<case>/shud.yaml` without requiring SHUD to parse YAML.

#### Scenario: Render-only command
- **GIVEN** a valid `projects/<case>/shud.yaml`
- **WHEN** user runs `render-shud-cfg`
- **THEN** the runner writes generated cfg files under the selected `run_dir` and prints their locations

### Requirement: Adapter YAML is runner-only (single source of truth)
The meta-runner SHALL treat any adapter YAML referenced by `projects/<case>/shud.yaml` (e.g. `configs/forcing/*.yaml`, `configs/output/*.yaml`) as **runner-only templates** and SHALL render the effective SHUD configuration into KEY VALUE `.cfg` files (e.g. `<prj>.cfg.forcing`, `<prj>.cfg.ncoutput`).

SHUD SHALL only consume the rendered `.cfg` files at runtime and SHALL NOT be required to read YAML, preventing “two sources of truth”.

#### Scenario: YAML adapters are rendered into `.cfg`
- **GIVEN** `projects/<case>/shud.yaml` references an adapter YAML
- **WHEN** the meta-runner renders SHUD cfg overlays
- **THEN** it writes KEY VALUE `.cfg` files and does not require SHUD to read the adapter YAML directly

### Requirement: Provide regression compare tooling
The project SHALL provide tooling to compare baseline vs NetCDF forcing/output runs for regression verification.

#### Scenario: Sampled comparison produces a diff summary
- **GIVEN** two run directories (baseline and nc)
- **WHEN** user runs the compare tool
- **THEN** it prints a summary including max/mean diffs and sample points

