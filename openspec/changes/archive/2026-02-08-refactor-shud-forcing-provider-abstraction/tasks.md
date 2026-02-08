## Implementation
- [x] Create `ForcingProvider` interface (header-only or minimal .cpp)
- [x] Implement `CsvForcingProvider` using existing `tsd_weather[]`
- [x] Wire `Model_Data` to use provider for:
  - [x] `updateAllTimeSeries(t_min)`
  - [x] `tReadForcing(t, i)`
- [x] Keep station metadata (lon/lat/z) available for TSR and temperature elevation correction

## Validation
- [x] Build: `make shud`
- [x] Run baseline short simulation and compare legacy outputs against pre-refactor results

