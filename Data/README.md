# Data 目录约定（不入库）

本仓库把**体积很大的原始数据**统一放在仓库根目录的 `Data/`（或将 `Data/` 做成软链接指向数据盘/挂载盘，例如服务器上的 `/volume/...`）。

> 说明：`Data/` 下的真实数据 **不提交到 GitHub**；仓库里只保留这份目录结构说明，方便协作与复现。

## 推荐结构（支持多数据源并存）

```
Data/
  projects/
    qhh/
      raw/
        spatial/
          # 边界/河网/DEM/湖泊等（不入库）
          # e.g. meritbasin_wbd1_32647.shp, meritbasin_riv1.shp, gdem.tif, lake.shp

  Soil/
    HWSD_RASTER/
      hwsd.bil
      hwsd.dbf
      hwsd.hdr
      hwsd.blw
      ...
    <OtherSoilDataset>/
      ...

  Landuse/
    USGS_LCI/
      LCType.tif
      ...
    <OtherLanduseDataset>/
      ...

  Forcing/
    CMFD_2017_2018/           # 示例：QHH 基线（AutoSHUD→SHUD）用
      Prec/*.nc               # 如：prec_CMFD_*_201701.nc
      Temp/*.nc
      SHum/*.nc
      SRad/*.nc
      Wind/*.nc
      Pres/*.nc

    ERA5/                     # 示例：QHH 子集（按你当前的数据组织）
      qhh/
        2017/*.nc             # 如：ERA5_20170104.nc
        2018/*.nc

    <GLDAS|FLDAS|...>/        # 预留：后续接入（数据量大）
      ...
```

## 约定原则

- `Soil/`、`Landuse/`、`Forcing/` **每类下面允许多个数据集并存**，用子目录名区分（例如 `HWSD_RASTER`、`USGS_LCI`、`CMFD_2017_2018`）。
- **原始数据尽量只读**：裁剪/投影/中间产物/模型输入输出请写到 `runs/`（见 `runs/README.md`）。
- **示例（QHH）配置**会在 `projects/qhh/` 里指向这些目录；你也可以在 `projects/<your-case>/` 下新增配置文件来切换数据源与时间范围。
