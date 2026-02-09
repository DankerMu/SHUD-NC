# Change: Refactor R spatial stack (sf/terra) + manage `rSHUD/` as submodule

## Why
当前 baseline 的 AutoSHUD 流水线与 `rSHUD` 工具包依赖旧的 R GIS 生态（`sp/raster/rgdal/rgeos/proj4`）。这些包在新版本 R / macOS（尤其是 arm64）上经常出现：
- 编译失败（头文件缺失、宏污染 C++ headers、系统依赖不一致）
- 安装成本高且不可复现
- 长期维护风险（已被新生态取代）

本变更目标是 **保持功能不变**（baseline 流水线结果等价/可回归），但把底层 GIS 栈全面迁移到现代且可维护的：
- vector: `sf`（GEOS/PROJ/GDAL）
- raster: `terra`（GDAL）

并把 `rSHUD/` 纳入父仓库 submodule 管理，使环境与开发流程与 `SHUD/`、`AutoSHUD/` 一致。

## Scope
- 父仓库（`SHUD-NC`）
  - 将本地已有的 `rSHUD/` 纳入 git submodule（指向 `DankerMu/rSHUD` fork）
  - 增加 R 环境安装/自检脚本与文档（项目内 `.Rlib` 或等价方式）
- 子模块 `rSHUD/`
  - 移除对 `sp/raster/rgdal/rgeos/proj4` 的硬依赖（从 `Imports`/`LinkingTo` 移出）
  - 用 `sf/terra` 重实现当前项目中被 AutoSHUD 依赖的关键函数（保持语义一致）
- 子模块 `AutoSHUD/`
  - 全面替换 `readOGR/spTransform/gBuffer/...` 等旧 API 到 `sf/terra`
  - `GetReady.R` 不再 `library(rgdal/rgeos/sp/raster)`

## Non-goals
- 不改变 SHUD 求解器行为、NetCDF forcing/output 的契约与实现
- 不引入新的 forcing 产品或新的输出 schema
- 不做“算法升级”（例如改用新的简化/叠置策略）；只做等价替换与修复

## Current findings (R 代码依赖图)
### AutoSHUD（现状）
- 旧栈依赖入口：`AutoSHUD/GetReady.R`
  - `library(raster)`, `library(sp)`, `library(rgeos)`, `library(rgdal)`, `library(rSHUD)`
- 典型旧 API 使用（不完全列举）：
  - I/O / CRS / transform：`readOGR()`, `spTransform()`, `sp::CRS()`
  - GEOS ops：`gBuffer()`, `gUnaryUnion()`, `gUnionCascaded()`, `gSimplify()`, `gIntersects()`, `gLength()`, `gArea()`
  - raster ops：`raster::raster()`, `raster::extent()`, `raster::res()`, `raster::extract()`, `raster::crop()`, `raster::mask()`, `raster::projectRaster()`

### rSHUD（现状）
`rSHUD/DESCRIPTION` 当前 `Imports` 包含 `raster/sp/rgeos/proj4`，并且 `LinkingTo: sp`（会强制依赖 `sp`）。
代码中大量直接调用 `rgdal::readOGR()` 与 `rgeos::*`。

## Acceptance criteria
- [ ] 在干净环境中，安装并运行 AutoSHUD（Step1–Step3）不再需要安装 `rgdal/rgeos/sp/raster/proj4`
- [ ] `rSHUD` 可在不安装上述旧包的情况下完成安装（旧包最多作为 `Suggests`，且默认路径不依赖它们）
- [ ] `python3 tools/shudnc.py projects/qhh/shud.yaml run --profile baseline` 在准备好数据后可跑通（R 侧依赖已满足）
- [ ] 提供 `tools/` 下的 R 环境自检脚本：缺依赖时 fail-fast 并列出缺失项
- [ ] 文档明确：系统依赖（GDAL/GEOS/PROJ）+ R 包安装方式 + 常见故障排查

## Test plan
- 以 `projects/qhh/shud.yaml` 的 baseline profile 为主：
  - 运行 AutoSHUD Step1–Step3（必要时缩短时段/简化配置）
  - 验证关键产物存在（`runs/.../input/<prj>/` 结构、静态输入、forcing CSV baseline）
- 回归对比：
  - 对 mesh/att/riv 关键文件做结构性检查（行数、关键字段范围、统计量）
  - 对几何运算结果允许极小差异（定义容差与“等价”判定规则）

