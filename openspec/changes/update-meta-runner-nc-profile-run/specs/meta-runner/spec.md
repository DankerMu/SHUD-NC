## MODIFIED Requirements

### Requirement: Single entry config
The runner SHALL support profiles that do not require forcing CSV generation (e.g., NetCDF forcing mode), while still running AutoSHUD static-input steps when configured.

#### Scenario: `profiles.nc` without `autoshud.forcing`
- **GIVEN** a profile with `shud.forcing_mode=netcdf`
- **WHEN** validating/running the profile
- **THEN** the runner does not require `autoshud.forcing.*` keys and instead validates NetCDF forcing inputs

