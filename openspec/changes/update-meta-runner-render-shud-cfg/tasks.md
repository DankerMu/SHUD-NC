## Implementation
- [ ] Add CLI command `render-shud-cfg` to `tools/shudnc.py`
- [ ] Implement rendering for:
  - [ ] forcing cfg (`<prj>.cfg.forcing`) based on `profiles.<name>.shud.forcing`
  - [ ] ncoutput cfg placeholder (stage B; allow rendering to be a no-op for now)
- [ ] Implement `.cfg.para` patching (append/update keys idempotently)
- [ ] Ensure paths are resolved consistently relative to repo root and run/input dirs

## Validation
- [ ] `python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile baseline --dry-run`
- [ ] `python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile nc --dry-run`

