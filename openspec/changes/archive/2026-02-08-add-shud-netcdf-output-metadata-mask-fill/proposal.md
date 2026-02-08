# Change: Add metadata registry + masks + fill values for NetCDF outputs

## Why
第一版 NetCDF 输出必须做到 “完整 + 可回归 + 可后处理”。当 legacy `cfg.output` 关闭部分列时，NetCDF 仍应输出 **全量维度** 并用 `_FillValue` 填充，同时提供 mask 变量；并补充 units/long_name/global attributes。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- NetCDF 变量维度统一全量（NumEle/NumRiv/NumLake），禁用列用 `_FillValue`
- 写出 mask：
  - `element_output_mask(mesh_face)` / `river_output_mask(river)` / `lake_output_mask(lake)`
- 建立变量 metadata registry（至少覆盖核心变量）：units、long_name（可先按 legacy 后缀表驱动）
- 全局属性：Conventions（CF/UGRID）、title、history、forcing_mode/product（若可得）

## Non-goals
- 不要求一次性补齐所有 CF `standard_name`（可后续增强）。

## Acceptance criteria
- [ ] NetCDF 变量维度为全量对象维，禁用列被填充 `_FillValue`。
- [ ] mask 变量存在且与 cfg.output 一致。
- [ ] 至少核心变量具有 units/long_name。

## Test plan
- 准备一个 cfg.output 关闭部分列的 case
- 运行并检查 NetCDF：维度长度、fill 值、mask、units

