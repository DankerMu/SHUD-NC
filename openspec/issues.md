# Issue Templates (generated from OpenSpec backlog)

使用方式（推荐）：
- 先把父仓库的 OpenSpec 与 `openspec/changes/<id>/` 提交到 `DankerMu/SHUD-NC`
- 然后在对应仓库创建 issue（`DankerMu/SHUD-up` / `DankerMu/SHUD-NC`）
- issue 里引用 `OpenSpec change id: <id>`，并把 `proposal.md` 的内容作为 issue body

> 备注：当前 `DankerMu/AutoSHUD` 仓库 issues 未开启；如未来需要在 AutoSHUD 跟踪任务，请先启用 issues。

## Epic（可选）

### Repo: `DankerMu/SHUD-NC`
Title: `Epic: SHUD NetCDF forcing + output migration (A/B)`

Body:
- Problem: 需要把 SHUD forcing 输入迁移到直接读 NetCDF，并输出标准 NetCDF，同时保留 baseline。
- Scope:
  - Phase A: NetCDF forcing（CMFD2, ERA5）
  - Phase B: NetCDF output（CF/UGRID）
  - Meta-runner: 单入口 `projects/<case>/shud.yaml` 支撑 baseline/nc profile
- Acceptance:
  - [ ] baseline profile 结果不变
  - [ ] nc profile 可跑通（forcing netcdf + output netcdf）
  - [ ] 提供回归对比工具
- Backlog (OpenSpec change ids):
  - [ ] add-shud-forcing-mode-config
  - [ ] refactor-shud-forcing-provider-abstraction
  - [ ] add-shud-build-netcdf-flag
  - [ ] add-shud-netcdf-forcing-cmfd2
  - [ ] add-shud-netcdf-forcing-era5
  - [ ] update-meta-runner-render-shud-cfg
  - [ ] update-meta-runner-nc-profile-run
  - [ ] add-shud-output-mode-config
  - [ ] add-shud-printctrl-sink-interface
  - [ ] add-shud-netcdf-output-core
  - [ ] add-shud-netcdf-output-ugrid-mesh
  - [ ] add-shud-netcdf-output-riv-lake
  - [ ] add-shud-netcdf-output-metadata-mask-fill
  - [ ] add-tools-regression-compare

## Phase A：Forcing NetCDF（SHUD 子模块）

### Repo: `DankerMu/SHUD-up`
Title: `[A0] Parse FORCING_MODE/FORCING_CFG in cfg.para (default CSV)`

Body:
- OpenSpec change id: `add-shud-forcing-mode-config`
- See: `openspec/changes/add-shud-forcing-mode-config/proposal.md`
- Acceptance criteria / Test plan: 同 proposal.md

### Repo: `DankerMu/SHUD-up`
Title: `[A1] Refactor forcing access behind ForcingProvider abstraction`

Body:
- OpenSpec change id: `refactor-shud-forcing-provider-abstraction`
- See: `openspec/changes/refactor-shud-forcing-provider-abstraction/proposal.md`
- Acceptance criteria / Test plan: 同 proposal.md

### Repo: `DankerMu/SHUD-up`
Title: `[A2] Makefile: optional NetCDF build flag (NETCDF=1)`

Body:
- OpenSpec change id: `add-shud-build-netcdf-flag`
- See: `openspec/changes/add-shud-build-netcdf-flag/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[A3] NetCDF forcing provider: CMFD2 (NEAREST + unit conversion)`

Body:
- OpenSpec change id: `add-shud-netcdf-forcing-cmfd2`
- See: `openspec/changes/add-shud-netcdf-forcing-cmfd2/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[A4] NetCDF forcing provider: ERA5 subset (accumulated tp/ssr)`

Body:
- OpenSpec change id: `add-shud-netcdf-forcing-era5`
- See: `openspec/changes/add-shud-netcdf-forcing-era5/proposal.md`

## Meta-runner：父仓库编排层

### Repo: `DankerMu/SHUD-NC`
Title: `[T1] tools/shudnc.py: render SHUD cfg overlays (render-shud-cfg)`

Body:
- OpenSpec change id: `update-meta-runner-render-shud-cfg`
- See: `openspec/changes/update-meta-runner-render-shud-cfg/proposal.md`

### Repo: `DankerMu/SHUD-NC`
Title: `[T2] tools/shudnc.py: enable nc profile validate/run`

Body:
- OpenSpec change id: `update-meta-runner-nc-profile-run`
- See: `openspec/changes/update-meta-runner-nc-profile-run/proposal.md`

## Phase B：Output NetCDF（SHUD 子模块）

### Repo: `DankerMu/SHUD-up`
Title: `[B0] Parse OUTPUT_MODE/NCOUTPUT_CFG in cfg.para (default LEGACY)`

Body:
- OpenSpec change id: `add-shud-output-mode-config`
- See: `openspec/changes/add-shud-output-mode-config/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[B1] Print_Ctrl: add sink interface (legacy unchanged)`

Body:
- OpenSpec change id: `add-shud-printctrl-sink-interface`
- See: `openspec/changes/add-shud-printctrl-sink-interface/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[B2] NetCDF output core: element file + time axis append`

Body:
- OpenSpec change id: `add-shud-netcdf-output-core`
- See: `openspec/changes/add-shud-netcdf-output-core/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[B3] NetCDF output: write UGRID mesh in element file`

Body:
- OpenSpec change id: `add-shud-netcdf-output-ugrid-mesh`
- See: `openspec/changes/add-shud-netcdf-output-ugrid-mesh/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[B4] NetCDF output: add riv/lake files`

Body:
- OpenSpec change id: `add-shud-netcdf-output-riv-lake`
- See: `openspec/changes/add-shud-netcdf-output-riv-lake/proposal.md`

### Repo: `DankerMu/SHUD-up`
Title: `[B5] NetCDF output: metadata registry + masks + fill values`

Body:
- OpenSpec change id: `add-shud-netcdf-output-metadata-mask-fill`
- See: `openspec/changes/add-shud-netcdf-output-metadata-mask-fill/proposal.md`

## Regression tools（父仓库）

### Repo: `DankerMu/SHUD-NC`
Title: `[R] tools: sampled regression compare (forcing + output)`

Body:
- OpenSpec change id: `add-tools-regression-compare`
- See: `openspec/changes/add-tools-regression-compare/proposal.md`

