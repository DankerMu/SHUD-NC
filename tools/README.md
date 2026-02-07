# tools（辅助脚本）

本目录放置“父仓库编排层”的脚本：负责串联 AutoSHUD→SHUD 的运行、校验数据目录结构、回归对比等。

当前提供：

- `tools/shudnc.py`：以 `projects/<case>/shud.yaml` 为**单一入口配置**的运行器（生成 AutoSHUD 配置并串联运行）
- `tools/run_qhh_baseline_autoshud.sh`：运行 QHH 的 baseline（AutoSHUD Step1–Step3，生成 SHUD 静态输入 + forcing CSV）
- `tools/run_qhh_baseline.sh`：一键跑完 baseline（AutoSHUD Step1–Step3 + 调用 `SHUD/shud` 运行）
