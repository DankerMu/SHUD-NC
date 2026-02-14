# Spec: SHUD Forcing

## Purpose
定义 SHUD 对 “气象 forcing” 的输入契约与时间推进语义，作为 baseline 回归与 NetCDF forcing 改造的共同基线。
## Requirements
### Requirement: Forcing station list file (`<prj>.tsd.forc`)
SHUD SHALL read a forcing station list file `input/<prj>/<prj>.tsd.forc` to determine:
- `NumForc` (number of forcing stations)
- `ForcStartTime` (YYYYMMDD, base date for SHUD internal time axis)
- per-station metadata: `Lon/Lat/X/Y/Z` and a station data reference (CSV filename in baseline)

#### Scenario: Parse a valid `<prj>.tsd.forc`
- **GIVEN** `<prj>.tsd.forc` has header `<NumForc> <ForcStartTime>` and `NumForc > 0`
- **WHEN** SHUD loads the project
- **THEN** SHUD sets `ForcStartTime` as the base date and allocates exactly `NumForc` stations

#### Scenario: Invalid header fails fast
- **GIVEN** `<prj>.tsd.forc` first line cannot be parsed as `<NumForc> <ForcStartTime>`
- **WHEN** SHUD loads the project
- **THEN** SHUD SHALL exit with a clear error mentioning the file and expected format

### Requirement: Forcing variable contract (5 variables)
For each forcing station and each model time, SHUD SHALL obtain exactly 5 forcing variables (Nforc=5) with the following units *before SHUD internal conversions*:
- `Precip`: **mm/day**
- `Temp`: **°C**
- `RH`: **0–1**
- `Wind`: **m/s**
- `RN`: **W/m²**

#### Scenario: Values out of expected range are warned
- **GIVEN** forcing values are loaded for a station
- **WHEN** values are outside reasonable physical ranges (e.g., Temp < -70°C or RH > 1)
- **THEN** SHUD SHOULD warn (range-check), helping detect unit mistakes

### Requirement: Time semantics (step function)
Forcing in SHUD SHALL behave as a **step function** over forcing time intervals, independent of forcing source.

#### Scenario: Provider swap does not change behavior
- **GIVEN** the baseline CSV forcing source
- **WHEN** forcing is accessed through a provider abstraction
- **THEN** values and `currentTimeMin/nextTimeMin` semantics remain unchanged

### Requirement: Coverage must include the simulation period
For each forcing station, the forcing time coverage SHALL fully cover the simulation interval `[START, END]` (in SHUD minutes).

#### Scenario: Insufficient coverage fails fast
- **GIVEN** simulation END is beyond forcing max time
- **WHEN** SHUD validates time stamps
- **THEN** SHUD SHALL exit with an error showing both simulation interval and forcing coverage interval

### Requirement: Solar lon/lat selection must be valid
When terrain solar radiation (TSR) is enabled, SHUD SHALL select a valid global `(lon, lat)` for solar geometry based on forcing stations and `SOLAR_LONLAT_MODE`.

#### Scenario: Selected lon/lat is validated
- **GIVEN** `SOLAR_LONLAT_MODE` selects a lon/lat
- **WHEN** SHUD initializes forcing
- **THEN** it SHALL validate lon ∈ [-180, 180] and lat ∈ [-90, 90] and fail fast otherwise

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

### Requirement: ERA5 accumulated variables are converted to interval values
For ERA5 NetCDF forcing, accumulated variables (e.g., `tp`, `ssr`) SHALL be converted to interval increments for `[time[k], time[k+1])` and then expressed in SHUD contract units.

#### Scenario: Reset handling
- **GIVEN** an accumulated series that resets (A[k+1] < A[k])
- **WHEN** computing interval increment
- **THEN** the provider uses `inc = A[k+1]` for that interval

#### Scenario: Forward-difference requires lookahead
- **GIVEN** simulation END is an exclusive bound and does not include forcing at `t == END`
- **WHEN** computing accumulated-field increments via forward difference for the last simulated forcing interval
- **THEN** the provider SHALL ensure forcing availability at the first forcing time boundary `>= END` (for reading A[k+1])

### Requirement: GLDAS NetCDF forcing (NEAREST)
When `FORCING_MODE=NETCDF` and product is `GLDAS`, SHUD SHALL read GLDAS (e.g., NOAH 0.25° 3-hourly) NetCDF forcing stored as **one file per time step**, and provide the 5 forcing variables using NEAREST sampling with SHUD contract units.

Dataset-to-contract mapping:
- Precip (mm/day): `Rainf_f_tavg` (kg/m²/s) → `val * 86400`
- Temp (°C): `Tair_f_inst` (K) → `val - 273.15`
- RH (0–1): derived from `Qair_f_inst` (kg/kg), `Psurf_f_inst` (Pa), `Tair_f_inst` (K) using the same SHum→RH formula as CMFD2
- Wind (m/s): `Wind_f_inst`
- RN (W/m²): `SWdown_f_tavg`

#### Scenario: Per-timestep files are enumerated without directory scan
- **GIVEN** forcing files are stored under `{year}/{doy}/...` and there is exactly one file per forcing timestep
- **WHEN** the provider initializes for a simulation interval
- **THEN** it enumerates the required files by constructing expected paths from the time range, without scanning directories

#### Scenario: Missing water-mask grid cells are handled
- **GIVEN** the nearest grid cell for a station is `_FillValue` (e.g., over lakes)
- **WHEN** the provider initializes station-to-grid mapping
- **THEN** it remaps to the nearest valid grid cell within a limited search radius, otherwise fails fast with a clear error
