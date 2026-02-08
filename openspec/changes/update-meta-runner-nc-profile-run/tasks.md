## Implementation
- [ ] Make `tools/shudnc.py` tolerant of missing `profiles.<name>.autoshud.*` (provide sensible defaults)
- [ ] Extend validation to handle `profiles.<name>.shud.forcing` for NetCDF mode
- [ ] Implement `run --profile nc` sequence:
  - [ ] AutoSHUD steps (static inputs)
  - [ ] render SHUD cfg overlays + patch `.cfg.para`
  - [ ] run SHUD binary

## Validation
- [ ] `python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile nc`
- [ ] `python3 tools/shudnc.py projects/qhh/shud.yaml run --profile nc --dry-run`

