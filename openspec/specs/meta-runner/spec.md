# Spec: Meta-Runner (`tools/shudnc.py`)

## Purpose
定义父仓库编排层（meta-runner）的行为：以 `projects/<case>/shud.yaml` 为单入口，串联 AutoSHUD 与 SHUD，支撑 baseline 与后续 nc profile。

## Requirements

### Requirement: Single entry config
The system SHALL treat `projects/<case>/shud.yaml` as the canonical entry point and support selecting a `profile` under `profiles.<name>`.

#### Scenario: Profile selection
- **GIVEN** a `profiles.baseline` entry
- **WHEN** user runs `python3 tools/shudnc.py ... --profile baseline`
- **THEN** the runner uses that profile's `run_dir` and settings

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

