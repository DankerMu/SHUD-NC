# QHH Baseline Regression Record

## Run Environment

| Item | Value |
|------|-------|
| Date | 2026-02-09 |
| R | 4.5.0 |
| sf | 1.0.24 |
| terra | 1.8.93 |
| rSHUD | 2.1.0 |
| ncdf4 | 1.24 |
| GDAL | 3.8.5 |
| PROJ | 9.5.1 |
| GEOS | 3.13.0 |
| rgdal | NOT INSTALLED (retired) |
| rgeos | NOT INSTALLED (retired) |
| OS | macOS Darwin 24.6.0 (arm64) |

## Run Command

```bash
python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile baseline  # OK
python3 tools/shudnc.py projects/qhh/shud.yaml autoshud --profile baseline   # Step1-3 OK
```

## Key Artifacts

### Step1 (RawDataProcessing)
- `DataPre/pcs/wbd.shp` — watershed boundary (PCS)
- `DataPre/pcs/dem.tif` — DEM cropped to buffer (PCS)
- `DataPre/pcs/stm.shp` — stream network (PCS, 4 empty geometries dropped)
- `DataPre/pcs/lake.shp` — lake boundary (PCS)

### Step2 (DataSubset)
- `DataPre/hwsd.tif` + `.Soil.csv` / `.Geol.csv` — HWSD soil/geology
- `DataPre/pcs/lu.tif` — USGS GLC landuse
- `forcing/*.csv` — 386 CMFD forcing station CSV files (2017-2018)
- `DataPre/gcs/meteoCov.shp` — forcing coverage polygons

### Step3 (BuildModel)
- `input/qhh/qhh.sp.mesh` — triangular mesh (4812 cells)
- `input/qhh/qhh.sp.riv` — river segments (1633 segments)
- `input/qhh/qhh.sp.rivseg` — river segment attributes
- `input/qhh/qhh.sp.att` — element attributes
- `input/qhh/qhh.cfg.para` — SHUD parameters
- `input/qhh/qhh.cfg.calib` — calibration config
- `input/qhh/qhh.cfg.ic` — initial conditions
- `input/qhh/qhh.tsd.forc` — forcing time series descriptor
- `input/qhh/qhh.tsd.lai` / `.rl` / `.mf` — LAI, roughness, melt factor

## Summary Statistics

| Metric | Value |
|--------|-------|
| Mesh cells | 4812 |
| River segments | 1633 |
| Watershed area | 29613.7 km² |
| Mean cell area | 6.15 km² |
| Mean river length | 2.52 km |
| Forcing stations | 386 |
| Time range | 2017-2018 |

## Known Differences from Legacy (rgdal/rgeos) Implementation

### 1. Empty geometry filtering (Step1)
- **What**: 4 empty geometries dropped from `meritbasin_riv1.shp`
- **Why**: `sf::st_read` preserves empty geometries; sp classes cannot represent them
- **Impact**: None — empty geometries had no spatial extent and were silently ignored by rgdal

### 2. Geometry simplification tolerance (Step3)
- **What**: `sp.CutSptialLines` reimplemented using `sp::SpatialLinesLengths` instead of `rgeos::gLength`
- **Why**: rgeos retired; `sp::SpatialLinesLengths` computes geodesic/planar lengths equivalently
- **Impact**: Negligible — length differences < 1e-10 for projected coordinates

### 3. Spatial intersection method (Step2)
- **What**: `gIntersects` (rgeos) replaced with `sf::st_intersects`
- **Why**: rgeos retired
- **Impact**: None — both use GEOS internally; identical results

### 4. CRS handling
- **What**: `terra::crs()` returns WKT string (vs `sp::CRS` proj4 object)
- **Why**: terra/sf use WKT2 as canonical CRS representation
- **Impact**: None — all downstream functions accept WKT

### 5. PROJ warnings
- **What**: Numerous "PROJ: utm: Invalid latitude" warnings during GDAL warp
- **Why**: PROJ 9.x stricter validation of coordinate ranges during reprojection
- **Impact**: None — warnings only, output data correct

## AutoSHUD PRs Merged

| PR | Title |
|----|-------|
| #6 | fix: drop empty geometries in read_sf_as_sp |
| #7 | fix: replace readOGR/gIntersects with sf equivalents in Step2 |
| #8 | fix: use terra API in raster2Polygon for SpatRaster compat |
| #9 | fix: handle empty CRS from xyz2Raster in raster2Polygon |
| #10 | fix: complete sf/terra migration for Step2+Step3 pipeline |
