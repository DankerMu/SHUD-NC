## Implementation
- [ ] Implement `NetcdfPrintSink` with:
  - [ ] file creation and global attributes
  - [ ] `time` unlimited dimension + variable
  - [ ] append on each sink write
  - [ ] 1 element variable end-to-end
- [ ] Parse minimal keys from `NCOUTPUT_CFG` (dir/prefix/format)

## Validation
- [ ] Build: `make shud NETCDF=1`
- [ ] Run short simulation with `OUTPUT_MODE=BOTH`
- [ ] Verify `xarray.open_dataset("<prefix>.ele.nc")` works and time aligns to legacy

