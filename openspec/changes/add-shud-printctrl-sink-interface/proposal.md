# Change: Add `Print_Ctrl` sink interface (for NetCDF output)

## Why
NetCDF 输出应复用 legacy `Print_Ctrl` 的 interval/buffer 语义（避免重新实现平均/积分逻辑）。因此需要把 `Print_Ctrl` 改造成 “可插拔 sink”：
- legacy sink：继续写 CSV/Binary（保持不变）
- netcdf sink：接收同样的 `t_quantized` 与 buffer 数据并写入 NetCDF

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 为 `Print_Ctrl` 增加可选 sink 回调（onInit/onWrite/onClose）
- sink 回调能获得：
  - `legacy_basename`（用于派生变量名）
  - 全量列数 `n_all` 与被选列索引 `icol[]`
  - `t_quantized_min`（与 legacy 完全一致）

## Non-goals
- 本 change 不实现 NetCDF writer（由后续 changes 完成）。

## Acceptance criteria
- [ ] legacy 输出文件内容与改造前一致（time 与数据）。
- [ ] sink 接口可被调用且不影响 legacy 输出性能/稳定性。

## Test plan
- `make shud`
- baseline case 短模拟，对比关键 legacy 输出文件（至少 1 个 ele、1 个 riv）

