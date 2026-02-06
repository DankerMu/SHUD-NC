# AutoSHUD 项目功能与 SHUD 衔接（深度说明）

> 适用读者：第一次接触 AutoSHUD/SHUD，希望搞清楚“AutoSHUD到底做什么、产出什么、SHUD如何消费这些产物、哪些东西必须有、哪些可以替换（例如 forcing 读 NetCDF）”的人。  
> 本文基于当前仓库 `AutoSHUD/` 脚本与同级目录 `SHUD/` 源码的实际实现（C++ 读入逻辑、文件命名与字段要求）。

---

## 1. 一句话定位：AutoSHUD 是什么？不是什​​么？

**AutoSHUD 是一套 R 脚本流水线**，把用户提供的研究区空间数据（边界/河网/DEM/投影）和可选的全球/区域数据源（LDAS/CMFD/SoilGrids/HWSD/NLCD/USGS 等）整理、裁剪、投影、提取、参数化，最终生成 **SHUD 模型可以直接运行的输入文件集**。

它不是：
- SHUD 本体（SHUD 是 `../SHUD/` 的 C/C++ 求解器）。
- 一个“只靠 forcing NetCDF 就能跑起来”的系统：**SHUD 运行还需要网格、属性映射、参数表、初值、配置等大量静态输入**，这些通常由 AutoSHUD 的 Step1–Step3 生成。

---

## 2. 全局视角：数据流（从原始数据到 SHUD 运行）

可以把整个流程理解成四层产物：

1) **原始输入（用户/外部数据）**  
`WBD(边界.shp)`、`STM(河网.shp)`、`DEM(dem.tif)`、（可选）`LAKE(lake.shp)`、  
（可选）forcing 的 NetCDF 数据目录（NLDAS/GLDAS/CMFD/CMIP6…）、  
（可选）土壤/土地利用的全球栅格与属性表。

2) **预处理数据（Predata，中间产物）**：`dir.out/DataPre/`  
包括裁剪/投影后的 DEM、边界缓冲、河网简化、forcing 覆盖网格（meteoCov），以及 soil/geol/landuse 的裁剪结果与属性表（`SOIL.csv/GEOL.csv/LANDUSE.csv` 等）。

3) **SHUD 输入文件（最终交付给求解器）**：`dir.out/input/<prjname>/`  
这一步是 **AutoSHUD 与 SHUD 的“握手点”**：AutoSHUD 生成的文件名与字段结构，必须匹配 SHUD 源码的读入逻辑。

4) **SHUD 运行输出（结果）**：`dir.out/output/<prjname>.out/`  
由 SHUD 求解器导出（多为二进制 `.dat` 与可选 `.csv`），然后可被 rSHUD/AutoSHUD Step5 读取绘图与诊断。

---

## 3. AutoSHUD 仓库结构（你应该先看哪些文件）

顶层脚本（流水线入口）：
- `GetReady.R`：读取项目配置、构造目录与预处理文件路径表、加载依赖包（几乎所有 Step 都 `source()` 它）。
- `Step1_RawDataProcessng.R`：原始空间数据标准化（裁剪、投影、缓冲、河网清理等）。
- `Step2_DataSubset.R`：土壤/地质/土地利用/forcing 数据裁剪与整理（调用大量 `Rfunction/` 与 `SubScript/`）。
- `Step3_BuidModel.R`：生成 SHUD 的核心输入文件（mesh/att/riv/para/cfg/tsd…）。
- `Step4_SHUD.R`：尝试下载/编译/运行 SHUD（脚本偏“示例性质”，实际项目常改为用同级 `../SHUD/` 已有源码）。
- `Step5_ResultVisualization.R`、`Step5_WaterBalance.R`：读取 SHUD 输出并做分析/水量平衡。
- `All.R`：简单串联 Step1–Step3。

功能模块：
- `Rfunction/`：可复用函数（GDAL wrapper、ReadProject、forcing/NetCDF 处理、单位换算等）。
- `SubScript/`：分支流程脚本（不同 soil/landuse/forcing 数据源的实现，以及 lake 模块、分析脚本等）。
- `Table/`：类别查找表（例如 `Table/USGS_GLC.csv`、`Table/nlcd.csv`）。
- `Example/`：示例项目配置与小型数据。

---

## 3.1 运行环境与依赖（跑通 Step1–Step3 的前提）

### 3.1.1 R 侧依赖
AutoSHUD 不是一个打包好的 R package，而是脚本集合；依赖主要在 `GetReady.R` 与 Step2 的各子脚本里。

常见依赖（以代码中 `library()/require()` 为准）：
- 空间/GIS：`raster`、`sp`、`rgdal`、`rgeos`、`terra`（部分脚本）、`deldir`（Voronoi）
- SHUD 工具：`rSHUD`（负责 mesh/att/riv 写入与读写工具）
- 时序/绘图：`xts`、`lattice`、`ggplot2`、`hydroTSM`、`hydroGOF`
- NetCDF：`ncdf4`（LDAS/CMFD/CMIP6 等 forcing 处理脚本）
- 其他：`lubridate`、`abind` 等（视具体 forcing 脚本而定）

> 备注：`rgdal`/`rgeos` 在新版本 R/CRAN 生态中已退役，很多环境需要从系统包或特定渠道安装；如果你计划长期维护，可考虑逐步迁移到 `sf`/`terra`。

### 3.1.2 系统依赖（必须）
- **GDAL 命令行工具**：脚本直接调用 `gdalwarp`/`gdal_merge.py`（见 `Rfunction/gdalwarp.R`）。  
  你需要保证这些命令在 `PATH` 里可用。

### 3.1.3 可选依赖
- `whitebox`（R 包）及其 backend：用于 `Setp0.1_Delineation.R` 的自动流域划分（可选功能，不是主流程必需）。

---

## 4. 项目配置文件：`*.autoshud.txt`（AutoSHUD 的“控制面板”）

### 4.1 读入方式与基本规则
`GetReady.R` 会从命令行参数读取配置文件路径：
- `Rscript Step1_RawDataProcessng.R Example/9035800.autoshud.txt`
- 如果不传参数，默认使用 `Example/9035800.autoshud.txt`

`Rfunction/ReadProject.R:read.prj()` 读取规则：
- 以“**第一列是键，第二列是值**”的形式解析（制表符或空格分隔）。
- 以 `#` 开头的行、空行会被忽略。
- 不支持带空格的路径（除非你确保分隔解析不被破坏）；建议路径避免空格。

### 4.2 关键字段（按用途分组）
下面用 `Example/9035800.autoshud.txt` 的字段做解释（不同项目可增删）：

**项目与时间**
- `prjname`：项目名（SHUD 的 project name），会决定 `input/<prjname>`、`output/<prjname>.out`。
- `startyear / endyear`：forcing/LAI/MF 等时间范围构建依据。
- `STARTDAY / ENDDAY`：写入 SHUD 的 `cfg.para`，控制模拟时间窗（单位：天，从 forcing 起始日算）。

**目录（决定 AutoSHUD 输出落在哪）**
- `dir.out`：部署目录根（AutoSHUD 会在其下创建 `DataPre/`、`input/`、`output/` 等）。
- `dout.forc`：forcing 的 CSV 输出目录（通常位于 `dir.out/forcing`，也可独立指定）。
- `dir.ldas`：外部 forcing NetCDF 原始数据目录（NLDAS/GLDAS/CMFD/CMIP6 等时使用）。
- `dir.soil`：外部土壤数据目录（global soil 时使用）。

**空间输入（用户必须/建议提供）**
- `fsp.wbd`：流域/行政边界 polygon shapefile。
- `fsp.stm`：河网 polyline shapefile。
- `fr.dem`：DEM raster（GeoTIFF）。
- `fsp.lake`：可选，湖泊 polygon shapefile（存在则启用 lake 模块）。

**数据源开关（决定 Step2 用哪套脚本）**
- `Forcing`：
  - `-1`：Dummy（不提供 forcing，Step3 会用缓冲区当 forcing 覆盖但没有真实时序）
  - `0.x`：LDAS/CMFD/CMIP6 等网格数据（通过 NetCDF 抽取生成 forcing CSV）
  - `1.x`：本地气象站/覆盖面（通过 `fsp.forc` 指向站点 shapefile）
- `Soil`：
  - `<1`：使用 global soil 数据（HWSD / ISRIC SoilGrids / SSURGO…）
  - `>=1`：使用本地 soil/geol 栅格+属性表（`fn.soil/fn.geol/fa.soil/fa.geol`）
- `Landuse`：
  - `0.1`：USGS GLC
  - `0.2`：NLCD
  - `>=1`：本地 landuse

**网格与数值控制（影响 Step3 生成网格与 SHUD 配置）**
- `NumCells`：期望网格单元数量（Step3 会换算为最大单元面积）。
- `MaxArea`：单元最大面积上限（km²，脚本内部会转成 m²）。
- `MinAngle`：三角剖分最小角度约束。
- `AqDepth`：含水层深度（用于 mesh 的 AqD）。
- `tol.wb`：边界简化容差。
- `tol.rivlen`：河段切分/简化的长度阈值。
- `RivWidth / RivDepth`：河道类型参数缩放/设定。
- `DistBuffer`：边界缓冲距离（影响裁剪范围与 forcing/soil/landuse 的外扩取数）。
- `flowpath`：是否做河网流向一致性/重建（脚本里有开关但部分路径被覆盖，需谨慎）。
- `QuickMode`：快速模式（不从 soil/geol 栅格细算参数，用默认 PTF 方案）。
- `MAX_SOLVER_STEP / CRYOSPHERE`：写入 SHUD 的 `cfg.para`，影响求解器步长与冻土开关。

---

## 5. GetReady.R：所有 Step 的“环境初始化器”

你可以把 `GetReady.R` 理解成：
1) 读取项目文件 → 得到 `xfg`（全局配置 list）。
2) 构造一套“预处理文件路径表”：
   - `pd.pcs`：投影坐标系（PCS）下的预处理文件（`DataPre/pcs/`）
   - `pd.gcs`：地理坐标系（GCS, EPSG:4326）下的预处理文件（`DataPre/gcs/`）
   - `pd.att`：属性表输出文件（如 `DataPre/SOIL.csv`、`DataPre/GEOL.csv`、`DataPre/LANDUSE.csv`）
3) 创建目录（`dir.out/DataPre`、`dir.out/input/<prj>`、`dir.out/output/<prj>.out`、`dout.forc`…）
4) 加载依赖包（`raster/sp/rgdal/rgeos/rSHUD/...`）。

在代码里最重要的几个对象：
- `xfg`：配置（来自 `Rfunction/ReadProject.R`）
- `pd.pcs$wbd / pd.pcs$dem / pd.pcs$stm / pd.pcs$meteoCov ...`：后续 Step 读写的“标准文件名”

---

## 6. Step1：原始空间数据标准化（RawDataProcessing）

### 6.1 目标
把用户提供的边界/河网/DEM 统一到工程内的标准路径与坐标系统，并生成缓冲区与基础 QC 图，供 Step2/Step3 使用。

### 6.2 主要输入
- `xfg$fsp.wbd`（边界 shp）
- `xfg$fsp.stm`（河网 shp）
- `xfg$fr.dem`（DEM tif；若缺失，脚本可能尝试从 ASTER GDEM 下载/生成）
- `xfg$crs.pcs`（投影坐标系；默认由边界推导 Albers）
- `xfg$para$DistBuffer`

### 6.3 核心处理（按顺序）
1) **边界修复与投影**
   - `gBuffer(width=0)` 修复自交/无效 polygon
   - dissolve、remove holes
   - 输出 `DataPre/pcs/wbd.shp`、`DataPre/pcs/wbd_buf.shp`，并同步生成 GCS 版本到 `DataPre/gcs/`
2) **DEM 裁剪与投影**
   - `Rfunction/gdalwarp.R:fun.gdalwarp()` 包装调用 `gdalwarp`  
   - 以 `wbd_buf` 为 cutline 裁剪
   - 输出：`DataPre/pcs/dem.tif`、`DataPre/gcs/dem.tif`
3) **河网投影与清理**
   - `spTransform` 到 PCS
   - 可选简化、去重、流向路径处理（`sp.RiverPath` 等）
   - 输出：`DataPre/pcs/stm.shp`
4) **可选湖泊处理**
   - 若配置了 `fsp.lake`：remove holes、投影，输出 `DataPre/pcs/lake.shp` 与 `DataPre/gcs/lake.shp`
5) **QC 图**
   - 输出如 `dir.out/Image/S1_Rawdata_Elevation.png`

### 6.4 产物清单（典型）
- `DataPre/pcs/wbd.*`
- `DataPre/pcs/wbd_buf.*`
- `DataPre/pcs/dem.tif`
- `DataPre/pcs/stm.*`
- （可选）`DataPre/pcs/lake.*`
- 同名的 `DataPre/gcs/` 版本

---

## 7. Step2：数据裁剪与整理（Soil / Landuse / Forcing）

`Step2_DataSubset.R` 通过 `irun = data.frame(soil=1, landuse=1, forcing=1)` 控制是否执行三大模块。每个模块都会把“外部大数据”裁剪到 `wbd_buf` 范围，并生成 Step3 所需的栅格与属性表/时序文件。

### 7.1 Soil/Geol 模块（`xfg$isoil`）
**目标**：得到
- `DataPre/pcs/soil.tif`、`DataPre/pcs/geol.tif`
- 对应属性表：`DataPre/SOIL.csv`、`DataPre/GEOL.csv`（列通常是 SILT/CLAY/OM/BD 等纹理或派生参数中间量）

分支示例（以当前代码为准）：
- `isoil == 0.1`：HWSD（`SubScript/Sub_iSoil_0.2.R`：裁剪 HWSD 并提取 Soil/Geol 属性）
- `isoil == 0.2`：ISRIC SoilGrids（`SubScript/Sub2.1_Soil_ISRIC_SoilGrids.R`：裁剪各层 tif 并生成 RDS 中间结果）
- `isoil == 0.3`：USDA SSURGO（`SubScript/Sub2.1_Soil_SSURGO.R`）
- `isoil >= 1`：本地 soil/geol 栅格+属性表（`SubScript/Sub_iSoil_1.1.R`）

核心函数：`Rfunction/Fun.Soil_Geol.R:fun.Soil_Geol()`  
它会：
- 读取栅格与属性表
- 对栅格的类别 ID 重映射（保证 1…N 连续）
- 输出裁剪/投影后的 soil/geol 栅格到 `pd.pcs$soil.r` / `pd.pcs$geol.r`
- 输出属性表到 `pd.att$soil` / `pd.att$geol`

### 7.2 Landuse 模块（`xfg$ilanduse`）

**目标**：得到 landuse 栅格（PCS）与 landcover 参数表，使 Step3 能为每个网格单元赋值 `iLC`，并在 SHUD 中通过 `.para.lc` 取得物理参数。

典型输出：
- `DataPre/pcs/landuse.tif`：原始 landuse 类别栅格（投影/裁剪后）
- `DataPre/pcs/landuse_idx.tif`：可选，把原始类别重映射为 1…N 的连续索引（便于参数表索引）
- `DataPre/LANDUSE.csv`（或 `pd.att$landuse`）：landcover 参数/属性表

分支示例：
- `ilanduse == 0.1`：USGS GLC（`SubScript/Sub2.2_Landcover_GLC.R`）
  - 用 `fun.gdalcut()` 裁剪/投影 `xfg$fn.landuse` 到 `pd.pcs$lu.r`
  - landcover 参数表通常直接用 `Table/USGS_GLC.csv`
  - 注意：USGS GLC 类别常从 0 开始，Step3 会用 `r.lc + 1` 转成 1-based
- `ilanduse == 0.2`：NLCD（`SubScript/Sub2.2_Landcover_nlcd.R`）
  - 裁剪 `xfg$fn.landuse` 到 `pd.pcs$lu.r`
  - 读取 `Table/nlcd.csv`，把出现的 NLCD 类别重映射为连续 ID（写 `pd.pcs$lu.idx`）
  - 写 landcover 属性表 `pd.att$landuse`
- `ilanduse >= 1`：本地 landuse（当前代码里未展开，通常需要你补齐“裁剪/投影 + 类别表”）

### 7.3 Forcing 模块（`xfg$iforcing`）

这是 AutoSHUD 与 SHUD 连接里最容易让人混淆的一部分：**SHUD 并不直接读 NetCDF**（当前版本），而是读：
1) 一个“forcing 索引文件”`<prj>.tsd.forc`（列出 forcing 点与其 CSV 文件名），以及  
2) 若干个“forcing 时序文件”`*.csv`（每个 forcing 点一个时序表，或多个点共享同名文件但路径不同）。

#### 7.3.1 forcing 的三个对象（强烈建议先形成这个心智模型）

1) **forcing 点（Sites）**：一组点坐标（Lon/Lat/X/Y/Z），每个点有一个 ID 和一个时序文件名。  
在 AutoSHUD 中由 `rSHUD::ForcingCoverage()` 构造（它会把点坐标附到一个 polygon coverage 的 `@data` 表里）。

2) **forcing 覆盖面（Coverage polygons）**：把整个流域划分为多个 polygon，每个 polygon 绑定一个 forcing 点（通常是 Voronoi）。  
Step3 在生成 `.sp.att` 时，会把每个网格单元落到哪个 polygon 里，从而确定该单元用哪个 forcing 点（即 `iForc`）。

3) **forcing 时序（CSV）**：每个 forcing 点一个 CSV（或按你项目约定）。  
SHUD 的 C++ 会根据 `.tsd.forc` 里给的 `path + Filename` 去读取 CSV，并按列序解释为：降水/温度/RH/风/辐射。

#### 7.3.2 `iforcing` 分支（AutoSHUD 内部逻辑）

在 `Step2_DataSubset.R` 与若干脚本中，forcing 大致分：
- `iforcing < 0`：Dummy（不做真实时序；Step3 会用流域缓冲区作为 forcing 覆盖，但缺 forcing CSV 会导致 SHUD 运行失败或只能做 dummy 模式）
- `iforcing == 0.x`：网格 forcing（LDAS/CMFD/CMIP6 等）
  - Step2 负责：从 NetCDF 子集提取时序 → 单位换算 → 输出每个格点的 forcing CSV
  - 同时需要生成 `DataPre/*/meteoCov.shp`（格点/网格覆盖，用于 Step3）
- `iforcing >= 1`：本地气象站/覆盖面 forcing
  - `fsp.forc` 指向站点 shapefile（或 coverage polygon），然后你需要准备与站点 ID 对应的 forcing CSV

> 注意：仓库里存在两套“生成 meteoCov + 生成 CSV”的实现路径：  
> - `SubScript/Sub2.3_Forcing_LDAS.R`（先生成 meteoCov，再调用各 `Rfunction/*_nc2RDS.R` 与 `*_RDS2csv.R`）  
> - 部分 `Rfunction/*_nc2RDS.R` 自身也会生成 meteoCov（例如 `Rfunction/GLDAS_nc2RDS.R`）  
> 实际使用时要确保：**Step3 需要的 `pd.pcs$meteoCov` 确实被生成，并且 CSV 命名与 Step3 的 ID/filename 规则一致。**

#### 7.3.3 forcing CSV 的格式（SHUD 实际怎么读）

SHUD 的 `_TimeSeriesData`（`../SHUD/src/classes/TimeSeriesData.*`）读 CSV 的关键点：
- 第一列是时间（单位：**天**，可以是小数表示小时/分钟分辨率），读入时会乘以 1440 转成分钟。
- 列名不影响计算，SHUD 只按固定列序取值（见 `../SHUD/src/Model/Macros.hpp`）：
  - `i_prcp=1`、`i_temp=2`、`i_rh=3`、`i_wind=4`、`i_rn=5`
- 所以 CSV 必须在时间列之后提供 **5 列 forcing 变量**，顺序固定。

rSHUD 的 `write.tsd()`（`../rSHUD/R/writeInput.R`）会写出 SHUD 能读的格式：  
首行含数据维度与起始日期（SHUD 只读前三个字段，后面字段会被忽略），然后是表头与数据行。

---

## 8. Step3：生成 SHUD 输入文件（AutoSHUD 与 SHUD 的关键衔接点）

`Step3_BuidModel.R` 是整个 AutoSHUD 的核心：它把 Step1/2 的空间栅格与属性表、forcing 覆盖、河网等“中间产物”，转换为 SHUD 求解器直接读取的输入文件集合。

### 8.1 输入依赖（Step3 运行前你应检查）
- `DataPre/pcs/wbd.*`、`DataPre/pcs/wbd_buf.*`
- `DataPre/pcs/dem.tif`
- `DataPre/pcs/stm.*`
- （若非 QuickMode）`DataPre/pcs/soil.tif`、`DataPre/pcs/geol.tif` 与 `DataPre/SOIL.csv`、`DataPre/GEOL.csv`
- landuse：`DataPre/pcs/landuse.tif`（以及可能的 `landuse_idx.tif`）
- forcing：
  - 网格 forcing：`DataPre/pcs/meteoCov.*`（格点覆盖） + `dout.forc/*.csv`
  - 本地站点：`xfg$fsp.forc`（站点 shp） + `dout.forc/*.csv`

### 8.2 网格（mesh）生成逻辑
主要步骤：
1) 读取流域边界 `wbd` 与 DEM（PCS）
2) 根据目标单元数/最大面积确定 `a.max`：  
   `a.max = min(AA / NumCells, MaxArea)`（单位：m²）
3) 简化边界（`gSimplify`），构造三角剖分 `tri = shud.triangle(...)`
4) 生成 SHUD 网格 `pm = shud.mesh(tri, dem, AqDepth=...)`
5) 输出可视化 shapefile：`input/<prj>/gis/domain.*`

### 8.3 河网与河段（riv / rivseg）
1) 读取 `DataPre/pcs/stm.*`
2) 可选 flowpath 清理与去重（脚本里有开关）
3) 按长度阈值切分河段：`spr = sp.CutSptialLines(..., tol=tol.rivlen)`
4) 构建 SHUD 河道对象：`pr = shud.river(spr, dem)`
   - 并按配置缩放宽度/深度：`RivWidth / RivDepth`
5) 生成“河段-网格单元”映射：
   - `sp.seg = sp.RiverSeg(spm, spr)`（把河线切进三角网格）
   - `prs = shud.rivseg(sp.seg)`（写入 `.sp.rivseg`）
6) 输出 GIS shapefile：`input/<prj>/gis/river.*`、`input/<prj>/gis/seg.*`

### 8.4 forcing 覆盖与 `.tsd.forc`
Step3 会生成两样东西：
1) **forcing 覆盖 polygon（sp.forc）**：用于 `.sp.att` 的 `iForc` 赋值  
2) **forcing 索引文件 `<prj>.tsd.forc`**：告诉 SHUD 每个 forcing 点的坐标与 CSV 文件名

分支（与 `iforcing` 一致）：
- 若 `iforcing < 1`：
  - 读取 `DataPre/pcs/meteoCov.shp`（或 dummy 情况下用 `wbd_buf`）
  - 为每个格点 polygon 构造 `ID = X<xcenter>Y<ycenter>`，并以该 ID 生成默认 `Filename = ID.csv`
  - 取 polygon 质心作为 forcing 点坐标 → `ForcingCoverage()` 生成 Voronoi coverage
- 若 `iforcing >= 1`：
  - 读取用户提供的 `fsp.forc` 站点点集
  - `ForcingCoverage()` 生成 coverage（并把站点 ID 映射为文件名）

最终写入：
- `<dir.modelin>/<prj>.tsd.forc`（通过 `rSHUD::write.forc()`）
  - 第 1 行：`NumForc  YYYYMMDD`（起始日）
  - 第 2 行：`path`（通常是 `dout.forc`）
  - 后续：`ID Lon Lat X Y Z Filename`

> 关键约束：`Filename` 必须在 `path` 下真实存在，否则 SHUD 读 forcing 会报错。

### 8.5 生成 `.sp.att`（元素属性索引：把“空间数据”接到“参数表”）

`.sp.att` 是 SHUD 输入里最“枢纽”的文件之一：它决定每个三角单元用哪一类 soil/geol/landcover/forcing（以及 MF/BC/SS/lake 等）。

Step3 的主要调用：
- landuse：`r.lc = raster(pd.pcs$lu.r)`；USGS GLC 会转成 1-based
- 若 QuickMode：soil/geol/forcing 直接用常数 1
- 否则：
  - `r.soil = raster(pd.pcs$soil.r)`
  - `r.geol = raster(pd.pcs$geol.r)`
  - `r.forc = sp.forc`（coverage polygon）
  - `pa = shud.att(tri, r.soil=..., r.geol=..., r.lc=..., r.forc=sp.forc, r.BC=0, sp.lake=...)`
- 缺失值处理：把 NA 用中位数/均值补齐（防止 SHUD 读入时报错）

SHUD 侧读入字段要求（`../SHUD/src/ModelData/MD_readin.cpp:read_att`）：
- 必须 9 列（示意）：
  1. index（可忽略）
  2. iSoil
  3. iGeol
  4. iLC
  5. iForc
  6. iMF
  7. iBC
  8. iSS
  9. Lake

### 8.6 生成参数表：`.para.soil / .para.geol / .para.lc`

Step3 会把 Step2 的 soil/geol 纹理信息转成 SHUD 可用的物理参数表（PTF 推导）：
- soil：`PTF.soil(...)` → 写 `<prj>.para.soil`
- geol：`PTF.geol(...)` → 写 `<prj>.para.geol`
- landcover：读取 `Table/USGS_GLC.csv` 或 `Table/nlcd.csv` 等 → 写 `<prj>.para.lc`

SHUD 读入时会做单位转换（例如渗透系数从 m/day → m/min，见 `read_soil/read_geol` 里 `/1440`），因此 Step3 输出的单位必须与 SHUD 预期匹配。

### 8.7 LAI / RL / MF：`.tsd.lai / .tsd.rl / .tsd.mf`
Step3 会生成：
- `tsd.lai`：不同 landcover 类别的 LAI 时序（按列对应 iLC）
- `tsd.rl`：粗糙度长度时序（当前 SHUD 代码里对 RL 的使用有注释掉的部分，但文件仍会生成/可扩展）
- `tsd.mf`：融雪因子时序（按列对应 iMF）

这些文件都用 `rSHUD::write.tsd()` 输出成 SHUD `_TimeSeriesData` 能读的格式。

### 8.8 初值与配置：`.cfg.ic / .cfg.para / .cfg.calib`

- `cfg.para`：控制仿真起止、求解器步长、输出间隔等  
  - Step3 会设置 `START/END/MAX_SOLVER_STEP/CRYOSPHERE` 等
  - SHUD 在 `Control_Data::read()` 中解析（`../SHUD/src/classes/Model_Control.cpp`）
- `cfg.calib`：校准因子/倍率（`globalCal::read()` 解析）
- `cfg.ic`：初始状态（元素/河道/湖泊水位等）  
  - Step3 默认把 `INIT_MODE` 设为 `3`（即“从 cfg.ic 读入”）
  - SHUD 在 `Model_Data::LoadIC()` 中读取（`../SHUD/src/ModelData/MD_initialize.cpp`）

---

## 9. Step4/Step5：运行与分析（理解即可，不是衔接核心）

### 9.1 Step4_SHUD.R 的定位与现实建议
`Step4_SHUD.R` 的逻辑是：clone SHUD → make → 运行。  
但在你的工程结构里，SHUD 代码已在同级 `../SHUD/`，更常见的做法是：
1) 在 `../SHUD/` 编译得到 `shud` 二进制
2) 切到 AutoSHUD 的部署目录 `dir.out`，直接运行 `shud <prjname>`

为什么可行？因为 AutoSHUD 的 `dir.out` 默认创建了与 SHUD 期望一致的目录结构：
- `dir.out/input/<prjname>/...`
- `dir.out/output/<prjname>.out/...`

### 9.2 推荐运行方式（最少踩坑）
假设你的项目配置里 `dir.out = /path/deploy9035800`，则：

1) 先跑 AutoSHUD 生成输入：
```bash
Rscript Step1_RawDataProcessng.R /path/to/your.autoshud.txt
Rscript Step2_DataSubset.R /path/to/your.autoshud.txt
Rscript Step3_BuidModel.R /path/to/your.autoshud.txt
```

2) 编译 SHUD（一次即可）：
```bash
cd ../SHUD
make clean
make shud
```

3) 在部署目录运行（推荐）：
```bash
cd /path/deploy9035800
/absolute/path/to/SHUD/shud 9035800
```

> 这时 SHUD 会自动寻找 `./input/9035800/9035800.*`，并把结果写到 `./output/9035800.out/`。

### 9.3 Step5 分析能做什么
- `Step5_ResultVisualization.R`：用 rSHUD 读取输出并做时序/空间图（脚本里有 `stop()`，更像示例/开发状态）
- `Step5_WaterBalance.R`：基于输出计算水量平衡误差、汇总 P/E/Q/ΔS 等诊断

---

## 10. AutoSHUD → SHUD：衔接“合同”（文件、字段与索引关系）

这一节是理解与改造的基础：你只要牢牢记住 **SHUD 读哪些文件、文件长什么样、索引怎么串起来**，就能判断“哪些东西必须由 AutoSHUD 提供、哪些可以替换为 NetCDF 直读”。

### 10.1 SHUD 输入文件的命名规则（硬编码）
SHUD 在 `FileIn::setInFilePath()`（`../SHUD/src/classes/IO.cpp`）里硬编码了文件名：
- `<inpath>/<prj>.sp.mesh`
- `<inpath>/<prj>.sp.att`
- `<inpath>/<prj>.sp.riv`
- `<inpath>/<prj>.sp.rivseg`
- `<inpath>/<prj>.para.soil`
- `<inpath>/<prj>.para.geol`
- `<inpath>/<prj>.para.lc`
- `<inpath>/<prj>.cfg.para`
- `<inpath>/<prj>.cfg.calib`
- `<inpath>/<prj>.cfg.ic`
- `<inpath>/<prj>.tsd.forc`
- `<inpath>/<prj>.tsd.lai`
- `<inpath>/<prj>.tsd.mf`
- `<inpath>/<prj>.tsd.rl`（预留）
…

AutoSHUD Step3 正是通过 `rSHUD::shud.filein()` 生成同名路径，然后 `write.mesh/write.df/write.config/write.tsd/write.forc` 写出这些文件。

### 10.2 “谁生成、谁读取、用来干什么”对照表

| 文件 | AutoSHUD 生成（Step/函数） | SHUD 读取位置 | 作用（你要理解的重点） |
|---|---|---|---|
| `<prj>.sp.mesh` | Step3：`shud.triangle` + `shud.mesh` + `write.mesh` | `Model_Data::read_mesh` | 三角网格拓扑 + 节点坐标/高程/AqD |
| `<prj>.sp.att` | Step3：`shud.att` + `write.df` | `Model_Data::read_att` | 每个单元的类别索引（iSoil/iGeol/iLC/iForc…） |
| `<prj>.sp.riv` | Step3：`shud.river` + `write.riv` | `Model_Data::read_riv` | 河道网络（上下游、类型、坡度、长度、BC…） |
| `<prj>.sp.rivseg` | Step3：`sp.RiverSeg` + `shud.rivseg` + `write.df` | `Model_Data::read_rivseg` | 河段与单元的耦合映射（决定河-坡面交换） |
| `<prj>.para.soil` | Step3：`PTF.soil` + `write.df` | `Model_Data::read_soil` | soil 类别参数表（被 iSoil 引用） |
| `<prj>.para.geol` | Step3：`PTF.geol` + `write.df` | `Model_Data::read_geol` | geology 类别参数表（被 iGeol 引用） |
| `<prj>.para.lc` | Step3：表格或推导 + `write.df` | `Model_Data::read_lc` | landcover 类别参数表（被 iLC 引用） |
| `<prj>.cfg.para` | Step3：`shud.para` + `write.config` | `Control_Data::read` | 控制仿真时间/步长/输出频率/开关 |
| `<prj>.cfg.calib` | Step3：`shud.calib` + `write.config` | `globalCal::read` | 校准倍率/偏置（雨、温度、ET、河道等） |
| `<prj>.cfg.ic` | Step3：`shud.ic` + `write.ic` | `Model_Data::LoadIC` | 初始状态（元素/河道/湖泊） |
| `<prj>.tsd.forc` | Step3：`ForcingCoverage` + `write.forc` | `Model_Data::read_forc_csv` | forcing 点列表 + 指向 CSV 文件 |
| `dout.forc/*.csv` | Step2：NetCDF→CSV 或用户准备 | `_TimeSeriesData::read_csv` | forcing 时序本体（列序固定） |
| `<prj>.tsd.lai` | Step3：`write.tsd` | `Model_Data::read_lai` | LAI 时序（按列对应 iLC） |
| `<prj>.tsd.mf` | Step3：`write.tsd` | `Model_Data::read_mf` | 融雪因子时序（按列对应 iMF） |

### 10.3 `.tsd.forc` 里到底是什么信息？
`.tsd.forc` 是一个“索引文件”（不是时序），结构如下（与 `rSHUD::write.forc()`/`SHUD::read_forc_csv()`一致）：

1. 第 1 行：`NumForc  ForcStartTime(YYYYMMDD)`  
2. 第 2 行：`path`（forcing CSV 的公共目录）  
3. 第 3 行：表头（通常 `ID Lon Lat X Y Z Filename`）  
4. 后续 NumForc 行：每个 forcing 点一行，含坐标与文件名

SHUD 运行时会把 `path + "/" + Filename` 拼起来，然后逐个读入对应 CSV。

### 10.4 `.sp.att` 的“索引链路”（理解 SHUD 输入的核心）
`.sp.att` 把每个三角单元的类别索引串到各参数表/时序：
- `iSoil` → `.para.soil` 的行号
- `iGeol` → `.para.geol` 的行号
- `iLC`   → `.para.lc` 的行号，同时也用于 `.tsd.lai`（列索引）
- `iForc` → `.tsd.forc` 的行号（从而找到该单元用哪个 forcing CSV）
- `iMF`   → `.tsd.mf` 的列索引

因此，只要你改变其中任何一个“表/时序”的组织方式，都必须保证 `.sp.att` 的索引仍然有效。

### 10.5 SHUD 输入文件的结构与字段（速查）

#### 10.5.1 TabularData 文件块（`.sp.* / .para.* / .cfg.ic` 的基础结构）
SHUD 的 `TabularData`（`../SHUD/src/classes/TabularData.*`）读取格式固定：
1) 第 1 行：`nrow ncol`
2) 第 2 行：表头字符串（通常是列名，用于提示；SHUD 不强依赖列名）
3) 后续 `nrow` 行：每行 `ncol` 个数值（以空格或 tab 分隔）

AutoSHUD/rSHUD 的 `write.df()` 会按该规则写出；当一个文件里连续写了多个表（例如 `.sp.mesh`、`.sp.riv`、`.cfg.ic`），SHUD 会多次调用 `tb.read(fp)` 依次读出每个表块。

#### 10.5.2 `<prj>.sp.mesh`（网格）
SHUD 读入：`Model_Data::read_mesh()`  
文件包含 **两个 TabularData 块**：

块 1：Elements（每个三角单元一行，关键字段）
- `index`
- `Node1 Node2 Node3`：三角形三个节点编号
- `nabr1 nabr2 nabr3`：三个相邻单元编号（边界处可能为 0 或 -1，取决于写出约定）

块 2：Nodes（每个节点一行，关键字段）
- `index`
- `x y`：节点平面坐标（PCS）
- `AqD`：含水层深度
- `zmax`：地表高程

#### 10.5.3 `<prj>.sp.att`（元素属性索引）
SHUD 读入：`Model_Data::read_att()`（要求 9 列）
- `index`
- `iSoil iGeol iLC iForc`：分别索引到 `.para.soil/.para.geol/.para.lc/.tsd.forc`
- `iMF`：索引到 `.tsd.mf` 的列
- `iBC`：边界条件标识（>0 / <0 会触发额外 BC 文件读入）
- `iSS`：源汇项标识（非 0 时会触发 SS 文件）
- `Lake`：湖泊 ID（>0 表示该单元属于某个湖）

#### 10.5.4 `<prj>.sp.riv` 与 `<prj>.sp.rivseg`
`<prj>.sp.riv`：两个块  
- 块 1（River reaches）：SHUD 要求 6 列：`index Down Type BedSlope Length BC`  
  - `Down`：下游河段 index（<1 表示 outlet）
  - `Type`：河型编号（索引到块 2）
  - `BC`：>0 Neumann，<0 Dirichlet（会触发 `tsd.rbc*` 读入）
- 块 2（River types）：SHUD 要求 9 列：`index depth bankslope bottomwidth sinuosity rough cwr ksath bedthick`

`<prj>.sp.rivseg`：一个块  
SHUD 要求 4 列：`index iRiv iEle Length`（把河段与单元建立耦合关系）

#### 10.5.5 `.para.soil / .para.geol / .para.lc`（参数表）
`.para.soil`：SHUD 要求 9 列：  
`index infKsatV ThetaS ThetaR infD Alpha Beta hAreaF macKsatV`  
注意：SHUD 读入时会把 `infKsatV/macKsatV` 除以 1440（把 m/day 转为 m/min）。

`.para.geol`：SHUD 要求 8 列：  
`index KsatH KsatV geo_ThetaS geo_ThetaR geo_vAreaF macKsatH macD`  
同样会对导水率做 `/1440` 单位换算。

`.para.lc`：SHUD 接受 7 或 8 列（当前实现至少用到）：  
`index Albedo VegFrac Rough RzD SoilDgrd ImpAF`  
其中 `Rough` 在 SHUD 内部会做 `/60`（把秒单位换到分钟尺度的粗糙度参数）。

#### 10.5.6 `.cfg.para / .cfg.calib`（键值配置）
这两类文件是“每行一个 `key value`”的配置文件：
- `cfg.para`：由 `Control_Data::read()` 读取，关键参数包括  
  - `START/END`：模拟起止（单位：天，SHUD 内部会乘 1440 转分钟）  
  - `MAX_SOLVER_STEP`：最大时间步（分钟）  
  - `dt_*`：各输出变量输出间隔（分钟）  
- `cfg.calib`：由 `globalCal::read()` 读取，常见 key 如  
  - `TS_PRCP`（降水倍率）、`TS_SFCTMP+`（温度偏移）  
  - `ET_ETP/ET_TR/...`（蒸散相关倍率）  
  - `AQ_DEPTH+`（AqD 调整）等

#### 10.5.7 `.cfg.ic`（初值）
SHUD 在 `Model_Data::LoadIC()` 中读取：文件是 **2 个或 3 个 TabularData 块**：
- 块 1：Elements 初值（至少含 6 列，SHUD用到第 2–6 列作为 IS/SNOW/SURF/UNSAT/GW）
- 块 2：Rivers 初值（SHUD用到第 2 列作为河道水位）
- 块 3（可选）：Lakes 初值（SHUD用到第 2 列作为湖泊水位）

---

## 11. 常见踩坑点（按定位思路整理）

### 11.1 “跑 Step3 报错/输出不全”
- `DataPre/pcs/*` 文件缺失：先确认 Step1/Step2 是否成功，尤其是 `dem.tif/wbd_buf/stm`。
- `meteoCov` 缺失：`iforcing < 1` 时 Step3 默认会读 `DataPre/pcs/meteoCov.shp`；必须由 Step2 的 forcing 流程生成。
- `xfg$res` 等参数缺失：部分 forcing 脚本依赖网格分辨率变量，可能需要你在项目文件里补齐或改脚本自动从 NetCDF 读分辨率。

### 11.2 “SHUD 读 forcing 报错/报缺数据”
- `.tsd.forc` 里的 `path/Filename` 不存在：检查 `dout.forc` 是否正确、文件名是否匹配（常见是 `X<lon>Y<lat>.csv`）。
- forcing CSV 时间不连续/缺段：SHUD 的 `_TimeSeriesData::movePointer()` 会检查时间序列是否连续，缺段会直接报错。
- forcing 列序不对：SHUD 不看列名，只按位置取 5 列（降水/温度/RH/风/辐射）。

### 11.3 “结果明显不对（但程序能跑）”
- 投影/单位不一致：PCS/GCS 混用会导致面积、长度、坡度严重偏离。
- soil/geol 参数异常：检查 `SOIL.csv/GEOL.csv` 是否提取正确、PTF 是否得到合理范围。
- START/END 与 forcing 覆盖期不一致：`cfg.para` 的 START/END 是“从 forcing 起始日算的天数”，越界会导致 forcing 指针错误或重复最后值。

---

## 12. 对你后续“SHUD 直接读原始 NetCDF forcing”的意义

如果你的目标是“用户只提供原始 CLDAS/GLDAS/NLDAS/CMFD NetCDF 就能启动 SHUD”，需要先区分：

- **静态输入（几乎必须存在）**：`.sp.mesh/.sp.att/.sp.riv/.sp.rivseg/.para.*.cfg.*.tsd.lai/.tsd.mf`  
  这些描述了网格、河网、参数化与初值，不是 forcing NetCDF 能替代的，通常仍由 AutoSHUD Step1–Step3 产出。
- **动态输入（可替换的部分）**：`dout.forc/*.csv`  
  这部分可以改成 SHUD 运行时直接读 NetCDF（方案 B），但你仍然需要 `.tsd.forc` 提供 forcing 点/覆盖与 element→forcing 的映射（或你要在 SHUD 内重做这套映射逻辑）。

换句话说：**forcing 直读 NetCDF 的改造，本质上是替换 “Step2 生成 forcing CSV + SHUD 读 CSV” 这一段**，而不是取消 AutoSHUD 的全部作用。

---

## 附录 A：仓库里的其他脚本与目录（可选/实验性）

### A.1 `Setp0.1_Delineation.R`：从 DEM 自动划分流域/河网
- 目标：在你没有现成 `wbd.shp/stm.shp` 时，尝试用 WhiteboxTools 做填洼、汇流累积、提取河网与流域边界。
- 现状：脚本内有明显的“硬编码路径”，更像作者的实验脚本；如果要用于通用流程，建议把路径改为由 `*.autoshud.txt` 配置驱动。

### A.2 `SubScript/StepX_MeshOnly.R`：只做边界+DEM+网格（debug 用）
- 目标：跳过 forcing/soil/landuse，只验证“边界裁剪 + mesh 生成”链路是否工作。

### A.3 `SubScript/Step5.1_FloodAnimation.R` 等
- 目标：对 SHUD 输出做动画/专题分析（通常依赖 rSHUD 的读输出接口与已有结果目录）。
