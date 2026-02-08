## MODIFIED Requirements

### Requirement: Time stamp semantics are "left endpoint"
The system SHALL expose the same `t_quantized` and interval-mean semantics to all output sinks (legacy and NetCDF).

#### Scenario: NetCDF sink receives legacy-aligned time
- **GIVEN** legacy output interval is `Interval`
- **WHEN** a sink is invoked for an output record
- **THEN** the sink receives `t_quantized = floor(t) - Interval`

### Requirement: Sink receives full-dimension metadata (`n_all` + `icol[]`)
When a print sink is enabled, `Print_Ctrl` SHALL provide:
- `n_all`: the full object dimension size (e.g., NumEle/NumRiv/NumLake)
- `icol[]`: the legacy selection indices (1-based) for enabled columns

This enables sinks (e.g., NetCDF) to write full-dimension outputs with `_FillValue` for disabled columns while preserving legacy selection semantics.

#### Scenario: Partial selection can be reconstructed
- **GIVEN** `cfg.output` disables some columns for legacy output
- **WHEN** the sink is initialized
- **THEN** it receives `n_all` and `icol[]` sufficient to reconstruct a full-length array with fill values
