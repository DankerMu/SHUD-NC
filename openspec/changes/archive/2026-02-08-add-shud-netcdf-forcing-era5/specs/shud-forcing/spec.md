## ADDED Requirements

### Requirement: ERA5 accumulated variables are converted to interval values
For ERA5 NetCDF forcing, accumulated variables (e.g., `tp`, `ssr`) SHALL be converted to interval increments for `[time[k], time[k+1])` and then expressed in SHUD contract units.

#### Scenario: Reset handling
- **GIVEN** an accumulated series that resets (A[k+1] < A[k])
- **WHEN** computing interval increment
- **THEN** the provider uses `inc = A[k+1]` for that interval
