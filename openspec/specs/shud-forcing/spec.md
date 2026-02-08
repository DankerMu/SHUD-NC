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
Forcing in SHUD SHALL behave as a **step function** over forcing time intervals:
- within a forcing interval `[t0, t1)`, `get()` returns a constant value
- the forcing source SHALL expose `currentTimeMin()` and `nextTimeMin()` for the active interval

#### Scenario: `movePointer(t)` advances in time order
- **GIVEN** a forcing time series with monotonic non-decreasing time stamps
- **WHEN** the model advances to `t` (minutes)
- **THEN** the forcing pointer advances only when `t >= nextTimeMin()`

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

