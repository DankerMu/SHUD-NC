# Change: Add `render-shud-cfg` and SHUD cfg overlay rendering in meta-runner

## Why
总体方案要求用户只改 `projects/<case>/shud.yaml` 即可切换 baseline 与 nc。由于 SHUD 不解析 YAML，父仓库需要把 YAML 配置 **渲染为 SHUD 可读的 `.cfg` 文件**，并对现有 `<prj>.cfg.para` 做最小 patch。

## Scope
- **Repo**: `DankerMu/SHUD-NC`
- 在 `tools/shudnc.py` 增加命令：
  - `render-shud-cfg`：仅生成并展示将写入的：
    - `input/<prj>/<prj>.cfg.forcing`
    - `input/<prj>/<prj>.cfg.ncoutput`（阶段 B）
    - `.cfg.para` patch（追加键）
- 明确路径规则：
  - 生成文件写入 `runs/<case>/<profile>/input/<prj>/`（与 AutoSHUD 输出一致）
  - `.cfg.para` patch 保持幂等（重复运行不产生重复键）

## Non-goals
- 本 change 不要求立即能跑 nc profile（由下一条 change 完成）。

## Acceptance criteria
- [ ] `python3 tools/shudnc.py ... render-shud-cfg --profile baseline|nc` 可运行（至少 dry-run）。
- [ ] 生成的 `.cfg` 为 KEY VALUE 文本，路径可解析，且不会修改 SHUD 源码。

## Test plan
- `python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile baseline --dry-run`
- `python3 tools/shudnc.py projects/qhh/shud.yaml render-shud-cfg --profile nc --dry-run`

