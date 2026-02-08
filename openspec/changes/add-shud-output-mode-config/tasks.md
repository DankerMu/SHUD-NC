## Implementation
- [ ] Add fields to store output mode and ncoutput cfg path
- [ ] Extend `.cfg.para` parser to read `OUTPUT_MODE` and `NCOUTPUT_CFG`
- [ ] Fail-fast validation when NETCDF is enabled but cfg missing
- [ ] Keep default behavior unchanged (LEGACY)

## Validation
- [ ] Build: `make shud`
- [ ] Baseline short run without new keys
- [ ] Error case: `OUTPUT_MODE NETCDF` missing `NCOUTPUT_CFG`

