## Implementation
- [x] Implement ERA5 file discovery (daily pattern, optional year subdir)
- [x] Handle `latitude` decreasing coordinate
- [x] Convert accumulated variables:
  - [x] `tp` (m accumulated) → mm/day rate per interval
  - [x] `ssr` (J/m2 accumulated) → W/m2 per interval
- [x] RH from dewpoint + temperature (ratio 0–1)
- [x] Map ERA5 `ssr` to `RADIATION_INPUT_MODE=SWNET` expectations (documented)

## Validation
- [x] Build: `make shud NETCDF=1`
- [x] Run short simulation (ERA5)
- [x] Compare sampled forcing values against baseline/expectations

