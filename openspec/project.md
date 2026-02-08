# Project Context

## Purpose
SHUD-NC 是一个 **meta-repo**，用于组织/管理 SHUD（求解器）与 AutoSHUD（输入生成流水线）相关工作，并推进以下目标：

- **阶段 A（Forcing）**：让 SHUD 运行时 **直接读取原始 forcing NetCDF**（先 CMFD2/ERA5），不再依赖 `dout.forc/*.csv`。
- **阶段 B（Output）**：让 SHUD 输出 **规范 NetCDF**（CF/UGRID 友好），便于 xarray/QGIS/Panoply 直接读取。
- **Baseline 保留**：保持原 AutoSHUD→SHUD（CSV forcing + legacy output）流水线可跑、可回归对照。

实现原则：核心模型能力落在 `SHUD/` 子模块；父仓库负责文档、配置与一键运行编排（`tools/shudnc.py` + `projects/<case>/shud.yaml` 单入口）。

## Tech Stack
- **SHUD**：C++14，SUNDIALS/CVODE；计划新增可选 NetCDF（netcdf-c）依赖
- **AutoSHUD**：R 脚本流水线（Step1–Step3 生成静态输入；baseline forcing CSV 作为对照）
- **Meta-runner**：Python3（`tools/shudnc.py`），YAML（`projects/<case>/shud.yaml`）
- **数据格式**：NetCDF（forcing 输入与 output 输出），目标对齐 CF/UGRID

## Project Conventions

### Code Style
- 父仓库脚本以“可读 + fail-fast”为先（清晰错误、路径解析一致、dry-run 可用）
- SHUD 侧改动坚持 **最小侵入**：先保持 baseline 行为完全不变，再新增模式/功能
- 配置命名约定：
  - 用户唯一入口：`projects/<case>/shud.yaml`
  - SHUD 新增配置：继续用 `.cfg`（KEY VALUE 文本），避免 SHUD 引入 YAML 依赖
  - 运行产物统一写入 `runs/`（不入库）；原始大数据在 `Data/`（不入库）

### Architecture Patterns
- Forcing：引入 `ForcingProvider` 抽象（CSV/NetCDF 两种 provider），保证 step-function 与 TSR 语义一致
- Output：复用 `Print_Ctrl` 的 buffer/interval 语义，通过 “sink” 机制新增 NetCDF 输出通道（legacy 保持不变）
- 父仓库只做编排与约定：生成/patch SHUD 配置、串联 AutoSHUD→SHUD、做 validate/compare

### Testing Strategy
- 最小回归：同一 case（QHH），缩短模拟期（例如 2–10 天）：
  - baseline：CSV forcing + legacy output
  - 阶段 A：NetCDF forcing + legacy output
  - 阶段 B：NetCDF forcing + NetCDF output（可与 legacy 同时开）
- 对齐策略：
  - forcing：抽样站点/时刻，对齐 `Precip/Temp/RH/Wind/RN`
  - 输出：抽样 element/river/lake 变量，对齐 time 与数值（允许极小浮点误差）
- 对 NetCDF：必须覆盖边界条件（跨月/跨日文件切换、lat 递减、lon 0–360、_FillValue 处理）

### Git Workflow
- 本仓库为父仓库，`SHUD/` 与 `AutoSHUD/` 为 submodule（父仓库只记录 gitlink SHA）
- 代码开发在各自子模块仓库进行（个人 fork：`DankerMu/SHUD-up`、`DankerMu/AutoSHUD`），通过 issue → PR → review 推进
- 子模块提交并 push 后，父仓库需要单独提交 submodule 指针更新
- 分支命名建议：`feat/<topic>`（子模块）；父仓库如需分支使用 `codex/<topic>`（可选）

## Domain Context
- SHUD forcing 固定 5 变量契约（单位必须在进入 SHUD 前满足）：
  - Precip：mm/day
  - Temp：°C（SHUD 内会做高程订正，依赖 forcing 点 Z）
  - RH：0–1
  - Wind：m/s
  - RN：W/m²（与 `RADIATION_INPUT_MODE=SWDOWN/SWNET` 语义相关）
- SHUD 内部时间轴：以 `<prj>.tsd.forc` 的 `ForcStartTime (YYYYMMDD)` 为基准，`t_min` 为相对分钟
- NetCDF 输出目标：CF/UGRID 友好，time 轴语义与 legacy `Print_Ctrl` 一致（left endpoint）

## Important Constraints
- **不得破坏 baseline**：默认行为必须保持 CSV forcing + legacy output
- **SHUD 不引入 YAML 解析**：所有新增配置用 `.cfg` KEY VALUE，YAML 仅在父仓库编排层使用
- **fail-fast**：数据缺测/覆盖期不足/单位无法判定时必须清晰报错（指出 file/var/time/station）
- 插值默认 `NEAREST`（优先回归一致性；未来再扩展 BILINEAR）

## External Dependencies
- SUNDIALS/CVODE（SHUD 必需）
- NetCDF（netcdf-c，阶段 A/B 可选依赖）
- GDAL（AutoSHUD Step1–Step3 常用）
- R packages（AutoSHUD 的 GIS/NetCDF 处理依赖；以脚本 `library()/require()` 为准）
