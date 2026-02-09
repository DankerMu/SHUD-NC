<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# SHUD-NC (meta-repo)

本仓库用于组织/管理 SHUD 相关工作流与文档；核心代码分别位于三个子模块中。

## 目录结构约定（推荐）

- `SHUD/`：SHUD 求解器源码（submodule）
  - **核心开发目标都落在这里**：forcing 直接读 NetCDF、输出写标准 NetCDF
- `AutoSHUD/`：AutoSHUD 流水线脚本（submodule）
  - 负责 **静态输入**（mesh/att/riv/soil/lc/para…）生成；forcing CSV 保留作为 baseline/兼容
- `rSHUD/`：R 工具包（submodule）
  - 提供 AutoSHUD 依赖的 R 侧空间/NetCDF 工具函数（R GIS 栈迁移/维护主要在这里）
- `docs/`：设计/迁移文档（可入库）
- `projects/`：项目/流域的**可版本化配置**（官方示例也在这里）
  - `projects/qhh/`：QHH 官方示例（baseline 对照 + 未来 NetCDF 改造目标配置）
- `configs/`：forcing 产品适配、输出 schema 等**可复用配置**（可入库）
- `tools/`：一键运行/校验/对比脚本（可入库）
- `testdata/`：可随仓库提交的小样本数据（用于测试/回归；可入库）
- `qhh/`：本地 legacy 工作区（可能包含大数据/旧脚本/旧产物；不入库，见 `.gitignore`）
- `Data/`：原始外部数据（不入库；仅保留 `Data/README.md` 说明结构）
- `runs/`：可再生中间结果与运行产物（不入库；仅保留 `runs/README.md`）

> 数据目录结构（多数据源并存）请以 `Data/README.md` 为准：`Soil/<dataset>/`、`Landuse/<dataset>/`、`Forcing/<dataset>/`。

## 仓库关系

- **本仓库（父仓库）**：`SHUD-NC`（私有）
  - 远程：`origin = https://github.com/DankerMu/SHUD-NC.git`
  - 作用：记录项目说明、文档、脚本，以及两个子模块所指向的 **commit 指针**。
- **子模块 1**：`SHUD/`
  - fork（推送用）：`origin = https://github.com/DankerMu/SHUD-up.git`
  - 上游（仅用于同步，可选）：`upstream = https://github.com/SHUD-System/SHUD.git`（默认分支 `master`）
- **子模块 2**：`AutoSHUD/`
  - fork（推送用）：`origin = https://github.com/DankerMu/AutoSHUD.git`
  - 上游（仅用于同步，可选）：`upstream = https://github.com/SHUD-System/AutoSHUD.git`（默认分支 `master`）
- **子模块 3**：`rSHUD/`
  - fork（推送用）：`origin = https://github.com/DankerMu/rSHUD.git`
  - 上游（仅用于同步，可选）：`upstream = https://github.com/SHUD-System/rSHUD.git`（默认分支 `master`）

## Submodule 模式的关键点

- 父仓库不会保存 `SHUD/`、`AutoSHUD/`、`rSHUD/` 的文件内容，只保存它们各自的 **commit SHA（gitlink）**。
- 子模块执行 `git submodule update` 后，可能会处于 **detached HEAD**；开发前请切到分支（如 `master` 或新建 feature 分支）。
- 你在子模块里完成提交并 `push` 后，如果希望父仓库也“跟上”该版本，需要在父仓库再提交一次子模块指针更新：
  - `git add SHUD AutoSHUD rSHUD && git commit -m "Update submodule refs" && git push`

## 常用操作（推荐流程）

### 克隆父仓库（含子模块）

1. `git clone https://github.com/DankerMu/SHUD-NC.git`
2. `cd SHUD-NC && git submodule update --init --recursive`

### 运行示例项目（单一入口：`projects/<case>/shud.yaml`）

- 校验：`python3 tools/shudnc.py projects/qhh/shud.yaml validate --profile baseline`
- 运行 baseline：`python3 tools/shudnc.py projects/qhh/shud.yaml run --profile baseline`

### 在子模块开发并推送到个人 fork

以 `AutoSHUD/` 为例（`SHUD/`、`rSHUD/` 同理）：

1. `cd AutoSHUD`
2. `git switch -c feat/<topic>`（或 `git checkout -b feat/<topic>`）
3. 修改后：`git add -A && git commit -m "<msg>"`
4. 推送：`git push -u origin feat/<topic>`

### 提 Issue / PR（只在个人仓库进行）

Issue（在个人仓库）：

- `gh issue create --repo DankerMu/AutoSHUD`
- `gh issue create --repo DankerMu/SHUD-up`
- `gh issue create --repo DankerMu/rSHUD`

PR（从分支提到个人仓库 `master`）：

- `gh pr create --repo DankerMu/AutoSHUD --base master --head feat/<topic>`
- `gh pr create --repo DankerMu/SHUD-up --base master --head feat/<topic>`
- `gh pr create --repo DankerMu/rSHUD --base master --head feat/<topic>`

### 同步上游更新到个人 fork

以 `SHUD/` 为例（`AutoSHUD/`、`rSHUD/` 同理）：

1. `cd SHUD`
2. `git fetch upstream`
3. `git switch master`
4. `git rebase upstream/master`（或使用 `git merge upstream/master`）
5. `git push origin master`

同步完成后，如需更新父仓库记录的子模块指针，再回到父仓库提交指针更新（见上文）。

## 注意事项

- 父仓库中不要把子模块当“普通目录”去 `git add SHUD/ AutoSHUD/ rSHUD/`（submodule 已由 `.gitmodules` 管理）。
- 大数据与产物不要进 Git：`Data/`、`runs/`、以及 `qhh/` 默认被 `.gitignore` 忽略。
