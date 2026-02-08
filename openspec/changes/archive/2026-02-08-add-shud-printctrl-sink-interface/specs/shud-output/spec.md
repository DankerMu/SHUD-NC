## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Sink receives full-dimension metadata (`n_all` + `icol[]`)
When a print sink is enabled, `Print_Ctrl` SHALL provide:
- `n_all`: the full object dimension size (e.g., NumEle/NumRiv/NumLake)
- `icol[]`: the legacy selection indices (1-based) for enabled columns

This enables sinks (e.g., NetCDF) to write full-dimension outputs with `_FillValue` for disabled columns while preserving legacy selection semantics.

#### Scenario: Partial selection can be reconstructed
- **GIVEN** `cfg.output` disables some columns for legacy output
- **WHEN** the sink is initialized
- **THEN** it receives `n_all` and `icol[]` sufficient to reconstruct a full-length array with fill values
