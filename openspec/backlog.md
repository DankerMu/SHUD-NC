# SHUD-NC Backlog (OpenSpec)

本文件用于把 `/docs/*方案与SPEC*` 拆分为 **可 review、可实现、可回归** 的 backlog 条目。

约定：
- 1 个 OpenSpec change ≈ 1 个 GitHub issue ≈ 1 个 PR（尽量）。
- change 的 `proposal.md`/`tasks.md` 写在父仓库；真正实现落在对应仓库（`SHUD/` 子模块为主，父仓库 tools 为辅）。
- 依赖关系在各 change 的 proposal 里标注；这里给出 “推荐执行顺序”。

## 阶段 A：SHUD 直接读取 forcing NetCDF

1. `add-shud-forcing-mode-config` (repo: `DankerMu/SHUD-up`)
2. `refactor-shud-forcing-provider-abstraction` (repo: `DankerMu/SHUD-up`)
3. `add-shud-build-netcdf-flag` (repo: `DankerMu/SHUD-up`)
4. `add-shud-netcdf-forcing-cmfd2` (repo: `DankerMu/SHUD-up`)
5. `add-shud-netcdf-forcing-era5` (repo: `DankerMu/SHUD-up`)
6. `update-meta-runner-render-shud-cfg` (repo: `DankerMu/SHUD-NC`)
7. `update-meta-runner-nc-profile-run` (repo: `DankerMu/SHUD-NC`)

## 阶段 B：SHUD 输出写规范 NetCDF（CF/UGRID）

8. `add-shud-output-mode-config` (repo: `DankerMu/SHUD-up`)
9. `add-shud-printctrl-sink-interface` (repo: `DankerMu/SHUD-up`)
10. `add-shud-netcdf-output-core` (repo: `DankerMu/SHUD-up`)
11. `add-shud-netcdf-output-ugrid-mesh` (repo: `DankerMu/SHUD-up`)
12. `add-shud-netcdf-output-riv-lake` (repo: `DankerMu/SHUD-up`)
13. `add-shud-netcdf-output-metadata-mask-fill` (repo: `DankerMu/SHUD-up`)

## 回归/对比工具（可并行）

14. `add-tools-regression-compare` (repo: `DankerMu/SHUD-NC`)

