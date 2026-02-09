## 1. Repo wiring (SHUD-NC)
- [ ] Add `rSHUD/` as a git submodule pointing to `https://github.com/DankerMu/rSHUD.git`
- [ ] Update root docs to include `rSHUD/` in the submodule workflow notes

## 2. rSHUD refactor (rSHUD submodule)
- [ ] Create a feature branch (e.g. `feat/sf-terra-stack`)
- [ ] Update `DESCRIPTION` to:
  - [ ] add `sf` + `terra` (and `lwgeom` if needed) to `Imports`
  - [ ] remove `sp/raster/rgeos/rgdal/proj4` from hard dependencies
  - [ ] remove `LinkingTo: sp` if not required by `src/`
- [ ] Provide a small set of internal wrappers (vector/raster/geometry):
  - [ ] read/write vector, CRS transform
  - [ ] buffer/union/simplify/length/area/intersects
  - [ ] make-valid / hole removal behavior used by AutoSHUD
- [ ] Refactor functions used by AutoSHUD to run on `sf/terra` objects:
  - [ ] `fishnet`, `writeshape`, `xy2shp`
  - [ ] `crs.Albers`, `days_in_year`
  - [ ] `ForcingCoverage`, `readnc`
- [ ] Add `testthat` smoke tests for the wrappers and a couple of key APIs

## 3. AutoSHUD refactor (AutoSHUD submodule)
- [ ] Create a feature branch (e.g. `feat/sf-terra-stack`)
- [ ] Replace vector I/O + transforms:
  - [ ] `readOGR()` → `sf::st_read()`
  - [ ] `spTransform()` → `sf::st_transform()`
- [ ] Replace GEOS ops:
  - [ ] `gBuffer/gUnaryUnion/gUnionCascaded/gSimplify/gIntersects/gLength/gArea` → `sf::*`
- [ ] Replace raster ops:
  - [ ] `raster::*` → `terra::*` (crop/mask/extract/reproject/plot)
- [ ] Update `GetReady.R` imports to drop legacy packages and load modern ones
- [ ] Run Step1–Step3 on QHH and at least one `AutoSHUD/Example/*.autoshud.txt`

## 4. Environment & tooling (SHUD-NC)
- [ ] Add `tools/r/install_deps.R` (project-local installation into `.Rlib/`)
- [ ] Add `tools/r/check_env.R` (fail-fast dependency check; returns non-zero on missing deps)
- [ ] Add `docs/environment.md` describing:
  - [ ] system deps (GDAL/GEOS/PROJ) for macOS/Linux
  - [ ] R deps install + troubleshooting
  - [ ] how to install local `rSHUD` from submodule

## 5. Validation
- [ ] Baseline pipeline run via `tools/shudnc.py` completes on QHH (Step1–Step3 + optional SHUD run)
- [ ] Summarize regression checks and any known tolerances/differences

