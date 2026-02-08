# Change: Add river & lake NetCDF output files

## Why
阶段 B 最终输出需要拆分为 3 文件（ele/riv/lake），分别承载不同对象类型的 time-series 变量，便于下游工具处理。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 输出文件：
  - `<prefix>.riv.nc`（river 维度）
  - `<prefix>.lake.nc`（lake 维度）
- 写入基础索引变量（`river_id`、`lake_id` 等），并把对应 `Print_Ctrl` 变量写入对应文件。

## Non-goals
- 不在本 change 完成完整 metadata registry（由后续 change 完成）。

## Acceptance criteria
- [ ] 启用 NetCDF 输出后生成 3 个文件（ele/riv/lake）。
- [ ] riv/lake 文件可被 xarray 打开且维度正确。

## Test plan
- 短模拟启用 `OUTPUT_MODE=BOTH`
- 检查 `*.riv.nc`、`*.lake.nc` 存在并可打开

