## ADDED Requirements

### Requirement: Forcing mode switch (`FORCING_MODE`)
SHUD SHALL support selecting forcing source via `<prj>.cfg.para`:
- default: `FORCING_MODE=CSV`
- allowed values: `CSV` or `NETCDF` (case-insensitive)

#### Scenario: Default remains CSV
- **GIVEN** `<prj>.cfg.para` does not define `FORCING_MODE`
- **WHEN** SHUD loads the project
- **THEN** forcing is read using the baseline CSV workflow

### Requirement: NetCDF forcing requires `FORCING_CFG`
When `FORCING_MODE=NETCDF`, SHUD SHALL require `FORCING_CFG <path>` to exist and be readable.

#### Scenario: Missing forcing cfg fails fast
- **GIVEN** `FORCING_MODE=NETCDF` and `FORCING_CFG` is missing
- **WHEN** SHUD loads the project
- **THEN** SHUD exits with a clear error mentioning `FORCING_CFG` and the input directory

