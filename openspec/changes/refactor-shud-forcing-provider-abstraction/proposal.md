# Change: Refactor forcing to a provider abstraction

## Why
阶段 A 需要支持 NetCDF forcing，但现有实现把 forcing 强耦合在 `tsd_weather[]`（每站 CSV）上。引入 `ForcingProvider` 抽象可在 **不改变外部语义** 的前提下扩展新的 forcing 来源。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 新增 `ForcingProvider` 接口（step-function 语义）并提供：
  - `movePointer(t_min)`
  - `get(station_idx, var)`（五变量）
  - `currentTimeMin()/nextTimeMin()`（TSR 需要）
  - station 元数据：lon/lat/z
- 实现 `CsvForcingProvider` 复用现有 `_TimeSeriesData` 行为。
- 将 `Model_Data::updateAllTimeSeries()` 与 `tReadForcing()` 的 forcing 读数改为走 provider。

## Non-goals
- 不改变 forcing 变量单位契约与时间语义（必须与 baseline 完全一致）。
- 不在本 change 实现 `NetcdfForcingProvider`。

## Acceptance criteria
- [ ] baseline case 跑短模拟结果与改造前一致（允许极小浮点误差，但原则上应一致）。
- [ ] TSR 依赖的 `currentTimeMin/nextTimeMin` 语义保持一致。
- [ ] 代码改动最小化：仅将 forcing 访问点替换为 provider 调用。

## Test plan
- `make shud`
- baseline 输入跑 2–10 天，抽查 1–2 个 legacy 输出文件对齐（time 与数值）

## References
- `docs/SPEC_阶段A_SHUD_NetCDF_Forcing.md`（3.2）

