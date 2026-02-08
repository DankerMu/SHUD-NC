## Implementation
- [x] Add fields to store output mode and ncoutput cfg path
- [x] Extend `.cfg.para` parser to read `OUTPUT_MODE` and `NCOUTPUT_CFG`
- [x] Fail-fast validation when NETCDF is enabled but cfg missing
- [x] Keep default behavior unchanged (LEGACY)

## Validation
- [x] Build: `make shud`
- [x] Baseline short run without new keys
- [x] Error case: `OUTPUT_MODE NETCDF` missing `NCOUTPUT_CFG`

