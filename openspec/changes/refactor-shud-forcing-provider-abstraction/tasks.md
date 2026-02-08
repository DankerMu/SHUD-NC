## Implementation
- [ ] Create `ForcingProvider` interface (header-only or minimal .cpp)
- [ ] Implement `CsvForcingProvider` using existing `tsd_weather[]`
- [ ] Wire `Model_Data` to use provider for:
  - [ ] `updateAllTimeSeries(t_min)`
  - [ ] `tReadForcing(t, i)`
- [ ] Keep station metadata (lon/lat/z) available for TSR and temperature elevation correction

## Validation
- [ ] Build: `make shud`
- [ ] Run baseline short simulation and compare legacy outputs against pre-refactor results

