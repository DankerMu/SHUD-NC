# QHH 官方示例

本目录用于提供 **QHH（青海湖/祁连山一带）** 的示例配置与可复现的运行入口，作为后续 “SHUD 直接读 forcing NetCDF + 输出 NetCDF” 改造的 **baseline** 对照。

> 注意：本仓库不会提交大数据与运行产物。请将原始数据放在仓库根目录 `Data/`（或软链接到数据盘），运行产物写到 `runs/`（见 `Data/README.md` 与 `runs/README.md`）。

## Baseline：原 AutoSHUD → SHUD（CSV forcing）流水线

### 1) 准备原始数据（Data）

至少需要以下数据集（默认目录约定见 `Data/README.md`）：

- Soil：`Data/Soil/HWSD_RASTER/`（包含 `hwsd.bil`、`hwsd.dbf` 等）
- Landuse：`Data/Landuse/USGS_LCI/LCType.tif`
- Forcing（CMFD 2017–2018 示例）：`Data/Forcing/CMFD_2017_2018/<Var>/*.nc`
  - `<Var>` 通常为 `Prec/Temp/SHum/SRad/Wind/Pres`
  - 文件命名形如 `prec_CMFD_*_201701.nc`

### 2) 准备 QHH 研究区空间输入（本地目录，不入库）

AutoSHUD 的 Step1 需要研究区的边界/河网/DEM（以及可选湖泊）。默认示例配置引用：

`Data/projects/qhh/raw/spatial/meritbasin_wbd1_32647.*`、`Data/projects/qhh/raw/spatial/meritbasin_riv1.*`、`Data/projects/qhh/raw/spatial/gdem.tif`、`Data/projects/qhh/raw/spatial/lake.*`

这些文件目前不随仓库提交；请在本地准备好（可从你现有的 QHH 数据目录拷贝/软链接到 `Data/projects/qhh/raw/spatial/`）。

### 3) 运行（推荐从 submodule 目录启动）

单一入口配置：`projects/qhh/shud.yaml`

推荐命令（从仓库根目录执行）：

1. 校验数据与路径：
   - `python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile baseline`
2. 一键跑完 baseline（AutoSHUD Step1–3 + SHUD 运行）：
   - `python3 tools/shudnc.py projects/qhh/shud.yaml run --profile baseline`

也可以用快捷脚本：

- `bash tools/run_qhh_baseline.sh`

产物默认会写到：

- AutoSHUD：`runs/qhh/baseline/DataPre/`、`runs/qhh/baseline/input/qhh/`
- forcing CSV（baseline）：`runs/qhh/baseline/forcing/`
- 自动生成的 AutoSHUD 配置：`runs/qhh/baseline/config/autoshud.generated.txt`

后续你可以用 `SHUD/` 子模块编译并运行求解器，读取 `runs/qhh/baseline/input/qhh/` 作为输入目录。
