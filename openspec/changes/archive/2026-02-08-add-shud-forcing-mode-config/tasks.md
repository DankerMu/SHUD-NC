## Implementation
- [x] Add fields to `Control_Data` to store forcing mode and forcing cfg path
- [x] Extend `.cfg.para` parser to read `FORCING_MODE` and `FORCING_CFG`
- [x] Implement fail-fast validation when `FORCING_MODE=NETCDF` but `FORCING_CFG` is missing/unreadable
- [x] Keep default behavior unchanged (CSV)

## Validation
- [x] Build: `make shud` (or equivalent)
- [x] Run a short baseline simulation (no new keys) and confirm no behavior change
- [x] Run with `FORCING_MODE NETCDF` and missing `FORCING_CFG` and confirm clear error

