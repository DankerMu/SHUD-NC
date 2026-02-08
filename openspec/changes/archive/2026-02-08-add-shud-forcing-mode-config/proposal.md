# Change: Add `FORCING_MODE` / `FORCING_CFG` to SHUD

## Why
阶段 A 需要在 **不改变 SHUD 命令行**（仍 `shud <prj>`）的前提下，让用户可以从 `.cfg.para` 切换 forcing 来源（CSV vs NetCDF），且默认保持 baseline 行为不变。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 在 `<prj>.cfg.para` 增加并解析：
  - `FORCING_MODE CSV|NETCDF`（默认 CSV）
  - `FORCING_CFG <path>`（仅 NETCDF 必填；相对路径相对 `input/<prj>/`）
- 当 `FORCING_MODE=NETCDF` 但缺失/不可读 `FORCING_CFG` 时 fail-fast（清晰错误）。

## Non-goals
- 本 change **不实现** NetCDF forcing 读取（由后续 change 完成）。
- 本 change **不修改** AutoSHUD 逻辑。

## Acceptance criteria
- [ ] 不配置新键时，baseline 行为完全一致（CSV forcing 读取路径不变）。
- [ ] `FORCING_MODE=NETCDF` 且缺少 `FORCING_CFG` 时，启动即 fail-fast 并提示修复方式。
- [ ] 解析支持 `CSV/NETCDF`（大小写不敏感），非法值给出明确提示。

## Test plan
- `make shud`（或仓库现有构建方式）
- 使用一个已存在的 baseline 输入目录：
  - 不加新键跑短模拟（2–10 天）确认行为不变
  - 加 `FORCING_MODE NETCDF` 但不提供 `FORCING_CFG`，确认报错信息可定位

## References
- `docs/SPEC_阶段A_SHUD_NetCDF_Forcing.md`

