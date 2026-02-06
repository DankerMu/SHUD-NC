# 阶段 A：将 AutoSHUD 的 Forcing 处理迁移到 SHUD（直接读取 NetCDF）

## 1. 背景与阶段目标

本阶段目标（A）是：**保持 AutoSHUD 现有的静态输入生产能力不变**（网格、土壤/地质/土地利用、参数、初值等仍由 Step1–Step3 生成），但将 **forcing 的“时间序列生成与读取”从 AutoSHUD 迁移到 SHUD**，使 SHUD 能够**直接读取用户提供的原始 NetCDF**（如 CLDAS/GLDAS/NLDAS/CMFD/CMIP6），不再依赖 `dout.forc/*.csv` 这类中间文件。

> 关键词：只迁移 forcing 的 **(3) 抽取/换算** 与 **(4) 时序读取**；保留 **(1) forcing 点位定义** 与 **(2) 网格单元到 forcing 点位映射** 的“轻量成果”。

## 2. AutoSHUD 当前 forcing 处理拆解（4 件事）

可以将 AutoSHUD 的 forcing 相关工作拆成四层：

1) **定义 forcing 点集（空间）**  
   - 站点：读取 `fsp.forc`（气象站点 shapefile）。  
   - NetCDF：生成/读取 `meteoCov`（覆盖流域缓冲区的格点/格元中心集合，例如 `DataPre/pcs/meteoCov.shp`）。

2) **建立“单元 → forcing 点”的映射（空间）**  
   - 通过 `rSHUD::ForcingCoverage()` 生成覆盖面（多点时是 Voronoi/泰森多边形，单点时是一个覆盖全域的面），并写入点位属性 `ID/Lon/Lat/X/Y/Z/Filename`。  
   - `shud.att(... r.forc=sp.forc ...)` 使用三角形单元重心落在覆盖面中的编号，将 `.att` 里的 `FORC`（SHUD 运行时 `Ele[i].iForc`）赋值。

3) **从原始 forcing 源生成 SHUD 需要的 5 个变量时序（时间）**  
   - 典型包括：NetCDF 抽取、时间轴整理、单位换算、RH 计算（比湿+气压+温度）。

4) **把 forcing 交付给 SHUD 的输入接口（文件/读取）**  
   - `<prj>.tsd.forc`：forcing 点位索引表（告诉 SHUD 有多少个 forcing 点、每个点的坐标/高程/文件名）。  
   - `dout.forc/*.csv`：每个 forcing 点一份时序文件（SHUD 逐个读取）。

## 3. 关键澄清：为什么阶段 A 不必把 (1)/(2) 一起搬进 SHUD？

“(1) forcing 点集定义”与“(2) 单元映射”**确实依赖 forcing 的空间结构**，但它们**不依赖 forcing 全时段的时间序列值**：

- 站点 forcing：只需要站点坐标（`fsp.forc`）即可生成覆盖面和 `FORC` 映射；不需要先准备站点时序。
- NetCDF forcing：只需要 NetCDF 的网格坐标（lat/lon 数组与分辨率）即可定义格点集合；甚至只读任意一个文件的 header/坐标维就能完成点集定义。

因此，阶段 A 仍可保留 AutoSHUD 产出的**轻量空间成果**（`.att` 的 `FORC` 映射 + `.tsd.forc` 的点位元数据），而把最“重”的部分（海量 `*.csv` 的生成与 I/O）迁入 SHUD。

## 4. 阶段 A 的迁移边界（做什么 / 不做什么）

### 4.1 迁移到 SHUD 的内容（重点）

- **forcing 时序读取**：SHUD 直接从 NetCDF 读取 forcing；不再读取 `dout.forc/*.csv`。  
- **数据契约与单位换算**：在 SHUD 内复刻 AutoSHUD 的变量换算逻辑（例如 `Rfunction/LDAS_UnitConvert.R` 中的降水/温度/RH/风速/辐射换算）。
- **缓存/分块策略**：按时间窗口/按点位缓存，避免把全流域×全时段一次性读入内存。

### 4.2 保留在 AutoSHUD 的内容（阶段 A 不动）

- SHUD 必需的静态输入：`.mesh/.att/.riv/.soil/.geol/.lc/.lai/.mf/.para/.calib...`（NetCDF 不包含这些）。
- forcing 点位集合与映射的构建：继续由 AutoSHUD 生成 `.att(FORC)` 与 `<prj>.tsd.forc`（或等价文件）。

> 注意：阶段 A 的成功标准不是“完全不跑 AutoSHUD”，而是“不再生成与读取 forcing 的 `dout.forc/*.csv`”。

## 5. SHUD forcing 数据契约（必须一致）

SHUD 在运行时至少需要 5 个 forcing 变量（见 `../SHUD/src/Model/Macros.hpp` 中 `Nforc=5`）：

- `Precip`：单位 **mm/day**（SHUD 内部会再转成 m/min）  
- `Temp`：单位 **℃**（并会按 forcing 点位高程与单元高程做温度订正）  
- `RH`：单位 **0–1**（相对湿度比值）  
- `Wind`：单位 **m/s**  
- `RN`：单位 **W/m²**（净短波/可用辐射，SHUD 内部会乘以 `(1-Albedo)` 再用于 ET）

特别注意两点：

1) **温度高程订正依赖 forcing 点位的 Z**：SHUD 会用 forcing 点高程与单元地表高程做温度订正。阶段 A 仍建议沿用 `<prj>.tsd.forc` 中的 `Z` 字段。  
2) **时间轴必须连续覆盖模拟期**：SHUD 读取 forcing 是“顺时间推进”的；模拟时段内缺数据会直接报错中断。

## 6. 推荐实现方式（SHUD 侧的最小改造）

建议在 SHUD 中引入 “ForcingProvider” 抽象，并实现两种 provider：

- `CsvForcingProvider`：保留现有逻辑（读取 `<prj>.tsd.forc` + `dout.forc/*.csv`），用于回归对照。  
- `NetcdfForcingProvider`：读取 `<prj>.tsd.forc` 获取 forcing 点位元数据（ID/Lon/Lat/X/Y/Z），然后按 `Ele[i].iForc` 在 NetCDF 中采样该点位的 forcing 变量。

最小化接口变更的做法是：仍保留 `<prj>.tsd.forc` 作为“forcing 点位定义文件”，但当 `forcing_mode = netcdf` 时：

- **忽略/不再使用** `Filename` 所指向的 `*.csv`；  
- 将 NetCDF 数据路径、变量名映射、插值方式、时间频率等写入一个新配置（例如在 `.para` 新增键，或增加一个单独的 forcing 配置文件）。

## 7. 与 AutoSHUD 现有逻辑的一致性要求（建议逐源对齐）

阶段 A 的 NetCDF reader 应优先对齐 AutoSHUD 的处理方式，避免“同一数据源、两套换算”：

- RH：AutoSHUD 典型用 `specific humidity + pressure + temperature` 计算 RH，并最终转为 0–1（参考 `Rfunction/LDAS_UnitConvert.R`）。  
- 降水：不同产品的降水单位可能是 `kg m-2 s-1`、`mm/hr` 等；AutoSHUD 对应有不同的换算（同上）。  
- 时间步长：例如 NLDAS 常见为小时尺度；GLDAS 可能为 3 小时；CMFD 常见为 3 小时；需要保证 SHUD 读取时的“时间标签”与模拟步进一致（可采用“分段常值”的策略，与现有 CSV 读取一致）。

## 8. 验收与回归测试建议（阶段 A 必做）

为了证明“迁移正确”，推荐做一组严格回归：

1) **基线**：使用 AutoSHUD 现有流程生成 `dout.forc/*.csv`，用现有 SHUD CSV forcing 跑一个短模拟（可把 `.para` 的 `ENDDAY` 调小到 2–10 天）。  
2) **新实现**：使用同一套 NetCDF 原始数据，切换到 `forcing_mode = netcdf`，跑相同模拟。  
3) **对比**：  
   - 强迫量在点位层面一致（至少抽几处 forcing 点位对比 `Precip/Temp/RH/Wind/RN`）；  
   - 产流/蒸散/水量平衡等关键输出在可接受误差内（若插值策略不同，允许小差异，但需解释）。

## 9. 阶段 A 明确不做（避免范围膨胀）

- 不把 GIS 预处理（投影转换、流域裁剪、DEM 抽取等）塞进 SHUD 主程序。  
- 不试图“完全不跑 AutoSHUD”。静态输入与 `FORC` 映射依然依赖 AutoSHUD（或等价预处理工具）。

---

## 附：关键文件位置（便于查代码/对齐行为）

- AutoSHUD forcing 分发入口：`Step2_DataSubset.R`（`iforcing` 分支）  
- forcing 点与 `.tsd.forc` 写出：`Step3_BuidModel.R`（`write.forc(...)`）  
- forcing 覆盖面生成：`../rSHUD/R/Func_GIS.R`（`ForcingCoverage()`）  
- `.att` 中 `FORC` 赋值：`../rSHUD/R/MeshDomain.R`（`shud.att()`）  
- SHUD 读取 `.tsd.forc` 并加载 forcing：`../SHUD/src/ModelData/MD_readin.cpp`（`read_forc_csv`）  
- AutoSHUD 单位换算参考：`Rfunction/LDAS_UnitConvert.R`

