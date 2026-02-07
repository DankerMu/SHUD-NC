# configs（可复用配置）

本目录用于存放“可复用的适配层配置”，让项目不被某个 case 的目录结构绑死。

- `configs/forcing/`：不同 forcing 产品（CMFD/ERA5/GLDAS/FLDAS…）的读入与单位换算约定（供 SHUD 的 NetCDF forcing provider 使用）
- `configs/output/`：SHUD 输出 NetCDF 的 schema/变量清单/频率等约定

