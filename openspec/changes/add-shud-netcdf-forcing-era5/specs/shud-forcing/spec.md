## ADDED Requirements

### Requirement: ERA5 accumulated variables are converted to interval values
For ERA5 NetCDF forcing, accumulated variables (e.g., `tp`, `ssr`) SHALL be converted to interval increments for `[time[k], time[k+1])` and then expressed in SHUD contract units.

#### Scenario: Reset handling
- **GIVEN** an accumulated series that resets (A[k+1] < A[k])
- **WHEN** computing interval increment
- **THEN** the provider uses `inc = A[k+1]` for that interval

### Requirement: NetCDF dimension order MUST be resolved by name
The provider MUST resolve variable dimension order using NetCDF dimension names (`time`, `latitude`, `longitude`) and MUST NOT assume a fixed order.

#### Scenario: Variable dimensions are ordered differently
- **GIVEN** an ERA5 NetCDF variable whose dimensions are not in `(time,lat,lon)` order
- **WHEN** the provider reads a station time series
- **THEN** it maps indices by dimension name and returns values aligned to the `time` axis
