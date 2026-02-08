# Change: Write UGRID mesh into `<prefix>.ele.nc`

## Why
为了让 element 变量可在非结构网格上被 QGIS/Panoply/xarray 友好识别，需要在 element NetCDF 文件里写入 UGRID mesh topology 与 connectivity。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 在 `<prefix>.ele.nc` 写入：
  - node 坐标（x/y）
  - face connectivity（3 节点三角形，start_index=1）
  - topology variable `mesh`（`cf_role="mesh_topology"` 等）
  - 可选 face center 坐标（默认开启）

## Non-goals
- 本 change 不扩展 riv/lake 文件（后续）。

## Acceptance criteria
- [ ] `<prefix>.ele.nc` 包含 UGRID mesh 变量与属性，且不影响 time-series append。
- [ ] 常见工具可识别 mesh（至少不会报错）。

## Test plan
- 运行短模拟生成 `<prefix>.ele.nc`
- 用 `ncdump -h` 或 xarray 检查 mesh 变量与属性存在

