## Implementation
- [x] Implement CMFD2 NetCDF reader with:
  - [x] coordinate discovery (time/lat/lon)
  - [x] lon normalization (0..360 vs -180..180)
  - [x] NEAREST index precompute per station
  - [x] time units parse → `t_min[]` and monotonic validation
  - [x] scale_factor/add_offset and _FillValue handling
  - [x] per-variable conversion to SHUD forcing contract
  - [x] monthly file switching and caching
- [x] Add clear error messages (file/var/time/station_idx/lon/lat)

## Validation
- [x] Build: `make shud NETCDF=1`
- [x] Run short simulation in NETCDF forcing mode (CMFD2)
- [x] Compare sampled forcing values vs baseline CSV

