# SHUD 河道 From/To 索引错配 Bug 验证 — 理想实验报告

> 实验分支：`exp/river-bug-verification`
> 开始日期：2026-03-26
> 状态：Phase 0–1 完成，Phase 2+ 进行中

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

![图 1：合成河网总览](../testdata/ftbug/fig1_network_overview.png)

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

![图 4：顶点密度与 simplify 效果](../testdata/ftbug/fig4_vertex_density.png)

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

![图 2：DEM 高程面与河网叠加](../testdata/ftbug/fig2_dem_with_rivers.png)

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

![图 3：各河段坡度（log 尺度）](../testdata/ftbug/fig3_slope_profile.png)

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

## Phase 2–5：待执行

> 以下 Phase 的详细设计见 `docs/SHUD_river_bug_experiment_plan.md`

### Phase 2：生成 old / fixed `.sp.riv` 变体

用 old rSHUD (`4e6afef`) 和 fixed rSHUD (`e0d407d`) 分别处理同一套合成河网，生成 5 种 `.sp.riv` 变体（truth / fixed / old / slope-only / point-only），验证预处理层面 `fixed == truth` 且 `old != truth`。

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
