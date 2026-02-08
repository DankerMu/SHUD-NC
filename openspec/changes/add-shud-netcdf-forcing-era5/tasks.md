## Implementation
- [ ] Implement ERA5 file discovery (daily pattern, optional year subdir)
- [ ] Handle `latitude` decreasing coordinate
- [ ] Convert accumulated variables:
  - [ ] `tp` (m accumulated) → mm/day rate per interval
  - [ ] `ssr` (J/m2 accumulated) → W/m2 per interval
- [ ] RH from dewpoint + temperature (ratio 0–1)
- [ ] Map ERA5 `ssr` to `RADIATION_INPUT_MODE=SWNET` expectations (documented)

## Validation
- [ ] Build: `make shud NETCDF=1`
- [ ] Run short simulation (ERA5)
- [ ] Compare sampled forcing values against baseline/expectations

