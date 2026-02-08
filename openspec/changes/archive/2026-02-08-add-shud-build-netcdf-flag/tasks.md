## Implementation
- [x] Update Makefile to accept `NETCDF=1` (default 0)
- [x] When enabled, resolve flags from `nc-config` or `pkg-config netcdf`
- [x] Add `-D_NETCDF_ON` (or similar) compile define for conditional compilation
- [x] Keep existing OpenMP/SUNDIALS behavior unchanged

## Validation
- [x] `make clean && make shud`
- [x] `make clean && make shud NETCDF=1` (if NetCDF installed)

