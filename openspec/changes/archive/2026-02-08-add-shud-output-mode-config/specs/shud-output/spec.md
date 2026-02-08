## ADDED Requirements

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

