## ADDED Requirements

### Requirement: Optional NetCDF support build flag
The SHUD build system SHALL support enabling NetCDF support behind an explicit build flag (e.g., `NETCDF=1`) and keep it disabled by default.

#### Scenario: Default build does not require NetCDF
- **GIVEN** NetCDF is not installed
- **WHEN** user runs `make shud`
- **THEN** the build succeeds and NetCDF support remains disabled

#### Scenario: NetCDF-enabled build links NetCDF
- **GIVEN** NetCDF is installed and discoverable via `nc-config` or `pkg-config`
- **WHEN** user runs `make shud NETCDF=1`
- **THEN** the build links against `libnetcdf` and enables NetCDF support

