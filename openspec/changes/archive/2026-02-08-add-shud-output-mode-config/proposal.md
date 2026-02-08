# Change: Add `OUTPUT_MODE` / `NCOUTPUT_CFG` to SHUD

## Why
阶段 B 需要在不破坏 legacy 输出的前提下，为 SHUD 增加 NetCDF 输出通道，并允许用户通过 `.cfg.para` 选择 `LEGACY/NETCDF/BOTH`。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 在 `<prj>.cfg.para` 增加并解析：
  - `OUTPUT_MODE LEGACY|NETCDF|BOTH`（默认 LEGACY）
  - `NCOUTPUT_CFG <path>`（当包含 NETCDF 时必填）
- 若启用 NETCDF 但缺少 `NCOUTPUT_CFG`：fail-fast。

## Non-goals
- 本 change 不实现 NetCDF writer（由后续 changes 完成）。

## Acceptance criteria
- [ ] 默认不配置时 legacy 输出完全不变。
- [ ] `OUTPUT_MODE=NETCDF` 且缺失 `NCOUTPUT_CFG` 时 fail-fast 信息清晰。

## Test plan
- `make shud`
- baseline case 短模拟：不加新键、对比输出不变
- 配置 `OUTPUT_MODE NETCDF` 不加 `NCOUTPUT_CFG`：启动即报错

