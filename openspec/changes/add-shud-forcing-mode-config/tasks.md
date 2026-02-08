## Implementation
- [ ] Add fields to `Control_Data` to store forcing mode and forcing cfg path
- [ ] Extend `.cfg.para` parser to read `FORCING_MODE` and `FORCING_CFG`
- [ ] Implement fail-fast validation when `FORCING_MODE=NETCDF` but `FORCING_CFG` is missing/unreadable
- [ ] Keep default behavior unchanged (CSV)

## Validation
- [ ] Build: `make shud` (or equivalent)
- [ ] Run a short baseline simulation (no new keys) and confirm no behavior change
- [ ] Run with `FORCING_MODE NETCDF` and missing `FORCING_CFG` and confirm clear error

