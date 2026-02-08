# tools（辅助脚本）

本目录放置“父仓库编排层”的脚本：负责串联 AutoSHUD→SHUD 的运行、校验数据目录结构、回归对比等。

当前提供：

- `tools/shudnc.py`：以 `projects/<case>/shud.yaml` 为**单一入口配置**的运行器（生成 AutoSHUD 配置并串联运行）
  - `render-shud-cfg`：从 `profiles.<name>.shud` 渲染 SHUD 的 `.cfg` 覆盖文件并补丁 `.cfg.para`（用于 NetCDF forcing/output 迁移）
- `tools/run_qhh_baseline_autoshud.sh`：运行 QHH 的 baseline（AutoSHUD Step1–Step3，生成 SHUD 静态输入 + forcing CSV）
- `tools/run_qhh_baseline.sh`：一键跑完 baseline（AutoSHUD Step1–Step3 + 调用 `SHUD/shud` 运行）
- `tools/compare_forcing.py`：forcing 抽样对比（baseline CSV vs NetCDF forcing）
  - 依赖：`python3 -m pip install netCDF4 numpy`
  - 示例：
    - `python3 tools/compare_forcing.py --baseline-run runs/qhh/baseline --nc-run runs/qhh/nc --prj qhh --stations 0,1,2 --t-min 0,180 --out-json runs/qhh/compare/forcing.json`
- `tools/compare_output.py`：输出抽样对比（legacy *.dat vs NetCDF variable）
  - 依赖：`python3 -m pip install netCDF4 numpy`
  - 示例（Phase B 完成后）：
    - `python3 tools/compare_output.py --legacy-bin runs/qhh/baseline/output/qhh.out/qhh.eleysurf.dat --netcdf runs/qhh/nc/output_netcdf/qhh.ele.nc --var y_surf --obj-dim nface --times-min 0,60 --indices 1,2,3 --out-json runs/qhh/compare/output.json`
