# Change: Implement NetCDF output core (element file + time axis)

## Why
阶段 B 的第一步：在不影响 legacy 的前提下，先把 NetCDF “写文件 + time 轴 + append” 跑通，验证 sink 机制与 time 语义正确。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 实现 `NetcdfPrintSink`（或等价）：
  - 创建 `<prefix>.ele.nc`（先 element 文件）
  - 写 `time` unlimited 维度与 units（minutes since ForcStartTime）
  - 写至少 1 个 element 变量（例如 `eleygw` 或任意已启用 Print_Ctrl 变量）
  - 可通过 `NCOUTPUT_CFG` 指定输出目录与格式（默认 NETCDF4_CLASSIC）

## Non-goals
- 本 change 不要求写 UGRID mesh（下一条 change）。
- 本 change 不要求覆盖 riv/lake（后续）。

## Acceptance criteria
- [ ] `OUTPUT_MODE=NETCDF` 可生成 `<prefix>.ele.nc`，xarray 可 `open_dataset`。
- [ ] time 轴数值与 legacy 输出 time 对齐（left endpoint）。

## Test plan
- `make shud NETCDF=1`
- 跑短模拟（同时开 legacy + netcdf），抽样对齐 time（可用脚本）

