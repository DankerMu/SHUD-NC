# SHUD 河道 From/To 索引错配 Bug 验证 — 理想实验报告

> 实验分支：`exp/river-bug-verification`
> 开始日期：2026-03-26
> 状态：Phase 0–2 完成，Phase 3+ 进行中

---

## 实验目的

用 **SHUD solver 的输出结果**（而非仅代码分析）证明三件事：

1. **Bug 存在**：旧版 rSHUD 生成的 `.sp.riv` 中的 Slope 值是错的
2. **Fix 正确**：修复后的 Slope 值是对的（而不是"引入了新 bug"）
3. **影响可量化**：错误 Slope 对 SHUD solver 输出（流量、水位）的偏差幅度

核心方法论：**独立 truth baseline + Manning 解析解 + ablation 因果定位**，全程不依赖实测数据。

---

## Phase 0：版本冻结

### 目的

固定 solver、fixed rSHUD、old rSHUD 三者版本，确保对比基线不漂移。

### 冻结结果

| 组件 | Commit | 角色 | 关键代码差异 |
|------|--------|------|-------------|
| SHUD solver | `752d27a` | 唯一求解器，所有 case 共用 | 不修改 |
| rSHUD (fixed) | `e0d407d` | 修复版预处理 | `River.R:28`: `FromToNode(sp.slt, coord=xy, simplify=TRUE)` + `force(coord)` + `snap_coords_to_ref` |
| rSHUD (old) | `4e6afef` | 修复前预处理 | `River.R:28`: `FromToNode(sp.slt, simplify=TRUE)` — 无 `coord=xy`，触发惰性求值 bug |

#### 修复的 3 个 commit

| SHA | 说明 |
|-----|------|
| `badfd44` | 核心修复：显式传 `coord=xy` + `force(coord)` 防止惰性求值 |
| `e6a9878` | 增加 `snap_coords_to_ref`：简化后端点 snap 回原始坐标表 |
| `fcfa676` | 修正 snap 容差为动态值 |

Old rSHUD 已 clone 到 `runs/_cmp/rSHUD-old/` 并 checkout 到 `4e6afef`（修复前最后一个提交）。版本锁定记录在 `runs/ftbug/version-lock.json`。

---

## Phase 1：合成测试数据 + 独立 Truth Baseline

### 目的

生成一套可控的合成河网 + DEM，并计算**完全绕开 rSHUD 的独立 truth baseline**。Truth 的 Slope 直接从 polyline 端点坐标 + DEM 解析公式手算，不经过 `FromToNode`，因此独立于 old 和 fixed 两个版本——可以同时判定两者的正确性。

### 1.1 合成河网设计

6 条河段、3 种 type 的合流网络：

```
R1(type1) \
            R3(type2) \
R2(type1) /            R5(type3) → R6(type3, outlet)
R4(type1) ─────────────/
```

拓扑关系（手工定义，不依赖任何自动推断）：

| 河段 | Down | Type | 说明 |
|------|------|------|------|
| R1 | 3 | 1 | 支流，汇入 R3 |
| R2 | 3 | 1 | 支流，汇入 R3 |
| R3 | 5 | 2 | 汇流段 |
| R4 | 5 | 1 | 侧支流，汇入 R5 |
| R5 | 6 | 3 | 主干 |
| R6 | -3 | 3 | 出口 |

![图 1：合成河网总览](/testdata/ftbug/fig1_network_overview.png)

**图 1 解读**：
- 蓝色 = Type 1（支流 R1、R2、R4），绿色 = Type 2（汇流段 R3），红色 = Type 3（主干 R5、出口 R6）
- 黑色实心圆 = From 端点，黑色三角 = To 端点，黄色大圆 = 交汇节点
- 箭头指示流向（From → To，上游 → 下游）
- R1 和 R2 从北侧汇入 R3，R4 从西侧汇入 R5，R5 向东接 R6 南下至出口

### 1.2 几何特性

| 河段 | 顶点数 | 长度 (m) | Jitter (m) |
|------|--------|----------|------------|
| R1 | 61 | 1045.9 | ±11 |
| R2 | 57 | 994.7 | ±11 |
| R3 | 67 | 775.6 | ±9 |
| R4 | 49 | 752.0 | ±8 |
| R5 | 73 | 918.9 | ±4 |
| R6 | 55 | 1720.2 | ±8 |
| **合计** | **362** | | |

- 坐标系：EPSG:32648 (WGS 84 / UTM zone 48N)，坐标量级 ~5×10⁵
- 每段 49–73 个顶点，**仅内部顶点加随机噪声**（perpendicular 方向），端点精确共享
- `set.seed(42)` 保证可复现

**Bug 触发条件验证**：`st_simplify` 以 `tol = (extent_x) × 0.01 ≈ 18 m` 简化后，362 个原始顶点被压缩到仅 **7 个**唯一端点。N/M = 362/7 ≈ **51.7×**，远超索引错配的触发阈值。

![图 4：顶点密度与 simplify 效果](/testdata/ftbug/fig4_vertex_density.png)

**图 4 解读**：
- 彩色点 = 原始顶点（颜色编码沿线位置），灰色线 = 原始 polyline
- 每段标注了顶点数（R1: 61, R2: 57, ... R5: 73）
- 左下框注：simplify tolerance = 18 m，原始 362 顶点 → 简化后仅 7 个唯一端点
- 这意味着旧版 `FromToNode(simplify=TRUE)` 返回的 `ft` 索引范围仅为 1–7，却被用于查询 362 行的原始 `xy` 表——索引体系完全不兼容

### 1.3 可控 DEM

DEM 使用解析公式构造，真实高程**精确可知**：

$$z = 2500 - 0.0006 \times (x - 500000) + 0.01 \times (y - 4200000)$$

- 分辨率：100 m
- 主梯度方向：y 方向（北高南低，系数 0.01），x 方向有微弱倾斜（系数 -0.0006）
- 所有河段端点对齐到 DEM 栅格中心，DEM 提取高程与解析公式**零误差**

![图 2：DEM 高程面与河网叠加](/testdata/ftbug/fig2_dem_with_rivers.png)

**图 2 解读**：
- 底图 = DEM 高程面，颜色从深绿（高，~2515 m）到浅黄/白（低，~2480 m）
- 河网叠加为黑色线，蓝圆 = From 端点（含高程标注），红三角 = To 端点（含高程标注）
- 可以直观看到：R1/R2 起始高程 ~2514 m，经 R3 交汇处 2505 m → R5 终点 2499 m → R6 出口 2482 m
- DEM 公式标注在图底部，确保可溯源

### 1.4 坡度分类

| 河段 | 真实坡度 | 分类 | 说明 |
|------|---------|------|------|
| R1 | 0.00878 | medium | |
| R2 | 0.00887 | medium | |
| R3 | 0.00683 | medium | |
| R4 | 0.00322 | medium | |
| R5 | **0.000588** | **gentle** | 接近 MINRIVSLOPE = 4×10⁻⁴，测试 clamp 边界 |
| R6 | **0.00992** | **steep** | 最大坡度，bug 导致的流量偏差最显著 |

![图 3：各河段坡度（log 尺度）](/testdata/ftbug/fig3_slope_profile.png)

**图 3 解读**：
- 柱状图为 log 纵坐标，颜色编码坡度类别：红 = steep，橙 = medium，绿 = gentle
- 灰色虚线 = MINRIVSLOPE = 4×10⁻⁴（SHUD solver 的坡度下限钳制值）
- **R5**（gentle, 5.88×10⁻⁴）仅比 MINRIVSLOPE 高约 47%，若 bug 导致其坡度变为负值，将被钳制到 4×10⁻⁴，偏差相对较小
- **R6**（steep, 9.92×10⁻³）坡度最大，若 bug 将其钳制到 4×10⁻⁴，Manning 流量将衰减至真值的 $\sqrt{4 \times 10^{-4} / 9.92 \times 10^{-3}} \approx 20\%$

### 1.5 独立 Truth Baseline

`truth.sp.riv` 的生成路径**完全绕开 rSHUD**：

```
polyline 端点坐标（直接从 sf geometry 提取首尾点）
       ↓
DEM 解析公式（z = 2500 - 0.0006*(x-500000) + 0.01*(y-4200000)）
       ↓
Slope = (From.z - To.z) / polyline_length
       ↓
手工组装 .sp.riv 格式（不调用 FromToNode / shud.river / extractCoords）
```

验证确认：
- 6 个端点的 From.z / To.z 与 DEM 解析公式**差异为 0**
- 6 条河段的 Slope 与手算 `(From.z - To.z) / Length` **差异 < 10⁻¹⁰**（浮点精度量级）
- 脚本中不含任何 rSHUD 函数调用（`grep` 确认）

Truth baseline 是后续所有比较的**独立参照**——无论 old 有 bug 还是 fix 引入了新 bug，truth 都能区分出来。

### 1.6 Truth .sp.riv 内容

```
6 6
Index Down Type Slope       Length      BC
1     3    1    0.0087770745 1045.906584 0
2     3    1    0.0088672420  994.672305 0
3     5    2    0.0068331939  775.625587 0
4     5    1    0.0032178838  752.047051 0
5     6    3    0.0005876630  918.893976 0
6    -3    3    0.0099173117 1720.224233 0
```

### 1.7 产物清单

| 文件 | 说明 |
|------|------|
| `testdata/ftbug/river.shp` (+.shx/.dbf/.prj) | 6-reach 合成河网 |
| `testdata/ftbug/dem.tif` | 解析公式 DEM |
| `testdata/ftbug/basin.shp` (+.shx/.dbf/.prj) | 流域边界多边形 |
| `testdata/ftbug/truth_down.csv` | 手工拓扑 |
| `testdata/ftbug/truth_type.csv` | 手工 stream order |
| `testdata/ftbug/truth_nodes.csv` | 手工端点坐标 + 高程 |
| `testdata/ftbug/truth.sp.riv` | 独立 truth baseline |
| `testdata/ftbug/manifest.yaml` | 元数据（seed、CRS、DEM 公式等） |
| `testdata/ftbug/fig1–fig4.png` | 可视化图 |
| `tools/r/build_ftbug_fixture.R` | 生成脚本（可复现） |
| `tools/r/plot_ftbug_fixture.R` | 可视化脚本 |

### 1.8 Phase 1 通过条件

| 检查项 | 结果 |
|--------|------|
| 6 reach, 3 type | ✓ |
| 不依赖 rSHUD | ✓ (`grep` 确认无 `FromToNode`/`shud.river`/`extractCoords` 引用) |
| DEM 高程与解析公式一致 | ✓ (6 个端点差异 = 0) |
| Slope 手算一致 | ✓ (差异 < 10⁻¹⁰) |
| 坡度三类覆盖 | ✓ (steep: R6, medium: R1–R4, gentle: R5) |
| 近 MINRIVSLOPE 覆盖 | ✓ (R5 = 5.88×10⁻⁴, 距 4×10⁻⁴ 仅 47%) |
| 所有坡度为正 | ✓ |
| 端点精确共享 | ✓ (5 个交汇点全部精确匹配) |
| .sp.riv 格式正确 | ✓ (3 块: 6×6, 3×9, 6×6, 共 21 行) |
| Simplify 触发 | ✓ (N=362 → M=7, 比值 51.7×) |

---

## Phase 2：生成 old / fixed `.sp.riv` 变体

### 目的

用 old rSHUD（`4e6afef`）和 fixed rSHUD（`e0d407d`）分别处理同一套合成河网，生成 5 种 `.sp.riv` 变体，在预处理层面验证：
- `fixed ≈ truth` → 修复正确
- `old ≠ truth` → 旧版有 bug
- Down/Type/Length 不受 bug 影响

### 2.1 实验方法

对同一套 Phase 1 合成河网（`testdata/ftbug/river.shp` + `dem.tif`），锁定 `rivord` 和 `rivdown` 为手工真值，分别调用：

| 版本 | 调用 | 差异来源 |
|------|------|---------|
| fixed rSHUD (`e0d407d`) | `shud.river(sl, dem, rivord=truth, rivdown=truth)` | Slope + @point 来自修复后的 `FromToNode` |
| old rSHUD (`4e6afef`) | 同上 | Slope + @point 来自 buggy `FromToNode` |

锁定 Down/Type 的目的：将差异**严格压缩到 Slope 和 @point**，排除拓扑推断的干扰。

然后构造两个因果隔离变体：

| 变体 | 构造方式 | 目的 |
|------|---------|------|
| `slope-only.sp.riv` | fixed 底座 + old 的 Slope 列 | 隔离 Slope 的独立影响 |
| `point-only.sp.riv` | fixed 底座 + old 的 @point 块 | 隔离 @point 的独立影响 |

### 2.2 坡度对比结果

![图 5：坡度三方对比 — Truth vs Fixed vs Old](/testdata/ftbug/fig5_slope_comparison.png)

**图 5 解读**：
- 绿色 = Truth（独立手算），蓝色 = Fixed（修复后 rSHUD），红色 = Old（旧版 rSHUD）
- Truth 和 Fixed 的柱高在每个河段上几乎完全重合（差异 < 2.2×10⁻⁷），肉眼不可分辨
- Old 的结果**灾难性偏离**：
  - **R1、R2、R3、R6**：坡度变为 **0**（红色 × 标记在底部）
  - **R4**：坡度变为**负值** -0.00133（红色 ▼ 标记，取绝对值显示）
  - **R5**：坡度从 0.000588 变为 0.00109（偏离 85%）
- 虚线 = MINRIVSLOPE = 4×10⁻⁴，old 的 4 个零坡度段和 1 个负坡度段全部会被 SHUD solver 钳制到此值

### 2.3 坡度散点图

![图 7：坡度散点 — Truth vs Old（左）和 Truth vs Fixed（右）](/testdata/ftbug/fig7_slope_scatter.png)

**图 7 解读**：
- **右图（Truth vs Fixed）**：所有 6 个点紧贴 1:1 线，fixed 坡度 = truth 坡度，**修复正确**
- **左图（Truth vs Old）**：所有点严重偏离 1:1 线：
  - R1/R2/R6（truth > 0.008）聚集在 y = 0 线上——坡度被索引错配抹为零
  - R3（truth = 0.0068）同样被抹零
  - R4（truth = 0.0032）落入负区域（y < 0）——From/To 高程关系被翻转
  - R5 是唯一一个没有被抹零的河段，但偏差仍达 85%

### 2.4 端点坐标错配

![图 6：From 端点错配 — Truth vs Old](/testdata/ftbug/fig6_point_mismatch.png)

**图 6 解读**：
- 绿色圆点 = 真实 From 端点位置，红色 × = old 版本 @point 记录的 From 位置
- 红色箭头 = 偏移方向和距离
- Old 版本的 From 端点**全部集中在河网左上角一小块区域**（R1 起始附近），而非分布在各河段的真实起点上
- 偏移距离：590 m 到 **2135 m**（R6 最大，超过 2 km）
- 这正是 bug 报告 §2.4 描述的机制：`ft` 索引范围仅 1–7，只能访问 `xy` 表的前 7 行，而这些行全部来自第一条河段的前几个顶点

### 2.5 量化汇总

![图 8：Phase 2 总结仪表板](/testdata/ftbug/fig8_phase2_summary.png)

**图 8 解读**：
- **Panel 1（Slope Error）**：fixed 坡度误差 2.21×10⁻⁷（蓝，浮点精度级），old 坡度误差 9.92×10⁻³（红，4.5 个数量级差距）
- **Panel 2（Point Error）**：fixed 端点坐标偏差 0 m，old 最大 3491.8 m（3.5 km）
- **Panel 3（Acceptance Checks）**：5 项验收条件全部 PASS
- **Panel 4（Key Numbers）**：汇总关键数值

### 2.6 详细数值对比

#### Slope 偏差

| 河段 | Truth | Fixed | Old | Old 偏差模式 |
|------|-------|-------|-----|-------------|
| R1 | 0.00878 | 0.00878 | **0** | 零坡度（被钳制到 4×10⁻⁴） |
| R2 | 0.00887 | 0.00887 | **0** | 零坡度 |
| R3 | 0.00683 | 0.00683 | **0** | 零坡度 |
| R4 | 0.00322 | 0.00322 | **-0.00133** | 负坡度（From.z < To.z） |
| R5 | 0.000588 | 0.000588 | 0.00109 | 偏离 85% |
| R6 | 0.00992 | 0.00992 | **0** | 零坡度 |

Fixed vs Truth 最大相对偏差：**0.007%**（DEM 栅格提取精度）
Old vs Truth 最大相对偏差：**141%**（6/6 河段超过 20% 阈值）

#### @point 坐标偏差

| 字段 | Fixed vs Truth max diff | Old vs Truth max diff |
|------|------------------------|----------------------|
| From.x | 0 | 1674 m |
| From.y | 0 | 1355 m |
| From.z | 0.000107 m | 14.5 m |
| To.x | 0 | 1770 m |
| To.y | 0 | 3010 m |
| To.z | 0.000107 m | 31.1 m |

Fixed 的 x/y 偏差为 0（端点坐标完全一致），z 偏差 ~0.1 mm（DEM 栅格插值精度）。
Old 的坐标偏差达到 **km 级**，高程偏差达到 **数十米**。

#### 锁定字段一致性

| 字段 | Fixed vs Old |
|------|-------------|
| Down | **完全一致** |
| Type | **完全一致** |
| Length | **完全一致** |

确认：bug 仅影响 Slope 和 @point，不影响拓扑（Down）、Order（Type）和长度（Length）。

### 2.7 Phase 2 通过条件

| 检查项 | 结果 | 证据 |
|--------|------|------|
| fixed Slope ≈ truth | ✓ PASS | max abs diff = 2.21×10⁻⁷ ≤ 1×10⁻⁶ |
| old Slope ≠ truth (>20%) | ✓ PASS | 6/6 河段超过 20%，max rel diff = 141% |
| Down/Type/Length 一致 | ✓ PASS | old == fixed（完全相同） |
| slope-only 仅 Block 1 Col 4 不同 | ✓ PASS | |
| point-only 仅 Block 3 不同 | ✓ PASS | |

### 2.8 Phase 2 结论

**预处理层验证（Layer 1）完成**：

1. **Bug 确认**：old rSHUD 的 `FromToNode(simplify=TRUE)` 导致 6/6 河段 Slope 错误，4 段变为 0、1 段变为负值、1 段偏离 85%
2. **Fix 验证**：fixed rSHUD 的 Slope 与独立 truth baseline 差异仅 2.2×10⁻⁷（浮点精度级），修复正确
3. **影响隔离**：bug 仅影响 Slope 和 @point，Down/Type/Length 不受影响
4. **因果变体就绪**：slope-only 和 point-only 变体已生成，可用于后续 solver 层因果定位

### 2.9 产物清单

| 文件 | 说明 |
|------|------|
| `runs/ftbug/preprocess/fixed.sp.riv` | 修复后 rSHUD 生成 |
| `runs/ftbug/preprocess/old.sp.riv` | 旧版 rSHUD 生成（buggy） |
| `runs/ftbug/preprocess/slope-only.sp.riv` | fixed 底座 + old Slope |
| `runs/ftbug/preprocess/point-only.sp.riv` | fixed 底座 + old @point |
| `runs/ftbug/preprocess/compare.json` | 结构化对比报告 |
| `testdata/ftbug/fig5–fig8.png` | Phase 2 可视化图 |
| `tools/r/generate_riv_variants.R` | 生成脚本 |
| `tools/r/plot_ftbug_phase2.R` | 可视化脚本 |

---

## Phase 3–5：待执行

> 以下 Phase 的详细设计见 `docs/SHUD_river_bug_experiment_plan.md`

### Phase 3：构建最小 SHUD 输入底座

基于合成 fixture 构建可运行的 SHUD 输入集（mesh + 参数 + forcing），两个 profile：route-only（纯河道排水）和 coupled（含降雨脉冲）。

### Phase 4：Solver 只读 Diagnostics

给 SHUD solver 增加只读诊断输出（BedSlope、QrivDown、DYriv、uYriv 等），不改计算逻辑。

### Phase 5：运行实验并比较

运行 5 个 case，验证：
- `old ≈ slope-only` → Slope 是主要污染通道
- `point-only ≈ fixed` → @point 不影响 solver
- `fixed ≈ truth` → 修复正确
- Solver 输出偏差量与 Manning $\sqrt{S}$ 解析预测一致
