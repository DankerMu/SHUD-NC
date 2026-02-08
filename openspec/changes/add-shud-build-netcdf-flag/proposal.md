# Change: Add optional NetCDF build flag to SHUD Makefile

## Why
阶段 A/B 都需要链接 NetCDF（netcdf-c）。必须确保：
- 默认构建不依赖 NetCDF（避免破坏 baseline 用户环境）
- 在需要时可通过开关启用 NetCDF（统一用于 forcing 与 output）

## Scope
- **Repo**: `DankerMu/SHUD-up`
- Makefile 增加可选开关（例如 `NETCDF=1`）：
  - 自动探测 `nc-config --cflags/--libs` 或 `pkg-config netcdf`
  - 加入 include/lib flags 与 `-lnetcdf`
- 文档补充：macOS/Linux 安装提示（保持简短）

## Non-goals
- 不在本 change 实现 NetCDF forcing/output 逻辑，只铺设构建能力。

## Acceptance criteria
- [ ] `make shud` 在无 NetCDF 环境下仍可编译（与当前一致）。
- [ ] `make shud NETCDF=1` 在有 NetCDF 环境下可编译并链接成功。
- [ ] 构建日志能看出是否启用 NETCDF 以及使用的 flags（便于排障）。

## Test plan
- `make clean && make shud`
- `make clean && make shud NETCDF=1`（本机有 netcdf 时）

