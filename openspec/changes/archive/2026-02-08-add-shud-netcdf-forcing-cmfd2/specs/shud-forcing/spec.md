## ADDED Requirements

### Requirement: CMFD2 NetCDF forcing (NEAREST)
When `FORCING_MODE=NETCDF` and product is `CMFD2`, SHUD SHALL read CMFD2 NetCDF forcing and provide the 5 forcing variables using NEAREST sampling.

#### Scenario: Station maps to nearest grid point
- **GIVEN** a station lon/lat from `<prj>.tsd.forc`
- **WHEN** the provider initializes
- **THEN** it selects the nearest `(grid_lon, grid_lat)` indices and logs the mapping for the first N stations

### Requirement: Unit conversion matches SHUD contract
The provider SHALL convert CMFD2 variables to SHUD forcing contract units (mm/day, °C, 0–1, m/s, W/m²).

#### Scenario: Precip units auto-detected or explicitly configured
- **GIVEN** precipitation units are detectable from NetCDF metadata
- **WHEN** the provider converts precipitation
- **THEN** it produces mm/day consistent with the detected units, otherwise fails fast requesting an explicit override

### Requirement: NetCDF dimension order MUST be resolved by name
The provider MUST resolve variable dimension order using NetCDF dimension names (`time`, `lat`, `lon`) and MUST NOT assume a fixed order (e.g. `(lon,lat,time)` vs `(time,lat,lon)`).

#### Scenario: Dataset uses a different dimension order
- **GIVEN** a CMFD2 NetCDF variable whose dimensions are not in `(time,lat,lon)` order
- **WHEN** the provider reads a station time series via NEAREST sampling
- **THEN** it maps indices by dimension name and returns correct values aligned to the `time` axis
