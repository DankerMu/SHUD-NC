## Implementation
- [x] Make `tools/shudnc.py` tolerant of missing `profiles.<name>.autoshud.*` (provide sensible defaults)
- [x] Extend validation to handle `profiles.<name>.shud.forcing` for NetCDF mode
- [x] Implement `run --profile nc` sequence:
  - [x] AutoSHUD steps (static inputs)
  - [x] render SHUD cfg overlays + patch `.cfg.para`
  - [x] run SHUD binary

## Validation
- [x] `python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile nc`
- [x] `python3 tools/shudnc.py projects/qhh/shud.yaml run --profile nc --dry-run`

