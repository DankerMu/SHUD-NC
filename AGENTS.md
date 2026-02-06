# SHUD-NC (meta-repo)

本仓库用于组织/管理 SHUD 相关工作流与文档；核心代码分别位于两个子模块中。

## 仓库关系

- **本仓库（父仓库）**：`SHUD-NC`（私有）
  - 远程：`origin = https://github.com/DankerMu/SHUD-NC.git`
  - 作用：记录项目说明、文档、脚本，以及两个子模块所指向的 **commit 指针**。
- **子模块 1**：`SHUD/`
  - fork（推送用）：`origin = https://github.com/DankerMu/SHUD-up.git`
  - 上游（同步/提 PR 目标）：`upstream = https://github.com/SHUD-System/SHUD.git`（默认分支 `master`）
- **子模块 2**：`AutoSHUD/`
  - fork（推送用）：`origin = https://github.com/DankerMu/AutoSHUD.git`
  - 上游（同步/提 PR 目标）：`upstream = https://github.com/SHUD-System/AutoSHUD.git`（默认分支 `master`）

## Submodule 模式的关键点

- 父仓库不会保存 `SHUD/`、`AutoSHUD/` 的文件内容，只保存它们各自的 **commit SHA（gitlink）**。
- 子模块执行 `git submodule update` 后，可能会处于 **detached HEAD**；开发前请切到分支（如 `master` 或新建 feature 分支）。
- 你在子模块里完成提交并 `push` 后，如果希望父仓库也“跟上”该版本，需要在父仓库再提交一次子模块指针更新：
  - `git add SHUD AutoSHUD && git commit -m "Update submodule refs" && git push`

## 常用操作（推荐流程）

### 克隆父仓库（含子模块）

1. `git clone https://github.com/DankerMu/SHUD-NC.git`
2. `cd SHUD-NC && git submodule update --init --recursive`

### 在子模块开发并推送到个人 fork

以 `AutoSHUD/` 为例（`SHUD/` 同理）：

1. `cd AutoSHUD`
2. `git switch -c feat/<topic>`（或 `git checkout -b feat/<topic>`）
3. 修改后：`git add -A && git commit -m "<msg>"`
4. 推送：`git push -u origin feat/<topic>`

### 提 Issue / PR（分别在各自上游仓库进行）

Issue（在上游仓库）：

- `gh issue create --repo SHUD-System/AutoSHUD`
- `gh issue create --repo SHUD-System/SHUD`

PR（从个人 fork 的分支提到上游 `master`）：

- `gh pr create --repo SHUD-System/AutoSHUD --base master --head DankerMu:feat/<topic>`
- `gh pr create --repo SHUD-System/SHUD --base master --head DankerMu:feat/<topic>`

### 同步上游更新到个人 fork

以 `SHUD/` 为例：

1. `cd SHUD`
2. `git fetch upstream`
3. `git switch master`
4. `git rebase upstream/master`（或使用 `git merge upstream/master`）
5. `git push origin master`

同步完成后，如需更新父仓库记录的子模块指针，再回到父仓库提交指针更新（见上文）。

## 注意事项

- 父仓库中不要把子模块当“普通目录”去 `git add SHUD/ AutoSHUD/`（submodule 已由 `.gitmodules` 管理）。
- `qhh/` 为本地大数据/输出目录，已在 `.gitignore` 中忽略；如需共享建议使用外部存储或 Git LFS（按需）。

