# SHUD 河道 From/To 索引错配 Bug 验证实验方案（v2）

## 1. 实验目的与核心问题

本实验要用 **SHUD solver 的输出结果**（而非仅代码分析）证明三件事：

1. **Bug 存在**：旧版 rSHUD 生成的 `.sp.riv` 中的 Slope 值是错的；
2. **Fix 正确**：修复后的 Slope 值是对的（而不是"引入了新 bug"）；
3. **影响可量化**：错误 Slope 对 SHUD solver 输出（流量、水位）的影响幅度。

### 1.1 为什么不需要实测数据

验证 bug 不需要实测流量/水位。实测数据包含参数不确定性、forcing 误差、模型结构误差等混杂因素，无法归因到 Slope bug。

验证策略是**自对照 + 独立真值**：

```
truth（手工计算，绕开 rSHUD）  →  结果 T
fixed（修复后 rSHUD）          →  结果 F
old（旧版 rSHUD）              →  结果 O

T ≈ F  →  fix 是对的
T ≠ O  →  old 是错的
O 偏离解析预测  →  错误符合 bug 机制
```

### 1.2 "谁对谁错"的判据

**判据 1：独立 truth baseline**

`truth_manual` 的 `.sp.riv` 不经过任何版本的 `FromToNode`，直接从 polyline 端点坐标 + DEM 计算 Slope。它独立于 old 和 fixed，可以同时判定两者的正确性。

**判据 2：解析解对照**

对最简场景（单一均匀河道、稳态流），Manning 方程的稳态流量可手算：

$$Q = \frac{1}{n} A R^{2/3} S^{1/2}$$

- 给 SHUD 喂正确的 $S$ → solver 输出应趋近解析解 $Q_{\text{true}}$
- 给 SHUD 喂错误的 $S$ → solver 输出应偏离，且偏离量与 $\sqrt{S_{\text{bug}}/S_{\text{true}}}$ 一致

这是**物理定律级别的判据**：不是"两个版本不同"，而是"一个符合 Manning 方程，另一个不符合"。

---

## 2. 执行仓库与职责

### 2.1 主执行仓库

**`SHUD-NC` 根仓库**。

### 2.2 各仓库职责

| 仓库 | 角色 | 说明 |
|------|------|------|
| `SHUD-NC/` | 总入口 | 文档、脚本、fixture、运行结果 |
| `SHUD-NC/SHUD` | 唯一 solver | 所有 case 使用同一个二进制 |
| `SHUD-NC/rSHUD` | fixed implementation | 当前修复版，生成 fixed `.sp.riv` |
| `runs/_cmp/rSHUD-old/` | old implementation | 单独 checkout 修复前提交，生成 buggy `.sp.riv` |

---

## 3. 实验分层设计

实验分为三层，从简到繁，每层独立有价值：

### Layer 1：预处理层验证（不需要 solver）

**目标**：证明 old `.sp.riv` 的 Slope 是错的、fixed 是对的。

方法：对同一条合成河网，比较三种方式计算的 Slope：

| 来源 | 计算方式 | 是否经过 `FromToNode` |
|------|----------|----------------------|
| `truth` | 手工从 polyline 首尾端点 + DEM 提取高程 | **否** |
| `fixed` | 修复后 `shud.river()` | 是（`coord=xy, simplify=TRUE, force(coord)`） |
| `old` | 旧版 `shud.river()` | 是（`simplify=TRUE`，无 `coord=xy`，无 `force`） |

**判定**：
- `fixed == truth` → fix 正确
- `old != truth` → old 有 bug
- 偏差模式与索引错配机制一致 → bug 根因确认

### Layer 2：单河道解析解验证（最简 solver 运行）

**目标**：用物理定律判定"谁对谁错"。

方法：构造单条均匀直河道，初始水深已知，Manning 稳态流量可手算。

$$Q_{\text{analytical}} = \frac{1}{n} A(y_0) \cdot R(y_0)^{2/3} \cdot S_{\text{true}}^{1/2}$$

分别用 $S_{\text{true}}$ 和 $S_{\text{bug}}$ 运行 SHUD，对比出口流量与解析值。

**判定**：
- $Q_{\text{solver}}(S_{\text{true}}) \approx Q_{\text{analytical}}$ → solver + truth Slope 符合物理
- $Q_{\text{solver}}(S_{\text{bug}}) / Q_{\text{analytical}} \approx \sqrt{S_{\text{bug}} / S_{\text{true}}}$ → 偏差符合 Manning 预测

### Layer 3：多河道因果定位（完整 ablation 实验）

**目标**：在多河道耦合场景中定位 solver 的有效污染通道。

方法：5-case ablation（详见 §5），证明 Slope 是唯一有效污染入口、@point 不影响 solver。

---

## 4. 合成测试数据设计

### 4.1 网络结构

使用 **6-reach、3-type** 的简化合流网络：

```text
R1(type1) \
            R3(type2) \
R2(type1) /            R5(type3) -> R6(type3,outlet)
R4(type1) -------------/
```

拓扑真值（手工定义，写入 `truth_down.csv`）：

```text
R1 -> R3,  R2 -> R3,  R3 -> R5,  R4 -> R5,  R5 -> R6,  R6 -> -3 (outlet)
```

### 4.2 几何要求

| 参数 | 要求 | 目的 |
|------|------|------|
| 坐标系 | Projected/UTM 风格，量级 ~$10^6$ | 模拟真实场景 |
| 每段顶点数 | 40–80 | 确保 `st_simplify` 大幅减少顶点（N >> M），触发 bug |
| 噪声 | 仅对内部顶点加随机偏移 | 增加几何复杂度 |
| 端点 | 首尾端点精确共享 | 确保拓扑连通 |

### 4.3 DEM 要求

构造可控 DEM，使真实坡度精确可知。至少覆盖三类坡度：

| 类别 | 坡度范围 | 目的 |
|------|----------|------|
| 陡坡 | ~$10^{-2}$ | 验证大偏差场景 |
| 中坡 | $10^{-3} \sim 10^{-2}$ | 一般情况 |
| 缓坡 | ~$6 \times 10^{-4}$ | 接近 MINRIVSLOPE ($4 \times 10^{-4}$)，验证 clamp 效应 |

### 4.4 关于随机种子

AutoSHUD/rSHUD 的 mesh 和 river 生成流程是**完全确定性的**（经搜索确认：无 `set.seed`、无 `sample`、无 `runif` 在活跃代码路径中）。

方案中的 seed 仅用于**合成测试数据生成**时给河段中间顶点加的随机噪声（如 `gen_mock1_y_shape.R` 中的 `set.seed(42)` 控制锯齿偏移）。由于 bug 触发条件只需 $N > M$（顶点被简化即可），40+ 顶点的河段几乎必然触发，**不需要大量 seed 搜索**。

建议：固定 `set.seed(42)`（与现有 Mock1 一致），仅在生成失败时尝试 2–3 个备选 seed。

---

## 5. 实验 Case 设计

### 5.1 truth_manual（独立真值，核心判据）

- **不经过任何版本的 `FromToNode`**
- 直接从原始 polyline 提取每段首尾端点坐标
- 从 DEM 提取首尾端点高程
- 手工计算 `Slope = (z_from - z_to) / Length`
- 组装为 `.sp.riv` 格式

这是独立于 old 和 fixed 的第三方参照。

### 5.2 fixed_manual（修复后 rSHUD）

- 使用 `SHUD-NC/rSHUD` 当前修复版
- 调用 `shud.river(sl, dem, rivord=truth, rivdown=truth)`
- 锁定 Down/Type 为真值，仅测试 Slope 和 @point

### 5.3 old_manual（旧版 rSHUD）

- 使用 `runs/_cmp/rSHUD-old/` 的旧版实现
- 同样锁定 Down/Type 为真值
- 生成 buggy `.sp.riv`

### 5.4 slope-only_manual（因果隔离）

- 从 `fixed_manual.sp.riv` 复制
- **仅替换第一块第 4 列 Slope** 为 `old_manual` 的值
- 其他全部保持与 fixed 一致

### 5.5 point-only_manual（因果隔离）

- 从 `fixed_manual.sp.riv` 复制
- **仅替换第三块 @point** 为 `old_manual` 的 point block
- 其他全部保持一致

### 5.6 因果定位逻辑

| 观察到的结果 | 结论 |
|-------------|------|
| `old ≈ slope-only` | Slope 是 old 对 solver 的主要污染通道 |
| `point-only ≈ fixed` | @point 不影响 solver（符合 bug 报告：SHUD 不读取 @point） |
| `fixed ≈ truth` | fix 是正确的 |
| `old ≠ truth` | old 是错的 |

---

## 6. 解析解验证设计（Layer 2 核心）

### 6.1 场景

单条直河道，矩形截面，参数完全已知：

| 参数 | 值 | 说明 |
|------|-----|------|
| 长度 $L$ | 1000 m | |
| 宽度 $W$ | 10 m | |
| 深度 $D$ | 5 m | |
| Manning $n$ | 0.04 s/m$^{1/3}$ | rSHUD 默认值 |
| 真实坡度 $S_{\text{true}}$ | 0.01 | |
| Bug 坡度 $S_{\text{bug}}$ | 0.0004 (clamped) | 假设 bug 产生负坡度后被 MINRIVSLOPE 钳制 |
| 初始水深 $y_0$ | 2.0 m | |

### 6.2 解析预测

矩形截面：$A = W \cdot y_0 = 20\ \text{m}^2$，$P = W + 2y_0 = 14\ \text{m}$，$R = A/P \approx 1.43\ \text{m}$

$$Q_{\text{true}} = \frac{1}{0.04} \times 20 \times 1.43^{2/3} \times 0.01^{1/2} \approx 63.5\ \text{m}^3/\text{s}$$

$$Q_{\text{bug}} = \frac{1}{0.04} \times 20 \times 1.43^{2/3} \times 0.0004^{1/2} \approx 12.7\ \text{m}^3/\text{s}$$

$$\frac{Q_{\text{bug}}}{Q_{\text{true}}} = \sqrt{\frac{0.0004}{0.01}} = 0.2$$

### 6.3 判定标准

| 条件 | 含义 |
|------|------|
| $Q_{\text{solver}}(S_{\text{true}})$ 趋近 $Q_{\text{analytical}}$ | solver + truth Slope 符合物理 |
| $Q_{\text{solver}}(S_{\text{bug}}) / Q_{\text{solver}}(S_{\text{true}}) \approx 0.2$ | 偏差量符合 Manning $\sqrt{S}$ 关系 |
| 偏差不可归因于"fix 引入了新错误" | 因为判据是独立的物理定律 |

注意：SHUD 的非稳态求解器不会精确达到稳态 Manning 流量，但在足够长的模拟时间后应趋近。验收时允许 $\pm 10\%$ 偏差（来自瞬态效应和水面梯度项）。

---

## 7. 分阶段执行计划

### Phase 0：版本冻结与工作区准备

**目标**：固定 old/fixed/solver 三者版本。

```bash
git submodule update --init --recursive
git -C SHUD rev-parse --short HEAD
git -C rSHUD rev-parse --short HEAD
git clone https://github.com/DankerMu/rSHUD.git runs/_cmp/rSHUD-old
git -C runs/_cmp/rSHUD-old checkout <old_commit>
```

**产物**：`runs/ftbug/version-lock.json`

**通过条件**：三者 commit SHA 固定并记录。

---

### Phase 1：生成合成数据 + truth baseline

**目标**：生成 6-reach 河网 + 可控 DEM + 独立 truth `.sp.riv`。

**脚本**：`tools/r/build_ftbug_fixture.R`

**关键**：truth `.sp.riv` 的 Slope 直接从 polyline 端点 + DEM 手工计算，**不调用 `FromToNode`**。

**产物**：
```text
testdata/ftbug/
  river.*           # 6-reach polyline
  dem.tif           # 可控 DEM
  basin.*           # 流域边界
  truth_down.csv    # 手工拓扑
  truth_type.csv    # 手工 order
  truth_nodes.csv   # 手工端点坐标 + 高程
  truth.sp.riv      # 独立真值 .sp.riv
```

**通过条件**：
- 6 reach, 3 type
- truth Slope 可手工验证（DEM 是我们造的，高程精确已知）
- 至少 1 reach 真实坡度 > 2 × MINRIVSLOPE（避免被 clamp 掩盖）
- 至少 1 reach 真实坡度接近 MINRIVSLOPE（测试 clamp 边界）

---

### Phase 2：生成 old/fixed `.sp.riv` 变体

**目标**：分别用 old 和 fixed rSHUD 生成 `.sp.riv`，并构造 slope-only 和 point-only 变体。

**脚本**：`tools/r/generate_riv_variants.R`

**流程**（固定 `set.seed(42)`，不做大规模 seed 搜索）：

1. 用 fixed rSHUD 生成 `fixed.sp.riv`
2. 用 old rSHUD 生成 `old.sp.riv`
3. 从 `fixed.sp.riv` 复制，替换 Slope 列 → `slope-only.sp.riv`
4. 从 `fixed.sp.riv` 复制，替换 point block → `point-only.sp.riv`

**通过条件**（预处理层验证，Layer 1 判定）：
- `fixed.sp.riv` 的 Slope 与 `truth.sp.riv` 的 Slope **完全一致**（max diff = 0）
- `old.sp.riv` 的 Slope 与 `truth.sp.riv` **不一致**（至少 1 reach 相对偏差 > 20%）
- `old` 与 `fixed` 的 Down/Type/Length **完全相同**（bug 不影响这些字段）
- `slope-only` 仅第一块第 4 列不同
- `point-only` 仅第三块不同

**如果 `fixed != truth`**：说明 fix 本身有问题，实验暂停排查。

---

### Phase 3：构建最小 SHUD 输入底座

**目标**：构建极小但完整的 SHUD 输入集。

**脚本**：`tools/r/build_ftbug_shud_base.R`

**要求**：
- 10–20 个三角形单元
- 每条 reach 至少一个相邻单元
- 统一 soil/lc/geol
- 单一 outlet

**两个 profile**：

| Profile | Forcing | 初始条件 | 河-坡交换 | 模拟时长 | 输出间隔 |
|---------|---------|----------|-----------|----------|----------|
| `route-only` | 全 0 | 河道水深 = 梯度波 | 极小化 | 5–10 天 | 1 小时 |
| `coupled` | 短时降雨脉冲 | 平缓水位 | 正常非零 | 30–60 天 | 3 小时 |

**通过条件**：fixed case 能跑通短时间窗。

---

### Phase 4：solver 只读 diagnostics（可选但推荐）

**目标**：导出 solver 内部变量，验证完整传播链。

**原则**：只加输出，不改计算。所有 case 用同一个 instrumented binary。

**输出**：
```text
diag_riv.tsv:  time, iRiv, BedSlope, QrivUp, QrivDown, QrivSurf, QrivSub, DYriv, uYriv
```

---

### Phase 5：运行实验并比较

**运行 5 个 case**（route-only 和 coupled 各一轮）：
- `truth_manual`
- `fixed_manual`
- `old_manual`
- `slope-only_manual`
- `point-only_manual`

**比较脚本**：`tools/compare_ftbug.py`

---

## 8. 量化验收标准

### 8.1 噪声地板

$$\mathrm{noise}(M) = \max\left(\mathrm{diff}(\text{fixed}, \text{truth}; M),\ \mathrm{diff}(\text{point-only}, \text{fixed}; M),\ \epsilon_{\text{abs}}\right)$$

其中 $\epsilon_{\text{abs}}$ 为绝对最小噪声地板，取 CVODE solver tolerance 量级：
- 流量指标：$\epsilon_{\text{abs}} = 10^{-8}\ \text{m}^3/\text{s}$
- 水位指标：$\epsilon_{\text{abs}} = 10^{-10}\ \text{m}$
- 坡度指标：$\epsilon_{\text{abs}} = 10^{-12}$

**说明**：由于 SHUD 不读取 @point（代码已注释），`diff(point-only, fixed)` 理论上严格为 0；如果 fix 正确，`diff(fixed, truth)` 也接近 0。$\epsilon_{\text{abs}}$ 防止噪声地板退化为 0 导致阈值无意义。

### 8.2 route-only 验收条件

| 条件 | 公式 | 含义 |
|------|------|------|
| A | $\mathrm{diff}(\text{old}, \text{slope-only}) \le 10 \times \mathrm{noise}$ | Slope 是 old 的主要污染入口 |
| B | $\mathrm{diff}(\text{fixed}, \text{truth}) \le 10 \times \mathrm{noise}$ | fix 正确 |
| C | $\mathrm{diff}(\text{point-only}, \text{fixed}) \le 10 \times \mathrm{noise}$ | @point 不影响 solver |
| D | $\mathrm{diff}(\text{old}, \text{fixed}) \ge 100 \times \mathrm{noise}$ | bug 影响显著 |

### 8.3 解析解验收条件

| 条件 | 公式 | 含义 |
|------|------|------|
| E | $\|Q_{\text{solver}}(S_{\text{true}}) - Q_{\text{analytical}}\| / Q_{\text{analytical}} < 0.1$ | solver + truth 符合物理 |
| F | $Q_{\text{solver}}(S_{\text{bug}}) / Q_{\text{solver}}(S_{\text{true}}) \approx \sqrt{S_{\text{bug}} / S_{\text{true}}}$（允许 $\pm 20\%$） | 偏差符合 Manning 预测 |

### 8.4 综合判定

若 A–F 同时成立：

1. **Bug 存在**：old Slope 偏离 truth（Layer 1）且导致 solver 输出偏离解析解（Layer 2）
2. **Fix 正确**：fixed Slope = truth（Layer 1）且 solver 输出符合解析解（Layer 2）
3. **污染通道 = Slope only**：old ≈ slope-only，point-only ≈ fixed（Layer 3）
4. **影响可量化**：偏差幅度由 $\sqrt{S_{\text{bug}}/S_{\text{true}}}$ 给出

---

## 9. 建议目录布局

```text
SHUD-NC/
  docs/
    SHUD_river_bug_experiment_plan.md   # 本文档
  testdata/
    ftbug/
      river.*
      dem.tif
      basin.*
      truth_down.csv
      truth_type.csv
      truth_nodes.csv
      truth.sp.riv
  tools/
    r/
      build_ftbug_fixture.R         # Phase 1: 生成合成数据 + truth
      generate_riv_variants.R       # Phase 2: 生成 old/fixed/slope-only/point-only
      build_ftbug_shud_base.R       # Phase 3: 构建最小 SHUD 输入
    compare_ftbug.py                # Phase 5: 比较 solver 输出
  runs/                             # 不入库
    _cmp/rSHUD-old/                 # old rSHUD checkout
    ftbug/
      version-lock.json
      preprocess/                   # .sp.riv 变体
      route-only/<case>/            # route-only 运行结果
      coupled/<case>/               # coupled 运行结果
```

---

## 10. 执行顺序与里程碑

| 阶段 | 产物 | 里程碑判定 |
|------|------|-----------|
| Phase 0 | version-lock.json | 版本固定 |
| Phase 1 | truth.sp.riv + fixture | `fixed == truth` 且 `old != truth` |
| Phase 2 | 5 种 .sp.riv 变体 | Layer 1 通过 |
| Phase 3 | SHUD 输入底座 | fixed case 跑通 |
| Phase 4 | instrumented solver（可选） | diagnostics 可读 |
| Phase 5 | solver 输出比较 | 条件 A–F 判定 |

**最关键的里程碑**：

> Phase 1 完成时，如果 `fixed == truth` 且 `old != truth`，就已经在预处理层证明了 bug 存在和 fix 正确——即使后续 Phase 全部跳过，这个结论也成立。

后续 Phase 是量化影响和因果定位，属于锦上添花。

---

## 11. 注意事项

### 11.1 出口 BC 标记

Bug 报告 §B 记录了 `-4 → -3` 的 BC 覆盖问题。在本实验中：
- 合成 fixture 统一使用 `-3`（排除 BC 变量）
- 如果后续用 QHH 数据做补充验证，需单独控制 BC 值

### 11.2 模拟时长

SHUD 是非稳态求解器，解析解对照需要足够长的模拟时间使河道趋近稳态。建议：
- route-only：5–10 天，输出间隔 1 小时
- coupled：30–60 天，输出间隔 3 小时

### 11.3 已有测试资源

`testdata/mock_river/` 下已有 3 套 mock 数据和验证脚本（`test_index_mismatch.R`、`gen_report_figures.R`）。这些已验证了预处理层的 bug（Layer 1）。本实验的增量价值在 Layer 2（解析解）和 Layer 3（solver 输出因果定位）。

---

## 12. 一句话摘要

**本方案用"独立 truth baseline + Manning 解析解"建立谁对谁错的判据，然后用 slope-only/point-only ablation 定位 solver 的有效污染通道，全程不依赖实测数据。**
