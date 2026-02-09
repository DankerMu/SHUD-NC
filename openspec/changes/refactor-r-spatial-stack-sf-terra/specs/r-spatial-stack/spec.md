## ADDED Requirements
### Requirement: Modern R spatial stack (sf/terra)
The project SHALL use `sf` for vector GIS operations and `terra` for raster operations in the baseline AutoSHUD pipeline and in the `rSHUD` toolbox.

#### Scenario: Fresh environment can install required R packages
- **GIVEN** a machine with system dependencies installed (GDAL/GEOS/PROJ)
- **WHEN** the user installs the project’s required R packages
- **THEN** installation succeeds without requiring `sp/raster/rgdal/rgeos/proj4`

### Requirement: No hard dependency on deprecated spatial packages
`rSHUD` and the AutoSHUD scripts SHALL NOT have hard dependencies on `sp`, `raster`, `rgdal`, `rgeos`, or `proj4` (e.g., in `Imports`, `Depends`, or `LinkingTo`).

#### Scenario: `rSHUD` installs in a clean library
- **GIVEN** an empty R library path
- **WHEN** the user installs `rSHUD` from the submodule
- **THEN** the install completes without installing the deprecated packages

### Requirement: Provide project-local R env install & check tooling
The meta-repo SHALL provide scripts to:
- install required R dependencies into a project-local library
- validate that the local environment is complete (fail-fast on missing deps)

#### Scenario: Environment check lists missing deps
- **GIVEN** required packages are not installed
- **WHEN** user runs the environment check script
- **THEN** it exits non-zero and prints a concise list of missing packages

### Requirement: Baseline pipeline remains runnable
The baseline workflow (AutoSHUD Step1–Step3 + optional SHUD run) SHALL remain runnable after the migration to `sf/terra`.

#### Scenario: QHH baseline runs via meta-runner
- **GIVEN** `projects/qhh/shud.yaml` is configured and required data exists under `Data/`
- **WHEN** user runs `python3 tools/shudnc.py projects/qhh/shud.yaml run --profile baseline`
- **THEN** AutoSHUD completes Step1–Step3 and produces SHUD static inputs under the run directory

