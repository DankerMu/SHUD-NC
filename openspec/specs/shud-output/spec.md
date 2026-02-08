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
For each output interval `Interval` (minutes), SHUD legacy output time stamps SHALL use:
- `t_quantized = floor(t) - Interval`

#### Scenario: Interval output aligns to boundaries
- **GIVEN** `Interval=60` minutes
- **WHEN** the solver reaches `t≈60` (within numerical tolerance)
- **THEN** SHUD writes one record with `t_quantized≈0`

### Requirement: Column selection via `cfg.output`
When an output selection file is present, SHUD SHALL only write selected columns and record their indices (`icol`) in the binary header.

#### Scenario: Disabled columns are excluded from legacy output
- **GIVEN** an element output selection file that disables some elements
- **WHEN** SHUD writes legacy outputs
- **THEN** the written column count equals the number of enabled indices

