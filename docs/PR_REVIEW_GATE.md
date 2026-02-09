# PR Review Gate（gh-pr-review）

本仓库启用了一个“可强制执行”的 PR 合并门禁：**只有当 `gh-pr-review` 状态检查为通过（success）且 CI 通过时，PR 才允许 merge**。

> 说明：GitHub 无法直接验证你“是否真的在本地运行了某个命令”，因此门禁采用“可验证产物”的方式——要求 PR 评论区存在一个带 marker 的 review 结果评论，并由 GitHub Actions 将其转换成一个 required status check（`gh-pr-review`）。

## 机制概览

- 工作流：`.github/workflows/gh-pr-review-gate.yml`
- 受保护分支：默认分支（例如 `main` / `master`）
- 必须通过的检查：
  - CI（按仓库实际配置）
  - `gh-pr-review`（由门禁工作流维护）

## 使用方式（让 PR 可 merge）

### 1) PR 有新提交时：`gh-pr-review` 会变为 pending

每次 PR `opened/synchronize/reopened`，门禁工作流会把 PR head commit 的 `gh-pr-review` 状态置为 **pending**，以确保“新提交必须重新 review”。

### 2) 运行本地 review（推荐：使用 `$gh-pr-review`）

按约定在本地完成 review，并把 review 结论以评论形式贴到 PR 下（可以是普通文字 + marker）。

### 3) 在评论末尾追加 marker（必须）

marker 是一行 HTML comment，格式固定：

```text
<!-- gh-pr-review: sha=<SHA> decision=PASS|FAIL score=<1-5> -->
```

规则：
- `sha` 必须匹配当前 PR 的 **head commit SHA**（允许使用 7 位短 SHA 前缀）。
- `decision=PASS` 且 `score>=4` 才会把 `gh-pr-review` 状态置为 `success`。
- `decision=FAIL` 或 `score<4` 会把状态置为 `failure`（继续阻止 merge）。
- marker 只接受来自 `OWNER|MEMBER|COLLABORATOR` 的评论（避免外部用户伪造）。

#### 获取 PR head SHA（CLI）

```bash
# 用 REST API 获取 head sha（推荐，稳定）
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER> --jq .head.sha
```

示例：

```bash
gh api repos/DankerMu/SHUD-NC/pulls/123 --jq .head.sha
```

## 常见问题

### Q: 我已经评论了 marker，为什么 `gh-pr-review` 还没变绿？

常见原因：
- marker 里的 `sha` 不是当前 head commit（PR 更新后 head sha 会变，需重新贴 marker）。
- marker 格式不匹配（必须一行，且包含 `sha/decision/score` 三个字段）。
- `score` 小于 4 或 `decision=FAIL`。

### Q: 为什么不用 GitHub 的 Approve？

本仓库流程把“是否通过 review”落到可追踪的 status check（`gh-pr-review`），从而避免“单人维护时无法满足非作者 approve”的限制。你仍然可以使用 GitHub Review（approve/request-changes），但 merge 的硬门禁由 `gh-pr-review` + CI 决定。
