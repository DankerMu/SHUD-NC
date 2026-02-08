# Change: Add regression compare tools (baseline vs nc)

## Why
阶段 A/B 的验收核心是“可回归”。需要在父仓库提供一键对比工具，帮助快速验证：
- forcing：NetCDF vs baseline CSV（点位/时刻抽样）
- output：NetCDF vs legacy（time 与数值抽样）

## Scope
- **Repo**: `DankerMu/SHUD-NC`
- 在 `tools/` 增加对比脚本（Python 优先）：
  - forcing 抽样对比：指定站点 idx + 时刻列表，输出差值统计
  - output 抽样对比：读取 legacy（CSV 或二进制）与 NetCDF，抽样变量/对象索引对齐
- 约定输出格式：stdout summary + 可保存为 `runs/.../compare/*.json`

## Non-goals
- 不做全量逐点对比（成本高）；先做抽样 + 可扩展。

## Acceptance criteria
- [ ] 提供可复用命令行接口（输入 run_dir / prj / 变量名）。
- [ ] 对比结果包含：max abs diff、mean diff、样本点列表。

## Test plan
- 以 QHH baseline + nc 短模拟为输入，运行对比脚本并生成 summary

