## Implementation
- [ ] Update Makefile to accept `NETCDF=1` (default 0)
- [ ] When enabled, resolve flags from `nc-config` or `pkg-config netcdf`
- [ ] Add `-D_NETCDF_ON` (or similar) compile define for conditional compilation
- [ ] Keep existing OpenMP/SUNDIALS behavior unchanged

## Validation
- [ ] `make clean && make shud`
- [ ] `make clean && make shud NETCDF=1` (if NetCDF installed)

