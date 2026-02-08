## Implementation
- [ ] Implement CMFD2 NetCDF reader with:
  - [ ] coordinate discovery (time/lat/lon)
  - [ ] lon normalization (0..360 vs -180..180)
  - [ ] NEAREST index precompute per station
  - [ ] time units parse → `t_min[]` and monotonic validation
  - [ ] scale_factor/add_offset and _FillValue handling
  - [ ] per-variable conversion to SHUD forcing contract
  - [ ] monthly file switching and caching
- [ ] Add clear error messages (file/var/time/station_idx/lon/lat)

## Validation
- [ ] Build: `make shud NETCDF=1`
- [ ] Run short simulation in NETCDF forcing mode (CMFD2)
- [ ] Compare sampled forcing values vs baseline CSV

