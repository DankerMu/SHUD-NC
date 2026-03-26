# SHUD 河道 From/To 索引错配理想实验方案（Markdown / LaTeX 可渲染）

## 1. 目的

本文档给出一个可在 **Codex** 中按阶段执行的理想实验方案，用于验证：

1. `rSHUD::shud.river()` 中 `From/To` 索引错配是否会通过 `Slope` 污染 SHUD 求解器；
2. 该污染是否沿着
   $$
   \mathrm{Slope} \rightarrow \mathrm{BedSlope} \rightarrow Q_{\mathrm{riv,down}} \rightarrow DY_{\mathrm{riv}} \rightarrow uY_{\mathrm{riv}} \rightarrow (Q_{\mathrm{seg,surf}}, Q_{\mathrm{seg,sub}}, Q_{\mathrm{out}})
   $$
   这条链路传播；
3. `SHUD-NC` 仓库中已集成的 `rSHUD` 修复是否正确；
4. 该修复是否适合作为与原错误实现对比的 **fixed baseline**。

---

## 2. 明确执行仓库

### 2.1 主执行仓库

**主执行仓库：`SHUD-NC` 根仓库。**

原因：

- `SHUD-NC` 是当前最合适的实验编排层；
- `SHUD/` 子模块提供固定求解器；
- `rSHUD/` 子模块提供已修复的预处理实现；
- `projects/`、`tools/`、`testdata/`、`runs/` 目录约定适合放置案例、脚本、输入和结果；
- 便于用同一 solver 对比 old/fixed 两种预处理产物。

### 2.2 各仓库职责

#### `SHUD-NC/`

- 作为总入口；
- 放置实验说明文档；
- 放置运行脚本与比较脚本；
- 放置 synthetic fixture；
- 放置运行结果与对比结果。

#### `SHUD-NC/rSHUD`

- 作为 **fixed implementation**；
- 使用仓库当前固定版本；
- 负责生成修复后的 `.sp.riv`。

#### `SHUD-NC/SHUD`

- 作为 **唯一 solver**；
- 所有 case 使用同一个二进制；
- 可选添加只读 diagnostics 输出，但不得修改计算逻辑。

#### `runs/_cmp/rSHUD-old/`

- 单独 checkout 一个 **old implementation**；
- 建议固定在修复前的基线提交；
- 仅用于生成错误版 `.sp.riv`。

---

## 3. 建议目录布局

以下目录建议在 `SHUD-NC` 根仓库下建立：

```text
SHUD-NC/
  docs/
    river-ft-bug-experiment.md
  projects/
    ftbug/
      README.md
      manifest.yaml
  testdata/
    ftbug/
      raw/
      expected/
  tools/
    ftbug.py
    compare_ftbug.py
    r/
      build_ftbug_fixture.R
      generate_riv_variants.R
      build_ftbug_shud_base.R
  runs/
    _cmp/
      rSHUD-old/
    ftbug/
      preprocess/
      route-only/
      coupled/
```

说明：

- `docs/`：实验文档；
- `projects/ftbug/`：实验案例定义与清单；
- `testdata/ftbug/`：可复用的小型 synthetic 数据；
- `tools/`：Codex 可调用的脚本；
- `runs/`：不入库的运行结果与临时中间件。

---

## 4. 总体实验思路

实验分为两条 lane：

1. **manual-topology**：核心证明实验；
2. **auto-topology**：完整流水线补充实验。

核心原则：

- **固定同一 solver**；
- **只替换预处理产物**；
- 在主实验中尽量将差异压缩到 `Slope` 一项；
- 用 `slope-only` 和 `point-only` 两种 patched `.sp.riv` 做因果定位。

---

## 5. Lane A：manual-topology（主实验）

## 5.1 目标

该 lane 用于验证：

> 在固定 `Down/Type/Length` 的前提下，旧实现对求解器的有效污染是否主要来自 `Slope`。

## 5.2 网络结构

建议使用一个 **6-reach、3-type** 的简化合流网络：

```text
R1(type1) \
            R3(type2) \
R2(type1) /            R5(type3) -> R6(type3,outlet)
R4(type1) -------------/
```

手工真值定义：

```text
R1 -> R3
R2 -> R3
R3 -> R5
R4 -> R5 或 R6（视具体布设选定一种，并在 fixture 中固定）
R5 -> R6
R6 -> -3   # outlet
```

建议在 fixture 中统一固定为一套最终真值，并写入：

- `truth_down.csv`
- `truth_type.csv`
- `truth_nodes.csv`

## 5.3 几何要求

为提高触发 bug 的概率，synthetic 河网应满足：

1. 使用 **projected/UTM 风格坐标**；
2. 坐标量级约为 $10^6$；
3. 每条河段有 $40 \sim 80$ 个顶点；
4. **只对内部顶点加噪声**；
5. 首尾端点必须精确共享；
6. 主干河段更长、更直；
7. 最小结点间距明显大于 simplify 容差。

## 5.4 DEM 要求

不要直接使用真实 DEM，建议构造可控 DEM，使真坡度可知。

至少布置三类坡度：

- 陡坡：$\sim 10^{-2}$
- 中坡：$10^{-3} \sim 10^{-2}$
- 缓坡：接近阈值，例如 $6 \times 10^{-4}$

目的：

- 验证一般坡度错误如何影响路由；
- 验证接近
  $$
  \mathrm{MINRIVSLOPE} = 4 \times 10^{-4}
  $$
  时的 clamp 效应。

## 5.5 manual-topology 五个 case

### `truth_manual`

- 不依赖旧版 `FromToNode(simplify=TRUE)`；
- 直接用原始 polyline 端点构造 `Fr/To` 真值；
- 由此计算 `Slope_true`；
- 生成真值版 `.sp.riv`。

### `fixed_manual`

- 使用 `SHUD-NC/rSHUD` 当前修复版；
- 调用 `shud.river(sl, dem, rivord=truth, rivdown=truth)`；
- 得到 fixed 版 `.sp.riv`。

### `old_manual`

- 使用单独 checkout 的 old `rSHUD`；
- 调用与 fixed 相同，但用错误实现生成 `.sp.riv`；
- `rivord/rivdown` 仍使用真值手工固定。

### `slope-only_manual`

- 从 `fixed_manual.sp.riv` 复制一份；
- **只替换第一块第 4 列 `Slope`** 为 `old_manual` 的对应列；
- 其他全部保持与 `fixed_manual` 一致。

### `point-only_manual`

- 从 `fixed_manual.sp.riv` 复制一份；
- **只替换第三块 point block** 为 `old_manual` 的 point block；
- 其他全部保持一致。

## 5.6 该 lane 的因果定位意义

如果在同一 solver 下观察到：

- `old_manual` 与 `slope-only_manual` 的结果高度一致；
- `point-only_manual` 与 `fixed_manual` 高度一致；

则说明当前 solver 的有效污染入口主要来自 `Slope`，而非 `point`。

---

## 6. Lane B：auto-topology（补充实验）

## 6.1 目标

该 lane 用于回答：

> 如果不手动冻结 `rivdown/rivord`，完整自动流水线中 old 实现是否还会额外污染 `Down` 或 `Type`。

## 6.2 case 设置

### `fixed_auto`

- 使用 fixed `rSHUD`；
- 调用 `shud.river(sl, dem, rivord=NULL, rivdown=NULL)`。

### `old_auto`

- 使用 old `rSHUD`；
- 同样调用自动推断版本。

## 6.3 作用

该 lane 主要用于：

- 记录 old/fixed 在完整预处理流水线下的额外偏差；
- 补充说明完整工作流中的风险范围；
- **不作为 `Slope-only` 因果证明的主依据**。

---

## 7. Codex 分阶段执行计划

以下阶段设计为可直接在 Codex 中按阶段执行。

---

## Phase 0：版本冻结与工作区准备

### 目标

固定 old/fixed/solver 三者版本，避免比较基线漂移。

### 执行仓库

`SHUD-NC` 根仓库。

### 操作

```bash
git submodule update --init --recursive
git -C SHUD rev-parse --short HEAD
git -C rSHUD rev-parse --short HEAD

git clone https://github.com/DankerMu/rSHUD.git runs/_cmp/rSHUD-old
git -C runs/_cmp/rSHUD-old checkout <old_commit>
```

### 产物

- `runs/_cmp/rSHUD-old/`
- `runs/ftbug/version-lock.json`

### 通过条件

- solver 版本固定；
- fixed `rSHUD` 版本固定；
- old `rSHUD` 版本固定；
- `version-lock.json` 写明三者 commit。

---

## Phase 1：生成 synthetic fixture

### 目标

生成可触发 bug 的小型理想河网与配套 DEM。

### 执行仓库

`SHUD-NC` 根仓库。

### 脚本

`tools/r/build_ftbug_fixture.R`

### 输入

- 无外部数据依赖；
- 由脚本内部生成：
  - basin polygon
  - river polylines
  - DEM
  - soil / landuse / geol 栅格
  - truth CSV

### 输出

```text
testdata/ftbug/raw/
  basin.*
  river.*
  dem.tif
  soil.tif
  lc.tif
  geol.tif
  truth_down.csv
  truth_type.csv
  truth_nodes.csv
  manifest.yaml
```

### 通过条件

- reach 数为 6；
- type 数为 3；
- truth topology 完整；
- 至少一条 reach 处于 clamp-sensitive 坡度区间。

---

## Phase 2：搜索可复现 seed，并生成 `.sp.riv` 变体

### 目标

从一组随机种子中选出最能稳定触发问题的 fixture，然后生成 old/fixed/truth 各类 `.sp.riv`。

### 执行仓库

`SHUD-NC` 根仓库。

### 脚本

`tools/r/generate_riv_variants.R`

### 建议流程

对随机种子 $s \in \{1,2,\dots,100\}$ 循环：

1. 生成 fixture；
2. 生成 `truth_manual`；
3. 生成 `fixed_manual`；
4. 生成 `old_manual`；
5. 生成 `fixed_auto`；
6. 生成 `old_auto`；
7. 计算各自差异；
8. 选择最合适 seed。

### seed 选择门槛

设某条 reach 的真坡度为 $S^{(i)}_{\text{truth}}$，旧实现坡度为 $S^{(i)}_{\text{old}}$，则至少满足：

$$
\exists i, \quad \frac{\left|S^{(i)}_{\text{old}} - S^{(i)}_{\text{truth}}\right|}{\left|S^{(i)}_{\text{truth}}\right|} > 0.2
$$

且最好满足：

$$
S^{(i)}_{\text{truth}} > 2 \times \mathrm{MINRIVSLOPE}
$$

这样可避免“只是被 clamp 掩盖”的情形。

### 输出

```text
runs/ftbug/preprocess/manual/
  truth.sp.riv
  fixed.sp.riv
  old.sp.riv
  slope-only.sp.riv
  point-only.sp.riv
  compare.json

runs/ftbug/preprocess/auto/
  fixed.sp.riv
  old.sp.riv
  compare.json
```

### 通过条件

#### manual lane

- `fixed_manual == truth_manual`；
- `old_manual != truth_manual` 至少 1 条 reach；
- `old_manual` 与 `fixed_manual` 的 `Down/Type/Length` 完全相同；
- `slope-only_manual` 仅第一块第 4 列不同；
- `point-only_manual` 仅第三块不同。

#### auto lane

- `fixed_auto` 与 truth 的 `Down/Type` 一致；
- `old_auto` 是否影响 `Down/Type` 做记录。

---

## Phase 3：构建最小 SHUD base case

### 目标

构建一个极小但完整的 SHUD 输入底座，后续所有 case 仅替换 `.sp.riv`。

### 执行仓库

`SHUD-NC` 根仓库；必要时调用 `SHUD/` 子模块格式约定。

### 脚本

`tools/r/build_ftbug_shud_base.R`

### 要求

- 10–20 个三角形单元；
- 每条 reach 至少有一个相邻单元；
- 统一的 soil / lc / geol；
- 单一 outlet；
- 固定输出间隔。

### 生成两个 profile

#### `route-only`

- forcing 全 0；
- 初始河道水位设为可衰减的梯度波；
- 河-坡交换尽量关闭或极小化。

#### `coupled`

- 初始水位平缓；
- 给一个短时降雨脉冲；
- 河-坡交换参数恢复为正常非零。

### 输出

```text
runs/ftbug/base/route-only/input/
runs/ftbug/base/coupled/input/
```

### 通过条件

- fixed case 能成功跑通一个短时间窗；
- base case 完整；
- profile 可复用。

---

## Phase 4：给 solver 增加只读 diagnostics（推荐）

### 目标

直接导出验证链条中的内部变量，避免只靠出口流量判断。

### 执行仓库

`SHUD-NC/SHUD` 子模块。

### 原则

- **只加输出，不改计算**；
- 所有 case 使用同一个 instrumented binary。

### 建议输出文件

```text
diag_riv.tsv:
time, iRiv, BedSlope, QrivUp, QrivDown, QrivSurf, QrivSub, DYriv, uYriv
```

### reach 选择建议

至少输出以下 4 条代表性河段：

- 1 条 type 1 headwater；
- 1 条 type 2 confluence reach；
- 1 条 type 3 trunk；
- 1 条 outlet trunk。

### 通过条件

- 输出文件存在；
- 不影响 solver 结果；
- 所有 case 输出字段一致。

---

## Phase 5：运行 manual-topology 的 route-only 主实验

### 目标

验证 `Slope -> BedSlope -> QrivDown -> DYriv -> uYriv -> Qout` 的主链条。

### 执行仓库

从 `SHUD-NC` 根仓库发起运行，solver 在 `SHUD/` 子模块。

### 脚本

```bash
python tools/ftbug.py run --lane manual --profile route-only
```

### 运行 case

- `truth_manual`
- `fixed_manual`
- `old_manual`
- `slope-only_manual`
- `point-only_manual`

### 输出

```text
runs/ftbug/route-only/manual/<case>/
  input/
  output/
  diag_riv.tsv
```

### 通过条件

- 五个 case 全部成功结束；
- diagnostics 可读；
- 对比脚本能生成差异报告。

---

## Phase 6：运行 manual-topology 的 coupled 实验

### 目标

验证路由差异是否进一步反馈到河-坡交换。

### 执行仓库

同 Phase 5。

### 脚本

```bash
python tools/ftbug.py run --lane manual --profile coupled
```

### 运行 case

- `truth_manual`
- `fixed_manual`
- `old_manual`
- `slope-only_manual`
- `point-only_manual`

### 输出

```text
runs/ftbug/coupled/manual/<case>/
  input/
  output/
  diag_riv.tsv
```

### 通过条件

- 五个 case 全部成功结束；
- `QrivSurf` 与 `QrivSub` 非零；
- 可生成对比图表和统计摘要。

---

## Phase 7：运行 auto-topology 补充实验

### 目标

记录完整自动流水线下 old/fixed 是否在 `Down/Type` 上产生额外差异。

### 执行仓库

同前。

### 脚本

```bash
python tools/ftbug.py run --lane auto --profile route-only
```

### 运行 case

- `fixed_auto`
- `old_auto`

### 作用

- 补充风险说明；
- 不是主因果证明；
- 不要求像 manual lane 那样完成全部严格因果拆分。

---

## 8. 量化验收标准

为避免把数值噪声误判为有效差异，定义每个 metric 的噪声地板。

### 8.1 route-only 噪声地板

对任意指标 $M$，定义：

$$
\mathrm{noise}(M) = \max \left(
\mathrm{diff}(\text{fixed\_manual}, \text{truth\_manual}; M),
\mathrm{diff}(\text{point-only\_manual}, \text{fixed\_manual}; M)
\right)
$$

其中 `diff(A, B; M)` 表示在指标 $M$ 上对两个 case 的差异度量。

### 8.2 route-only 验收条件

#### 条件 A：`old_manual` 与 `slope-only_manual` 高度一致

对以下指标均要求：

- `BedSlope_clamped`
- `QrivDown`
- `DYriv`
- `uYriv`
- `Qout`

满足：

$$
\mathrm{diff}(\text{old\_manual}, \text{slope-only\_manual}; M) \le 10 \times \mathrm{noise}(M)
$$

#### 条件 B：`fixed_manual` 与 `truth_manual` 高度一致

对上述同一组指标要求：

$$
\mathrm{diff}(\text{fixed\_manual}, \text{truth\_manual}; M) \le 10 \times \mathrm{noise}(M)
$$

#### 条件 C：`point-only_manual` 与 `fixed_manual` 高度一致

对上述同一组指标要求：

$$
\mathrm{diff}(\text{point-only\_manual}, \text{fixed\_manual}; M) \le 10 \times \mathrm{noise}(M)
$$

#### 条件 D：old/fixed 差异足够显著

至少在：

- 一个内部河道指标（推荐 `QrivDown` 或 `DYriv`）；
- 一个出口指标（推荐 `Qout` 或 outlet stage）；

上满足：

$$
\mathrm{diff}(\text{old\_manual}, \text{fixed\_manual}; M) \ge 100 \times \mathrm{noise}(M)
$$

如果 A、B、C、D 同时成立，则可判定：

1. `point` 不是当前 solver 的主要有效污染入口；
2. `Slope` 足以单独复现 old 实现对 solver 的主要污染；
3. `fixed` 修复版可作为可信 baseline。

---

## 8.3 coupled 噪声地板

对任意 coupled 指标 $M$，定义：

$$
\mathrm{noise}_c(M) = \max \left(
\mathrm{diff}(\text{fixed\_manual}, \text{truth\_manual}; M),
\mathrm{diff}(\text{point-only\_manual}, \text{fixed\_manual}; M)
\right)
$$

### 8.4 coupled 验收条件

重点检查以下指标：

- `uYriv`
- `QrivSurf`
- `QrivSub`
- `Qout`

#### 条件 E：`old_manual` 与 `slope-only_manual` 高度一致

$$
\mathrm{diff}(\text{old\_manual}, \text{slope-only\_manual}; M) \le 10 \times \mathrm{noise}_c(M)
$$

#### 条件 F：`fixed_manual` 与 `truth_manual` 高度一致

$$
\mathrm{diff}(\text{fixed\_manual}, \text{truth\_manual}; M) \le 10 \times \mathrm{noise}_c(M)
$$

#### 条件 G：old/fixed 在交换与出口上存在显著差异

至少在：

- 一个交换指标（`QrivSurf` 或 `QrivSub`）；
- 一个出口指标（`Qout` 或 outlet stage）；

上满足：

$$
\mathrm{diff}(\text{old\_manual}, \text{fixed\_manual}; M) \ge 100 \times \mathrm{noise}_c(M)
$$

如果 E、F、G 成立，则说明：

- old 实现通过 `Slope` 引起的路由差异会继续反馈到河-坡交换；
- 问题并非只停留在河道内部，而会传到耦合量上。

---

## 9. SHUD-NC 修复是否可作为 fixed baseline

结论：**可以，而且推荐直接作为 fixed baseline。**

原因：

1. 修复发生在 `rSHUD` 预处理侧，而不是 solver 内部补丁；
2. 修复思路针对根因：
   - 显式传递 `coord=xy`；
   - 避免 lazy evaluation 导致 `coord` 在错误时机求值；
   - 对 `gSimplify()` 后的端点漂移进行 snap；
3. `SHUD-NC` 当前结构适合用同一 solver 比较 old/fixed；
4. 与 `slope-only` / `point-only` 组合后，可形成严格的因果定位。

因此在本实验中建议：

- **fixed**：使用 `SHUD-NC/rSHUD` 当前固定版本；
- **old**：使用单独 checkout 的修复前 `rSHUD`；
- **solver**：固定 `SHUD-NC/SHUD` 当前版本。

---

## 10. 推荐执行顺序

建议 Codex 按以下顺序推进：

1. Phase 0：版本冻结；
2. Phase 1：生成 synthetic fixture；
3. Phase 2：生成 `.sp.riv` 变体并筛选 seed；
4. Phase 3：构建最小 SHUD base case；
5. Phase 4：增加只读 diagnostics；
6. Phase 5：先做 `manual-topology + route-only`；
7. Phase 6：再做 `manual-topology + coupled`；
8. Phase 7：最后补 `auto-topology`。

其中最关键的里程碑是：

> 先证明 `old_manual \approx slope-only_manual` 且 `point-only_manual \approx fixed_manual`。

只要这一点被严格证实，就基本完成了“当前 solver 中真正生效的污染通道主要是 `Slope`”这一主命题。

---

## 11. 最终判定标准（简版）

如果满足以下三条，则实验结论成立：

1. 预处理层面：
   - `fixed_manual = truth_manual`
   - `old_manual` 至少在 `Fr/To` 与 `Slope` 上出错

2. route-only 层面：
   - `old_manual \approx slope-only_manual`
   - `point-only_manual \approx fixed_manual`
   - `old_manual` 与 `fixed_manual` 差异显著

3. coupled 层面：
   - `old_manual \approx slope-only_manual`
   - `fixed_manual \approx truth_manual`
   - old/fixed 差异可传播到交换与出口指标

即可以得出：

$$
\text{old bug 的 solver 级主污染通道} \approx \text{Slope-only}
$$

并且：

$$
\text{SHUD-NC 中的修复方案可作为正确的 fixed baseline}
$$

---

## 12. 附：建议 Codex 直接实现的脚本清单

### Python

- `tools/ftbug.py`
  - 子命令：`prepare` / `run` / `compare` / `report`

- `tools/compare_ftbug.py`
  - 对比 `.sp.riv`
  - 读取 `diag_riv.tsv`
  - 输出统计摘要与图表

### R

- `tools/r/build_ftbug_fixture.R`
  - 生成 synthetic 河网与 DEM

- `tools/r/generate_riv_variants.R`
  - 调用 old/fixed `rSHUD`
  - 生成 `truth/fixed/old/slope-only/point-only`

- `tools/r/build_ftbug_shud_base.R`
  - 构建最小可运行 SHUD 输入底座

---

## 13. 一句话摘要

**本方案建议在 `SHUD-NC` 根仓库执行，固定同一 `SHUD` solver，只替换 `rSHUD` 生成的 `.sp.riv`，并用 `manual-topology + slope-only/point-only` 设计把 solver 中的有效污染通道严格定位到 `Slope`。**
