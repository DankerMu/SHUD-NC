# Change: Enable `nc` profile end-to-end in meta-runner

## Why
当前 `projects/qhh/shud.yaml` 已有 `profiles.nc`，但 `tools/shudnc.py` 仍按 baseline 假设读取 `profiles.<name>.autoshud.*`，导致 `validate/run --profile nc` 无法工作。该 change 使 nc profile 具备 **可验证、可 dry-run、可执行** 的端到端路径。

## Scope
- **Repo**: `DankerMu/SHUD-NC`
- `validate --profile nc`：
  - 允许 `profiles.nc.autoshud` 缺省（默认 steps=[1,2,3]；forcing CSV 生成可不要求）
  - 增加 NetCDF forcing 相关检查（data_root/pattern/adapter 文件存在）
- `run --profile nc`：
  - 跑 AutoSHUD Step1–Step3（静态输入）
  - 调用 `render-shud-cfg` 生成 `.cfg.forcing/.cfg.ncoutput` 并 patch `.cfg.para`
  - 调用 `SHUD/shud <prj>`

## Non-goals
- 不在本 change 实现 SHUD 侧 NetCDF forcing/output（由 SHUD 子模块 issues 完成）。

## Acceptance criteria
- [ ] `python3 tools/shudnc.py ... validate --profile nc` 可用。
- [ ] `python3 tools/shudnc.py ... run --profile nc --dry-run` 输出完整命令序列且不报缺 key。
- [ ] 当 `profiles.nc.shud.run=true` 且 `SHUD/shud` 可执行时，可实际运行（可选）。

## Test plan
- `python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile nc`
- `python3 tools/shudnc.py projects/qhh/shud.yaml run --profile nc --dry-run`

