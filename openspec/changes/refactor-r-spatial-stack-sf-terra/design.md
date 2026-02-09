# Design: R spatial stack refactor (sf/terra)

## Goals
- Eliminate hard dependencies on deprecated R spatial packages: `sp`, `raster`, `rgdal`, `rgeos`, `proj4`.
- Keep baseline pipeline behavior and outputs **functionally equivalent** (regression-friendly).
- Centralize spatial primitives in `rSHUD` so `AutoSHUD` scripts stay thin and consistent.

## Code inventory (what must change)
### AutoSHUD hotspots
The following scripts/functions currently *assume* the legacy stack and need to be migrated:
- `AutoSHUD/GetReady.R`: loads `raster/sp/rgeos/rgdal` and wires globals.
- `AutoSHUD/Step1_RawDataProcessng.R`:
  - vector I/O: `readOGR()`
  - CRS: `spTransform()`, `sp::CRS()`
  - geometry fixes/ops: `gBuffer(width=0)`, `gUnaryUnion()`, `gSimplify()`, `gLength()`
  - hole handling: `removeholes()` (from `rSHUD`)
- `AutoSHUD/Step3_BuidModel.R`:
  - basin area/union/simplify: `gArea()`, `rgeos::gUnionCascaded()`, `rgeos::gSimplify()`
  - river lengths: `gLength(byid=TRUE)`
  - forcing coverage: `rSHUD::ForcingCoverage()`
- `AutoSHUD/Rfunction/ReadProject.R`: CRS construction via `rSHUD::crs.Albers(rgdal::readOGR(...))`
- `AutoSHUD/Rfunction/getDEM.R`: `rgdal::readOGR()`, `sp::spTransform()`, `rgeos::gIntersects()`, plus `raster::*`
- Forcing subset helpers: `gIntersects(..., byid=TRUE)` appears in multiple `SubScript/` and `Rfunction/` files.

### rSHUD hotspots
`rSHUD` is currently built around `sp/raster/rgeos/rgdal/proj4`. Key files:
- `rSHUD/R/Func_GIS.R`: central GIS helper collection; heavy `sp/raster/rgeos` usage.
- `rSHUD/R/GIS_Projection.R`: CRS utilities using `sp::CRS()` and `spTransform()` patterns.
- `rSHUD/R/GIS_delineation.R`: `rgdal::readOGR()`, `sp::spTransform()`, `raster::mask/crop`.
- `rSHUD/R/GIS_RiverProcess.R`: `rgeos::gSimplify()` and `sp` objects.
- `rSHUD/R/autoBuildModel.R`: buffer/union/simplify/crop plotting built on legacy stack.

## Key decision: “modern core + optional legacy compatibility”
### Core (required)
- Vector: `sf`
- Raster: `terra`

### Optional (compat only; `Suggests`)
For a transition period, allow optional support for legacy inputs/objects **only if installed**:
- `sp`, `raster`

This allows:
- `rSHUD` to accept older object types (when users have them) via conversion (`sf::st_as_sf()` etc.)
- But does not force these packages to be installed in a clean environment.

## Mapping: old APIs → new APIs
### Vector I/O and projection
- `rgdal::readOGR()` / `readOGR()` → `sf::st_read()`
- `rgdal::writeOGR()` / `writeOGR()` / `rSHUD::writeshape()` → `sf::st_write()`
- `sp::spTransform()` / `spTransform()` → `sf::st_transform()`
- `sp::CRS()` → `sf::st_crs()`

### Geometry operations (GEOS)
- `rgeos::gBuffer()` → `sf::st_buffer()`
- `rgeos::gUnaryUnion()` / `rgeos::gUnionCascaded()` → `sf::st_union()`
- `rgeos::gSimplify()` → `sf::st_simplify()`
- `rgeos::gIntersects(..., byid=TRUE)` → `sf::st_intersects(..., sparse=TRUE)`
- `rgeos::gLength()` → `sf::st_length()`
- `rgeos::gArea()` → `sf::st_area()`

### Raster operations
- `raster::raster()` / `stack()` / `extent()` / `res()` → `terra::rast()` / `terra::ext()` / `terra::res()`
- `raster::crop()` / `mask()` → `terra::crop()` / `terra::mask()`
- `raster::extract()` → `terra::extract()`
- `raster::projectRaster()` → `terra::project()`

## Geometry validity & “removeholes”
AutoSHUD 现有逻辑常见用法：
- `gBuffer(x, width=0)` 用于修复几何错误
- `removeholes(gUnaryUnion(...))` 去孔洞/合并

在 `sf` 路径下建议：
- 使用 `sf::st_make_valid()`（必要时依赖 `lwgeom` 或 `s2` 配置）
- 对 hole 的处理采用显式规则（例如仅保留最大外环或按面积阈值过滤），并把规则固化到 `rSHUD` 包内的 helper 函数中

## Regression strategy
- 对比维度以“下游 SHUD 输入”优先：
  - `input/<prj>/` 下关键文件是否生成、行数/字段数一致、数值统计量一致
- 几何运算引入的微小差异（例如简化后节点数变化）允许存在，但必须：
  - 可解释（来自实现差异）
  - 被容差规则覆盖
  - 不影响 SHUD 运行稳定性

## Migration ordering (to reduce risk)
1. Refactor `rSHUD` first to provide stable wrappers based on `sf/terra`.
2. Update AutoSHUD to call `rSHUD` wrappers (or directly use `sf/terra`) and remove legacy package imports.
3. Only then remove legacy packages from required dependencies (so developers can still debug during the transition if needed).
