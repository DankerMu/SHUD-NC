# SPEC（阶段 A）：SHUD 直接读取 Forcing NetCDF（实现细则）

> Last updated: 2026-02-07  
> 目标：在 **不改变 AutoSHUD 静态输入生产能力**（Step1–Step3）与 `.att(FORC)` 映射方式的前提下，让 SHUD 在运行时 **不再读取 `dout.forc/*.csv`**，而是直接从用户提供的原始 NetCDF 读取 forcing，并严格遵守 SHUD 现有 forcing 变量契约与时间推进语义。

## 1. 范围与非目标

### 范围（本 spec 覆盖）
- SHUD 新增 `NetcdfForcingProvider`，支持：
  - **CMFD v2.0（3-hour, 0.1°）**：按 `Prec/Temp/SHum/SRad/Wind/Pres` 读取并换算到 SHUD 5 forcing。
  - **ERA5（QHH 子集，日文件、小时步长）**：按 `tp/t2m/d2m/u10/v10/ssr/sp` 读取并换算到 SHUD 5 forcing。
- 配置：SHUD 仍走 `.cfg` 风格（KEY VALUE），不引入 YAML 解析依赖。
- 时间语义：与现有 CSV forcing 完全一致（step‑function、`currentTimeMin/nextTimeMin` 可用）。

### 非目标（阶段 A 不做）
- 不把 GIS 预处理搬到 SHUD（仍由 AutoSHUD 负责：WBD/DEM/river/soil/landuse/mesh/att/...）。
- 不强制移除 baseline（CSV forcing）路径：必须保留用于回归对照。

---

## 2. SHUD forcing 变量契约（必须保持一致）

SHUD 内部固定 5 个 forcing（见 `SHUD/src/Model/Macros.hpp`）：

| SHUD 列 | 宏 | 含义 | 单位（进入 SHUD 前） | 备注 |
|---|---:|---|---|---|
| 1 | `i_prcp` | Precip | **mm/day** | SHUD 内部会再转为 `m/min`：`mm/day * 0.001 / 1440` |
| 2 | `i_temp` | Temp | **°C** | SHUD 会做高程订正：`TemperatureOnElevation(t0, Ele.z_surf, forcZ)` |
| 3 | `i_rh` | RH | **0–1** | SHUD 内部会 clamp 到 `[CONST_RH, 1]` |
| 4 | `i_wind` | Wind | **m/s** | SHUD 内部会 `abs(...) + 0.001` 防止 0 风 |
| 5 | `i_rn` | RN | **W/m²** | `RADIATION_INPUT_MODE` 决定是否乘 `(1-Albedo)` |

### 时间推进语义（必须保持一致）
- SHUD forcing 在运行时是 **分段常值（step function）**：在一个 forcing 时间区间内，`get()` 返回的值不随 t 变化。
- `currentTimeMin()` / `nextTimeMin()` 必须可用：TSR（terrain radiation）会用它们确定 forcing 区间 `[t0, t1)`。

> 结论：NetCDF forcing provider 必须提供与 `_TimeSeriesData::movePointer/getX/currentTimeMin/nextTimeMin` 同等语义的接口。

---

## 3. 依赖与输入文件（NetCDF forcing 模式仍依赖 `.tsd.forc`）

### 3.1 仍然要求 `<prj>.tsd.forc`

即使 forcing 来自 NetCDF，SHUD **仍要求** `input/<prj>/<prj>.tsd.forc` 存在，原因：
- 提供 forcing 点位列表（lon/lat/Z 等），并决定 `NumForc`。
- 提供 `ForcStartTime`（base date），SHUD 全部时间轴都是“分钟相对 base date”。
- `.att` 中 `Ele[i].iForc` 仍引用这些 forcing 点位（1‑based）。

`.tsd.forc` 格式保持不变（现有 `read_forc_csv()` 解析格式）：
1) 第 1 行：`<NumForc> <ForcStartTime_YYYYMMDD>`  
2) 第 2 行：forcing CSV 的相对路径（NetCDF 模式下可以保留任意值，SHUD 会忽略 CSV 文件名）  
3) 第 3 行：表头（忽略）  
4) 后续：每行 `ID Lon Lat X Y Z Filename`

### 3.2 新增 `.cfg` 配置文件（仅在 NetCDF forcing 模式下要求）

#### `.cfg.para` 新增键
在 `input/<prj>/<prj>.cfg.para` 增加（KEY VALUE）：
- `FORCING_MODE CSV|NETCDF`（缺省为 `CSV`，保证 baseline 不变）
- `FORCING_CFG <path>`（仅当 `FORCING_MODE=NETCDF` 时必填）

> 解析规则：`<path>` 若为相对路径，则相对 **输入目录 `input/<prj>/`**。

#### `<prj>.cfg.forcing`（forcing 配置）
文件名建议：`input/<prj>/<prj>.cfg.forcing`，内容为 KEY VALUE（大小写不敏感）：

> 重要：`projects/<case>/shud.yaml` 中引用的 adapter YAML（如 `configs/forcing/*.yaml`）是 **runner-only** 模板；
> `tools/shudnc.py render-shud-cfg` 会把它们渲染为 SHUD 运行时实际读取的 KEY VALUE `*.cfg`（单一真相），SHUD **不读 YAML**。

**必需键（所有产品都支持）**
- `PRODUCT CMFD2|ERA5`
- `DATA_ROOT <path>`：原始 NetCDF 数据根目录（相对或绝对）
  - 路径解析：在实现中，若为相对路径，则相对 `run_dir`（`.../runs/<case>/<profile>/`）。

**布局（layout）键（通用；runner 会从 adapter 渲染）**
- `LAYOUT_FILE_PATTERN <pattern>`：文件名模式（支持少量模板替换）
  - CMFD2：需要 `{yyyymm}`；ERA5：需要 `{yyyymmdd}`
  - 允许使用 `{var_lower}`（如 `prec/temp/...`）
- `LAYOUT_YEAR_SUBDIR 1|0`（可选；ERA5 常用）
  - `1`：先尝试 `DATA_ROOT/<yyyy>/...`，失败再回退 `DATA_ROOT/...`
  - `0`：只使用 `DATA_ROOT/...`
- `LAYOUT_VAR_DIR_<VAR> <dir>`（主要用于 CMFD2）
  - `VAR` 取值：`PREC|TEMP|SHUM|SRAD|WIND|PRES`
  - 例：`LAYOUT_VAR_DIR_PREC Prec`（表示数据位于 `DATA_ROOT/Prec/`）

**NetCDF 维度/变量名键（通用；runner 会从 adapter 渲染）**
- `NC_DIM_TIME <name>`（可选；默认 `time`）
- `NC_DIM_LAT <name>`（可选；默认 `lat`）
- `NC_DIM_LON <name>`（可选；默认 `lon`）
- `TIME_VAR <name>`（可选；默认与 `NC_DIM_TIME` 相同）
- `LAT_VAR <name>`（可选；默认与 `NC_DIM_LAT` 相同）
- `LON_VAR <name>`（可选；默认与 `NC_DIM_LON` 相同）
- `NC_VAR_<VAR> <name>`（变量名映射）
  - CMFD2：`VAR` 取值 `PREC|TEMP|SHUM|SRAD|WIND|PRES`
  - ERA5：`VAR` 取值 `TP|T2M|D2M|U10|V10|SSR|SP`

**换算/语义键**
- `RADIATION_KIND SWDOWN|SWNET`（可选；若提供，则覆盖/校验 `.cfg.para` 的 `RADIATION_INPUT_MODE`）
- `CMFD_PRECIP_UNITS AUTO|KG_M2_S|MM_HR`（默认 `AUTO`：按 NetCDF `units` 自动判定；判定失败则报错要求显式指定）

> 兼容性说明：
> - 实现当前支持 `CMFD_FILE_PATTERN` / `ERA5_FILE_PATTERN` 作为 `LAYOUT_FILE_PATTERN` 的别名；
> - 不再支持 `CMFD_SUBDIR_*` / `CMFD_VAR_*` / `ERA5_VAR_*` 这类旧键（请使用 `LAYOUT_VAR_DIR_*` / `NC_VAR_*`）。

**示例（由 `tools/shudnc.py render-shud-cfg` 生成的最小配置片段）**

CMFD2：
```text
PRODUCT CMFD2
DATA_ROOT ../../Data/Forcing/CMFD_2017_2018
LAYOUT_FILE_PATTERN {var_lower}_CMFD_*_{yyyymm}.nc
LAYOUT_VAR_DIR_PREC Prec
NC_DIM_TIME time
NC_DIM_LAT lat
NC_DIM_LON lon
NC_VAR_PREC prec
CMFD_PRECIP_UNITS AUTO
```

---

## 4. NetCDF 读入通用规则（适配所有产品）

### 4.1 维度与坐标
- 必须存在坐标变量：`time`、`lat/latitude`、`lon/longitude`（名称可配置覆盖）。
- `lat` 允许递增或递减；`lon` 允许递增。
- `lon` 可能是 `0..360` 或 `-180..180`；实现需要做 lon 归一化：
  - 若数据是 `0..360`，站点 lon（通常 `-180..180`）需映射到 `[0,360)`。
  - 若数据是 `-180..180`，站点 lon 保持原样。

### 4.2 缩放与缺测
对所有数值变量，必须按 netCDF 约定处理：
- 若存在 `scale_factor` / `add_offset`：`val = raw * scale_factor + add_offset`
- 若存在 `_FillValue` 或 `missing_value`：遇到缺测值应 fail-fast（报错指出 file/var/time/idx），默认不做插补。

### 4.3 时间轴解析
SHUD 内部时间 `t_min` 的定义：**距 `ForcStartTime`（YYYYMMDD 00:00 UTC）过去的分钟数**。

NetCDF 时间轴需支持解析：
- `time.units = "hours since YYYY-MM-DD HH:MM:SS"`（CMFD2/ERA5 都是该类）
- `time.calendar` 若缺省，按 `standard/gregorian` 处理

实现要求：
- 读取 `time[]`（单位小时），转换为 `t_min[]`（分钟相对 `ForcStartTime`）
- 校验 `t_min[]` 单调非递减
- provider 需暴露：
  - `minTimeMin()` / `maxTimeMin()`：用于覆盖期校验
  - `currentTimeMin()` / `nextTimeMin()`：用于 TSR

---

## 5. 站点采样规则（NEAREST）

### 5.1 站点来源
- 站点列表来自 `<prj>.tsd.forc` 的 Lon/Lat 列（单位：度）。
- station_idx 采用 `.tsd.forc` 读入顺序（0‑based 内部；SHUD `.att` 是 1‑based）。

### 5.2 最近邻索引
对每个站点，预计算最近邻格点索引：
- `i_lon = argmin(|lon - lon_station|)`
- `i_lat = argmin(|lat - lat_station|)`（lat 可能递减，不能用简单二分假设递增）

并缓存：
- `station_lon/lat`（原值）
- `grid_lon[i_lon]` / `grid_lat[i_lat]`（用于日志与可解释性）

> 要求：启动时打印前 N 个站点的映射（station → grid），便于用户排查“点位偏移”。

---

## 6. 产品适配：CMFD2（3-hour, 0.1°）

### 6.1 文件与变量（基于当前样例数据实测）
- 文件：`Data/Forcing/CMFD_2017_2018/<Var>/*_201701.nc`
- 维度：`time(248), lat(400), lon(700)`
- 变量名与单位（实测）：
  - `prec`：`kg m-2 s-1`
  - `temp`：`K`
  - `shum`：`kg kg-1`
  - `srad`：`W m-2`（downwelling shortwave）
  - `wind`：`m s-1`
  - `pres`：`Pa`
- 时间：`time.units = "hours since 1900-01-01 00:00:0.0"`（3 小时步长）

### 6.2 换算到 SHUD forcing
- `Temp_C = temp - 273.15`
- `RH_percent = 0.263 * pres * shum / exp(17.67 * (temp - 273.15) / (temp - 29.65))`
  - clamp：`RH_percent = min(RH_percent, 100)`
  - `RH_1 = RH_percent / 100`
- `Wind_m_s = abs(wind)`
- `RN_W_m2 = srad`
- `Precip_mm_day`：
  - 若 `prec.units` 匹配 `kg m-2 s-1`（或等价写法）：
    - `Precip_mm_day = prec * 86400`
  - 若 `prec.units` 匹配 `mm hr-1`（或等价写法）：
    - `Precip_mm_day = prec * 24`
  - 其他：要求用户在 `CMFD_PRECIP_UNITS` 显式指定，否则报错。

### 6.3 `RADIATION_KIND`
CMFD2 `srad` 为 downward shortwave，默认：
- `RADIATION_KIND = SWDOWN`（对应 SHUD 的 `RADIATION_INPUT_MODE=SWDOWN`）

---

## 7. 产品适配：ERA5（QHH 子集，日文件、小时步长）

### 7.1 文件与变量（基于当前样例数据实测）
- 文件：`Data/Forcing/ERA5/qhh/2017/ERA5_20170101.nc`（netCDF3）
- 维度：`time(24), latitude(26, 递减), longitude(41, 递增)`
- 变量（实测）：
  - `tp`：Total precipitation，units=`m`（**累积量**）
  - `t2m`：2m temperature，units=`K`
  - `d2m`：2m dewpoint，units=`K`
  - `u10/v10`：10m wind components，units=`m s**-1`
  - `ssr`：Surface net short-wave radiation，units=`J m**-2`（**累积能量**）
  - `sp`：Surface pressure，units=`Pa`
- 时间：`time.units = "hours since 1900-01-01 00:00:00.0"`（1 小时步长）
- 注意：ERA5 变量常带 `scale_factor/add_offset`（packed int16）；实现必须按通用规则解包。

### 7.2 累积变量的“区间增量”算法（关键）
`tp` 与 `ssr` 是累积变量，必须转换为“区间内平均量”（step‑function）：

对任意格点，设 `A[k]` 是 time[k] 时刻的累积值；则区间 `[k, k+1)` 的增量为：
- `dA = A[k+1] - A[k]`
- 若 `dA >= 0`：`inc = dA`
- 若 `dA < 0`（累积重置/拼接）：`inc = A[k+1]`

这样得到的 `inc[k]` 对应区间 `[time[k], time[k+1])`，可直接用于 step‑function forcing。

### 7.3 换算到 SHUD forcing

**温度**
- `Temp_C = t2m - 273.15`

**相对湿度（由露点计算，0–1）**
- `T = t2m - 273.15`（°C）
- `Td = d2m - 273.15`（°C）
- `es(T)  = 6.112 * exp(17.67*T /(T + 243.5))`（hPa）
- `ea(Td) = 6.112 * exp(17.67*Td/(Td + 243.5))`（hPa）
- `RH_1 = clamp(ea/es, 0, 1)`

**风速**
- `Wind_m_s = sqrt(u10*u10 + v10*v10)`（并可对最终结果取 `abs`）

**降水（mm/day）**
- 先用 7.2 算 `tp_inc_m[k]`（单位 m/interval）
- 令 `dt_sec = (time[k+1] - time[k]) * 3600`
- `Precip_mm_day = tp_inc_m * 1000 * (86400 / dt_sec)`
  - 对 1 小时步长：等价于 `tp_inc_m * 1000 * 24`

**辐射（W/m²）**
- 先用 7.2 算 `ssr_inc_jm2[k]`（单位 J/m2/interval）
- `RN_W_m2 = ssr_inc_jm2 / dt_sec`
- 由于 `ssr` 是 **net shortwave**，默认：
  - `RADIATION_KIND = SWNET`（对应 SHUD 的 `RADIATION_INPUT_MODE=SWNET`）

---

## 8. Provider 运行时缓存与 I/O 策略（必须）

### 8.1 为什么必须缓存
SHUD 在每个时间步会对每个 element 调用 `tReadForcing(t, i)`，若 provider 每次都触发 NetCDF I/O，会导致性能灾难。

### 8.2 强制要求的缓存层级
provider 必须做到：
- `movePointer(t_min)` 发生“时间索引变化”时才读 NetCDF（一次）
- 在该时间索引下，预先计算并缓存：
  - `prec_mm_day[NumForc]`
  - `temp_c[NumForc]`
  - `rh_1[NumForc]`
  - `wind_ms[NumForc]`
  - `rn_wm2[NumForc]`
- `get(station_idx, var)` 只能是 O(1) 的数组读取（不得 I/O）

### 8.3 文件切换
- CMFD2：按 `yyyymm` 组织（每月一个文件），provider 需在跨月时自动 open/close。
- ERA5：按 `yyyymmdd` 组织（每天一个文件），provider 需在跨日时自动 open/close。

---

## 9. 错误处理与日志（必须清晰、可定位）

必须 fail-fast 的情况：
- `FORCING_MODE=NETCDF` 但缺少 `FORCING_CFG`
- `FORCING_CFG` 指向文件不存在/不可读
- `DATA_ROOT` 不存在
- 期望变量/坐标不存在（指出 file + var + 可用变量列表）
- time 轴不可解析或非单调
- forcing 覆盖期不足（指出模拟区间与 forcing 覆盖区间）
- 任一站点采样到缺测值（指出 station_idx、lon/lat、time、文件名）

建议打印（启动时）：
- forcing 模式、产品、数据根目录
- `NumForc`、`ForcStartTime`
- 前 5 个站点：`(lon,lat)->(grid_lon,grid_lat)`
- time 覆盖范围（min/max）与步长（分钟）
