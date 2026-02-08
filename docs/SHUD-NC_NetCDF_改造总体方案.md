# SHUD‑NC NetCDF 改造方案（完整性 + 简洁性 + 用户友好）

> Last updated: 2026-02-07  
> Scope: 本文是 SHUD‑NC（父仓库 + SHUD 子模块 + AutoSHUD 子模块）的 **总体改造方案**。实现代码应主要落在 `SHUD/` 子模块；父仓库只负责项目组织与一键运行编排。

## 0. 目标与成功标准

### 目标

1) **SHUD forcing 输入**：从“每站 CSV”切换为 **直接读取原始 NetCDF**（先支持 **CMFD2 + ERA5（QHH 子集）**；GLDAS/FLDAS 预留）。  
2) **SHUD 输出**：生成 **规范 NetCDF**（CF/UGRID 友好），便于 xarray/netCDF4/QGIS/Panoply 等直接读取。  
3) **保留 baseline**：保持并可运行 **AutoSHUD→SHUD 原 pipeline**（CSV forcing + legacy 输出）作为对照回归基线。

### 成功标准（验收）

- baseline profile 能跑通且结果不变（同一 commit 下）。
- nc profile 能在相同输入网格/参数下跑通：  
  - forcing 点位层面：抽样若干 forcing 点（`<prj>.tsd.forc` 中的站点），`Precip/Temp/RH/Wind/RN` 与 AutoSHUD 生成 CSV 的同一时刻一致（或在可解释误差内）。  
  - 输出：生成 3 个 `.nc` 文件（ele/riv/lake），xarray 可直接 `open_dataset`，维度/变量齐全，time 轴语义明确。
- 对用户：只需要改 `projects/<case>/shud.yaml`（单入口），即可切换 baseline 与 nc。

---

## 1. 当前项目结构评估（是否冗余）

meta‑repo 分层（`projects/` + `configs/` + `tools/` + `Data/` + `runs/` + 两个 submodule）**利于达成目标**，且没有明显冗余：

- **实现落在 `SHUD/`**：forcing NetCDF provider、NetCDF writer 都应在这里做，避免父仓库承担“模型能力”。  
- **父仓库只做编排与约定**：`projects/<case>/shud.yaml` 单入口、`tools/shudnc.py` 一键运行、`Data/README.md` 数据契约。  
- `configs/forcing/*.yaml` 与 `configs/output/*.yaml` 不是冗余：它们是**可复用的产品适配/输出规范**（源数据一变只改配置，不改代码）。运行时给 SHUD 的配置会在 `runs/.../config/` 里生成（不入库），避免“双份真相”。

---

## 2. 配置设计（单入口 shud.yaml + 生成 SHUD cfg overlay）

### 2.1 `projects/<case>/shud.yaml`（单入口，用户只改它）

保持现有结构，但做两点“去硬编码/更通用”约束：

- **不允许把“时间/区域”写进 key 名**（例如 `cmfd_2017_2018`、`era5_qhh`）；仅用路径与参数表达。
- forcing 与 output 的细节配置都收敛到 `profiles.<name>.shud.*`，并允许将路径写成相对路径（相对 repo root）或绝对路径。

### 2.2 运行时生成的 SHUD 配置（不要求 SHUD 解析 YAML）

**SHUD 侧新增配置沿用 `.cfg` 风格（KEY VALUE 文本）**，避免引入 `yaml-cpp`。

- 生成文件建议放到 `runs/<case>/<profile>/config/` 并在运行前写入 `runs/.../input/<prj>/`：
  - `runs/.../input/<prj>/<prj>.cfg.forcing`（NetCDF forcing 配置）
  - `runs/.../input/<prj>/<prj>.cfg.ncoutput`（NetCDF 输出配置）
- 同时由 `tools/shudnc.py` 负责对 `runs/.../input/<prj>/<prj>.cfg.para` 做**追加/补丁**（append 若干键即可），确保“只改 shud.yaml 即可切换”。

---

## 3. SHUD 子仓库：阶段 A（forcing 直接读 NetCDF）

对齐 `docs/阶段A_SHUD直接读取NetCDF_forcing迁移方案.md` 的边界：保留 AutoSHUD 做 (1)(2)，把 (3)(4) 迁入 SHUD。

### 3.1 数据契约（保持与现有 SHUD 一致）

SHUD 内部最终仍只吃 5 个 forcing：

- Precip：`mm/day`
- Temp：`°C`（仍保留高程订正依赖 forcing 点 Z）
- RH：`0–1`
- Wind：`m/s`
- RN：`W/m²`（与现有 `RADIATION_INPUT_MODE` 兼容）

### 3.2 代码结构与接口（ForcingProvider 抽象）

在 `SHUD/src/forcing/` 新增：

- `ForcingProvider.hpp`：统一接口（最少包含）
  - `movePointer(t_min)`（与现有 step‑function forcing 一致）
  - `get(station_idx, var)`（返回当前 forcing 值）
  - `currentTimeMin()/nextTimeMin()`（给 TSR 用）
  - 站点元数据：lon/lat/z
  - `minTime()/maxTime()`（用于覆盖期校验）
- `CsvForcingProvider.*`：复用现有逻辑（读取 `<prj>.tsd.forc` + 加载每站 CSV）
- `NetcdfForcingProvider.*`：新增（读取 `<prj>.tsd.forc` 站点列表，但**忽略 Filename 指向的 csv**，直接从 NetCDF 采样）

修改点（最小侵入）：

- `SHUD/src/ModelData/MD_readin.cpp`：把 `read_forc_csv()` 改为 `initForcing()`，根据 `FORCING_MODE` 选择 provider。  
- `SHUD/src/ModelData/MD_update.cpp`：`updateAllTimeSeries()` 中 forcing 改为 `forcing->movePointer(t_min)`。  
- `SHUD/src/ModelData/MD_ET.cpp`：`tReadForcing()` 取值从 `tsd_weather[idx].getX(...)` 改为 `forcing->get(idx, ...)`，并用 provider 的 `current/nextTimeMin` 维持 TSR 行为一致。  
- `SHUD/src/ModelData/Model_Data.hpp`：新增 `std::unique_ptr<ForcingProvider> forcing;`，CSV 模式下可继续保留 `tsd_weather` 不动（或逐步内聚到 provider）。

### 3.3 NetCDF 适配（先 CMFD2，再 ERA5）

**插值方式**：默认 `NEAREST`（并预留未来加 `BILINEAR` 的扩展点）。

#### CMFD2（`Data/Forcing/CMFD_2017_2018/<Var>/*.nc`）

- 按 `Prec/Temp/SHum/SRad/Wind/Pres` 六类读入，按 AutoSHUD 的公式换算（`configs/forcing/cmfd2.yaml` 作为参考/spec）。  
- 读取策略：按站点 bounding box 计算 `lon/lat` 子集窗口，仅读子块，避免全局切片 I/O。

#### ERA5（`Data/Forcing/ERA5/qhh/<year>/ERA5_YYYYMMDD.nc`）

- 先检查 1 个样例文件的：维度名、变量名、单位、time 轴含义；再补全 `configs/forcing/era5.yaml`。  
- SHUD 侧实现 `Era5Adapter`：明确
  - 降水是累积还是瞬时率、换算到 `mm/day` 的窗口
  - RH 是直接给还是需要从（q/p/T）或（d2m/T）推导
  - RN 用哪一类辐射变量并换算到 `W/m²`

### 3.4 SHUD 侧配置（`.cfg.para` 追加键 + `*.cfg.forcing`）

不改 SHUD 命令行；仍运行 `shud <prjname>`。  
由 `tools/shudnc.py` 在运行前写入：

- `<prj>.cfg.para` 追加：
  - `FORCING_MODE NETCDF`（或 CSV）
  - `FORCING_CFG <relative/or/abs path to <prj>.cfg.forcing>`
- `<prj>.cfg.forcing`（KEY VALUE），至少包含：
  - `PRODUCT CMFD2|ERA5`
  - `DATA_ROOT <path>`
  - `METHOD NEAREST`
  - 文件布局（pattern/子目录）与维度/变量名（允许覆盖默认值）

### 3.5 构建系统

- `SHUD/Makefile` 增加可选 `NETCDF=1` 开关：
  - `-lnetcdf` 链接（优先 netcdf‑c C API，避免 netcdf‑cxx 兼容问题）
  - 文档补充：macOS 用 `brew install netcdf`，Linux 用 `libnetcdf-dev` 等。

---

## 4. SHUD 子仓库：阶段 B（输出写规范 NetCDF）

### 4.1 输出文件布局

输出 3 个文件（默认放到 `OUTPUT_NETCDF_DIR`）：

- `<prj>.ele.nc`：UGRID mesh + element 相关变量（所有 `NumEle` 维度）
- `<prj>.riv.nc`：river 相关变量（`NumRiv` 维度）
- `<prj>.lake.nc`：lake 相关变量（`NumLake` 维度）

### 4.2 复用现有输出逻辑（Print_Ctrl sink 化）

目标是：**不重新发明“输出间隔/平均/积分语义”**，直接复用 `Print_Ctrl` 的 buffer 机制，保证与 legacy 输出一致。

- 改造 `SHUD/src/classes/Model_Control.hpp/.cpp`：
  - 为 `Print_Ctrl` 增加可选 sink（例如 `IPrintSink* sink`），当达到输出边界时把 `(time, buffer[])` 交给 sink。
  - 现有 ASCII/BINARY sink 保持不变；新增 `NetcdfPrintSink`，内部持有 `NetcdfOutputManager`（3 文件）。
- `Model_Data::initialize_output()`：
  - 当 `OUTPUT_MODE` 包含 NETCDF 时：创建 `NetcdfOutputManager`，并把每个 `PCtrl[i]` 注册为一个 NetCDF 变量（按 `NumVar` 自动归类到 ele/riv/lake 文件）。

### 4.3 NetCDF 元数据（CF/UGRID）

- 全局属性：`Conventions="CF-1.10, UGRID-1.0"`、`title`、`history`、`forcing_product` 等。
- `ele` 文件写 UGRID mesh：
  - node coords、face connectivity、face center coords（可选但建议）
  - `mesh` topology variable（`cf_role="mesh_topology"` 等）
- time 轴：
  - `time` 维无限长
  - `time.units="minutes since YYYY-MM-DD 00:00:00 UTC"`（基于 `<prj>.tsd.forc` 的 `ForcStartTime`）
  - **time 值使用现有 Print_Ctrl 的 “left endpoint (t-Interval)” 语义**，保持与 legacy 对齐。

### 4.4 变量命名与单位（先对齐 legacy，再逐步友好化）

第一版优先“完整 + 可回归”：

- NetCDF 变量名使用 legacy 文件名后缀（如 `eleygw`, `elevprcp`, `rivqdown`），并附加：
  - `long_name`（从变量类型推导/表驱动）
  - `units`（按 IO.cpp 的命名约定推导：`y`=m, `v`=m/day, `q`=m3/day）

后续（可选）再做一层“友好别名”（例如 `groundwater_head`），但不阻塞主目标。

### 4.5 SHUD 输出配置（`<prj>.cfg.ncoutput`）

最少键：

- `OUTPUT_MODE LEGACY|NETCDF|BOTH`
- `OUTPUT_NETCDF_DIR <path>`
- `NETCDF_FORMAT NETCDF4|NETCDF4_CLASSIC`（默认 `NETCDF4_CLASSIC`）
- `DEFLATE_LEVEL 0-9`（默认 4）
- `CHUNK_TIME 1`（默认 1，保证 time‑append 友好）

---

## 5. 父仓库 tools/shudnc.py 改造（支撑单入口）

在 `tools/shudnc.py` 增强：

- 新增命令：`render-shud-cfg`（仅生成/展示将写入的 `.cfg.forcing`/`.cfg.ncoutput` 与 `.cfg.para` patch）
- `run --profile nc` 时：
  1) 运行 AutoSHUD Step1–Step3（维持静态输入生产）
  2) 写入 `input/<prj>/<prj>.cfg.forcing`、`input/<prj>/<prj>.cfg.ncoutput`
  3) append/patch `input/<prj>/<prj>.cfg.para` 增加 `FORCING_MODE/OUTPUT_MODE/FORCING_CFG/...`
  4) 调用 `SHUD/shud <prj>` 跑模型
- `validate`：
  - baseline：检查 HWSD/USGS/CMFD 目录存在（已有逻辑）
  - nc：额外检查 NetCDF forcing `data_root`、关键子目录/文件 pattern、cfg 生成路径。

---

## 6. 测试用例与回归场景

### 6.1 最小回归（必须）

- 用 QHH case，把 `<prj>.cfg.para` 的 `END` 临时调小（例如 2–10 天）做快速回归：
  - baseline：CSV forcing + legacy output
  - nc：NetCDF forcing + legacy output（阶段 A）
  - nc：NetCDF forcing + NetCDF output（阶段 B）
- 对比：
  - 抽 3 个 forcing 点、2 个时刻：5 个 forcing 变量逐项对齐
  - 抽 10 个 element：`eleygw/eleveta/rivqdown` 等关键输出对齐（允许极小浮点差）

### 6.2 覆盖关键边界（建议）

- 跨月（2017-01-31→2017-02-01）forcing 文件切换
- lon 0–360 vs -180–180（ERA5/其他产品可能）
- lat 递增/递减
- 缺测值（_FillValue/NaN）：默认 fail-fast 并报清晰错误（指出文件/变量/时间/格点）

---

## 7. 默认选择与假设（锁定）

- forcing 插值：`NEAREST`（优先回归一致）
- NetCDF 输出布局：3 文件（ele/riv/lake）
- SHUD 新配置格式：沿用 `.cfg`（KEY VALUE），不引入 YAML 解析依赖
- baseline pipeline 保持：不要求对 upstream 提 PR；只在 DankerMu 的仓库内提 issue/PR 与合并

