## Implementation
- [x] Implement `NetcdfPrintSink` with:
  - [x] file creation and global attributes
  - [x] `time` unlimited dimension + variable
  - [x] append on each sink write
  - [x] 1 element variable end-to-end
- [x] Parse minimal keys from `NCOUTPUT_CFG` (dir/prefix/format)

## Validation
- [x] Build: `make shud NETCDF=1`
- [x] Run short simulation with `OUTPUT_MODE=BOTH`
- [x] Verify `xarray.open_dataset("<prefix>.ele.nc")` works and time aligns to legacy

