# Spec: SHUD Output (Legacy)

## Purpose
定义 SHUD 当前 legacy 输出行为（CSV/Binary）与 time 轴语义，作为 NetCDF 输出改造的回归基线。
## Requirements
### Requirement: Output formats are controlled by `.cfg.para`
SHUD SHALL enable legacy output formats via:
- `ASCII_OUTPUT` (0/1)
- `BINARY_OUTPUT` (0/1)

#### Scenario: Binary-only output
- **GIVEN** `BINARY_OUTPUT=1` and `ASCII_OUTPUT=0`
- **WHEN** SHUD runs
- **THEN** it produces `*.dat` legacy outputs and no `*.csv` outputs

### Requirement: Time stamp semantics are "left endpoint"
For each output interval `Interval` (minutes), the system SHALL use:
- `t_quantized = floor(t) - Interval`

This `t_quantized` value SHALL be consistently exposed to all output sinks (legacy and NetCDF).

#### Scenario: Interval output aligns to boundaries
- **GIVEN** `Interval=60` minutes
- **WHEN** the solver reaches `t≈60` (within numerical tolerance)
- **THEN** the system writes one record with `t_quantized≈0`

#### Scenario: NetCDF sink receives legacy-aligned time
- **GIVEN** legacy output interval is `Interval`
- **WHEN** a sink is invoked for an output record
- **THEN** the sink receives `t_quantized = floor(t) - Interval`

### Requirement: Column selection via `cfg.output`
When an output selection file is present, SHUD SHALL only write selected columns and record their indices (`icol`) in the binary header.

#### Scenario: Disabled columns are excluded from legacy output
- **GIVEN** an element output selection file that disables some elements
- **WHEN** SHUD writes legacy outputs
- **THEN** the written column count equals the number of enabled indices

### Requirement: Output mode switch (`OUTPUT_MODE`)
SHUD SHALL support selecting output sinks via `<prj>.cfg.para`:
- default: `OUTPUT_MODE=LEGACY`
- allowed values: `LEGACY`, `NETCDF`, `BOTH` (case-insensitive)

#### Scenario: Default remains legacy
- **GIVEN** `<prj>.cfg.para` does not define `OUTPUT_MODE`
- **WHEN** SHUD runs
- **THEN** legacy outputs are produced as before

### Requirement: NetCDF output requires `NCOUTPUT_CFG`
When `OUTPUT_MODE` includes NetCDF, SHUD SHALL require `NCOUTPUT_CFG <path>` to exist and be readable.

#### Scenario: Missing ncoutput cfg fails fast
- **GIVEN** `OUTPUT_MODE=NETCDF` and `NCOUTPUT_CFG` is missing
- **WHEN** SHUD loads the project
- **THEN** SHUD exits with a clear error mentioning `NCOUTPUT_CFG`

### Requirement: NetCDF output core produces readable dataset
When `OUTPUT_MODE` includes NetCDF, SHUD SHALL produce a NetCDF file that can be opened by common tools (xarray/netCDF4) with a valid `time` axis.

#### Scenario: xarray can open element dataset
- **GIVEN** a successful SHUD run with NetCDF output enabled
- **WHEN** user opens `<prefix>.ele.nc` with xarray
- **THEN** the dataset contains an unlimited `time` dimension and at least one data variable

### Requirement: Element NetCDF includes UGRID mesh topology
The element NetCDF file SHALL include UGRID mesh topology and connectivity variables so that element variables can be associated with the mesh.

#### Scenario: Mesh topology variable exists
- **GIVEN** NetCDF output enabled
- **WHEN** `<prefix>.ele.nc` is produced
- **THEN** it contains a mesh topology variable with `cf_role="mesh_topology"` and face connectivity with `start_index=1`

### Requirement: Split NetCDF outputs by object type
The system SHALL write NetCDF outputs into three files: element, river, and lake, each with its own object dimension and shared `time` semantics.

#### Scenario: River file exists when rivers are present
- **GIVEN** `NumRiv > 0` and NetCDF output enabled
- **WHEN** SHUD finishes
- **THEN** `<prefix>.riv.nc` exists and contains a `river` dimension and `time` dimension

### Requirement: Variable routing is based on full-dimension size
When writing NetCDF outputs, the system SHALL route each `Print_Ctrl` stream to the correct file (element/river/lake) based on the **full-dimension size** (`n_all == NumEle/NumRiv/NumLake`), and SHALL NOT rely solely on variable name prefixes.

#### Scenario: Element variables without `ele` prefix are routed correctly
- **GIVEN** an element-dimension output stream whose variable name does not start with `ele` (e.g., `rn_h`)
- **WHEN** NetCDF output routing is performed
- **THEN** it is written to the element NetCDF file based on `n_all == NumEle`

### Requirement: Full-dimension NetCDF variables with fill values
NetCDF output variables SHALL use full object dimensions (NumEle/NumRiv/NumLake). When a column is disabled in legacy selection, the NetCDF variable SHALL contain `_FillValue` at that index.

#### Scenario: Disabled element column is filled
- **GIVEN** an element is disabled in `cfg.output`
- **WHEN** NetCDF output is written
- **THEN** the corresponding element index contains `_FillValue` and the mask is 0

### Requirement: Sink receives full-dimension metadata (`n_all` + `icol[]`)
When a print sink is enabled, `Print_Ctrl` SHALL provide:
- `n_all`: the full object dimension size (e.g., NumEle/NumRiv/NumLake)
- `icol[]`: the legacy selection indices (1-based) for enabled columns

This enables sinks (e.g., NetCDF) to write full-dimension outputs with `_FillValue` for disabled columns while preserving legacy selection semantics.

#### Scenario: Partial selection can be reconstructed
- **GIVEN** `cfg.output` disables some columns for legacy output
- **WHEN** the sink is initialized
- **THEN** it receives `n_all` and `icol[]` sufficient to reconstruct a full-length array with fill values

