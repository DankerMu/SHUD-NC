## Implementation
- [x] Add CLI command `render-shud-cfg` to `tools/shudnc.py`
- [x] Implement rendering for:
  - [x] forcing cfg (`<prj>.cfg.forcing`) based on `profiles.<name>.shud.forcing`
  - [x] ncoutput cfg placeholder (stage B; allow rendering to be a no-op for now)
- [x] Implement `.cfg.para` patching (append/update keys idempotently)
- [x] Ensure paths are resolved consistently relative to repo root and run/input dirs

## Validation
- [x] `python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile baseline --dry-run`
- [x] `python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile nc --dry-run`

