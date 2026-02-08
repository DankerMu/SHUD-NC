## ADDED Requirements

### Requirement: NetCDF output core produces readable dataset
When `OUTPUT_MODE` includes NetCDF, SHUD SHALL produce a NetCDF file that can be opened by common tools (xarray/netCDF4) with a valid `time` axis.

#### Scenario: xarray can open element dataset
- **GIVEN** a successful SHUD run with NetCDF output enabled
- **WHEN** user opens `<prefix>.ele.nc` with xarray
- **THEN** the dataset contains an unlimited `time` dimension and at least one data variable

