# runs 目录（不入库）

`runs/` 用于存放**可再生的中间结果与模型运行产物**（AutoSHUD 的 `dir.out`、SHUD 的 `output/` 等）。该目录默认被 `.gitignore` 忽略，不提交到 GitHub。

## 推荐结构

```
runs/
  qhh/
    baseline/     # 保持原 AutoSHUD→SHUD（CSV forcing）流水线的基线结果
    nc/           # 后续：SHUD 直接读 forcing NetCDF + 输出 NetCDF 的新结果

  <your-case>/
    baseline/
    nc/
```

> 建议：把“基线结果”和“新实现结果”分开存放，便于回归对比与验收。

