# Change: Implement NetCDF forcing provider (CMFD2)

## Why
阶段 A 的核心目标：让 SHUD 在运行时直接读 CMFD2 NetCDF，并输出与 baseline（AutoSHUD 生成 CSV）一致的 forcing 值（在可解释误差内），从而消除海量 `dout.forc/*.csv` 的生成与 I/O。

## Scope
- **Repo**: `DankerMu/SHUD-up`
- 新增 `NetcdfForcingProvider`（或 `Cmfd2ForcingProvider`）：
  - 读取 `<prj>.tsd.forc` 的站点列表（lon/lat/Z）
  - 最近邻（NEAREST）采样
  - 时间轴解析：`time.units="hours since ..."` → `t_min`
  - 单位换算对齐 spec（prec/temp/shum/srad/wind/pres → 5 forcing）
  - 跨月文件自动切换（`yyyymm`）
  - 缺测值 fail-fast（指出 file/var/time/station）
- 运行期日志打印前 N 个站点映射（station→grid）

## Non-goals
- 不实现双线性插值（预留扩展点）。
- 不在本 change 支持 ERA5（另一个 change）。

## Acceptance criteria
- [ ] 使用同一套输入网格/参数，`FORCING_MODE=NETCDF` 能跑通短模拟（2–10 天）。
- [ ] 抽样 3 个站点、2 个时刻：五个 forcing 变量与 baseline CSV 一致或在可解释误差内。
- [ ] 启动日志包含 forcing 覆盖范围、步长、站点映射信息。

## Test plan
- 构建：`make shud NETCDF=1`
- 准备 QHH baseline 输入（由 AutoSHUD Step1–Step3 生成），并在 `.cfg.para` 设置短模拟期
- 运行两次：
  - baseline：CSV forcing
  - nc：NetCDF forcing（CMFD2）
- 对比抽样 forcing 值（脚本可在父仓库工具中提供）

## References
- `docs/SPEC_阶段A_SHUD_NetCDF_Forcing.md`（CMFD2 部分）
- `configs/forcing/cmfd2.yaml`

