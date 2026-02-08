## ADDED Requirements

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
