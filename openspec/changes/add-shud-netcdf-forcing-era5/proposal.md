# Change: Implement NetCDF forcing provider (ERA5 subset)

## Why
在 CMFD2 打通后，ERA5（QHH 子集）是第二个高优先级 forcing 产品。ERA5 的关键复杂度是 **累积变量**（tp/ssr）的区间增量换算与 lat 递减坐标。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 新增 ERA5 适配：
  - 文件布局：按 `yyyymmdd`（可选 year 子目录）
  - 变量映射：`tp/t2m/d2m/u10/v10/ssr/sp`
  - 累积变量 `tp/ssr` 的 “区间增量” 算法（处理 reset）
  - `ssr` → `RN (W/m²)`，并默认匹配 `RADIATION_INPUT_MODE=SWNET`

## Non-goals
- 不在本 change 覆盖其它 ERA5 导出变体（若维度/变量名不同，先通过配置覆盖）。

## Acceptance criteria
- [ ] `FORCING_MODE=NETCDF` + ERA5 能跑通短模拟。
- [ ] 抽样站点/时刻对齐：温度、RH、风速、降水、辐射与 baseline CSV（或与已知期望）一致。
- [ ] `tp/ssr` 累积重置被正确处理（不出现明显负值/跳变）。

## Test plan
- `make shud NETCDF=1`
- 运行 QHH 子集 ERA5 的短模拟（2–10 天）
- 抽样对比 forcing 与输出（最小对比脚本可复用）

## References
- `docs/SPEC_阶段A_SHUD_NetCDF_Forcing.md`（ERA5 部分）
- `configs/forcing/era5.yaml`

