# Phase A（NetCDF Forcing）完整工作总结

> 最后验证：2026-02-14（QHH 10-day run）  
> 覆盖仓库：`DankerMu/SHUD-NC`（父仓库）、`DankerMu/SHUD-up`（SHUD 子模块）、`DankerMu/AutoSHUD`（AutoSHUD 子模块）、`DankerMu/rSHUD`（rSHUD 子模块）  
> 核心结论：在 QHH 10-day 验证窗口内，NetCDF forcing（CMFD2）与 baseline CSV forcing **5 个变量逐点一致**（`max_abs=0`），legacy `*.dat` 输出 **二进制一致**（`md5sum` 全部相同），baseline 默认路径未被破坏。

## 1. 背景与目标

### 1.1 Phase A 在 A/B 迁移中的定位

- 总体目标分两阶段推进：
  - **Phase A（Forcing）**：SHUD 运行时直接读取原始 forcing NetCDF（先 CMFD2/ERA5），不再依赖海量站点 CSV。见 `openspec/project.md:6`、`docs/SHUD-NC_NetCDF_改造总体方案.md:10`。
  - **Phase B（Output）**：SHUD 输出标准 NetCDF（CF/UGRID）。见 `openspec/project.md:7`、`docs/SHUD-NC_NetCDF_改造总体方案.md:11`。
  - **Baseline preservation**：默认仍保持 AutoSHUD→SHUD（CSV forcing + legacy output）可跑、可回归。见 `openspec/project.md:8`、`docs/SHUD-NC_NetCDF_改造总体方案.md:12`、`CLAUDE.md:11`。

### 1.2 为什么要做 NetCDF forcing

- Phase A 的直接动机是把 forcing I/O 从 “每站 CSV” 迁移为 “运行时读 NetCDF”，以消除生成/读取海量 `dout.forc/*.csv` 的成本与脆弱性。见 `openspec/changes/archive/2026-02-08-add-shud-netcdf-forcing-cmfd2/proposal.md:4`、`openspec/project.md:6`。
- 约束与原则：
  - **不破坏 baseline**（默认行为仍为 CSV）。见 `openspec/project.md:60`、`SHUD/src/classes/Model_Control.hpp:159`、`SHUD/src/classes/Model_Control.cpp:193`。
  - **SHUD 不解析 YAML**：YAML 只存在于父仓库编排层，运行时对 SHUD 只交付 `.cfg` KEY VALUE。见 `openspec/project.md:61`、`openspec/specs/meta-runner/spec.md:38`。
  - **fail-fast**：覆盖期不足/缺测/维度不匹配要清晰报错（file/var/time/station）。见 `openspec/project.md:62`、`SHUD/src/classes/NetcdfForcingProvider.cpp:459`、`SHUD/src/classes/NetcdfForcingProvider.cpp:482`。

## 2. 架构设计

### 2.1 ForcingProvider 抽象层

- SHUD 侧引入 `ForcingProvider` 抽象，统一 forcing 访问点，保证 “provider swap 不改变语义”。接口与 forcing contract（5 variables + step function）在 `SHUD/src/classes/ForcingProvider.hpp:15`–`SHUD/src/classes/ForcingProvider.hpp:33` 明确：
  - 5 variables：Precip(mm/day), Temp(°C), RH(0–1), Wind(m/s), RN(W/m²)。另见 `openspec/specs/shud-forcing/spec.md:22`。
  - step function：先 `movePointer(t_min)`，后 `get(station, var)` 返回当前 forcing 区间常值。见 `SHUD/src/classes/ForcingProvider.hpp:20`–`SHUD/src/classes/ForcingProvider.hpp:28`、`openspec/specs/shud-forcing/spec.md:35`。
- 两个实现：
  - `CsvForcingProvider`：复用现有 `_TimeSeriesData`（baseline 语义不变）。见 `SHUD/src/classes/ForcingProvider.hpp:36`–`SHUD/src/classes/ForcingProvider.hpp:63`。
  - `NetcdfForcingProvider`：Phase A 新增，封装 CMFD2/ERA5 NetCDF 读取与换算，且仅在 `_NETCDF_ON` 时编译。见 `SHUD/src/classes/NetcdfForcingProvider.hpp:14`–`SHUD/src/classes/NetcdfForcingProvider.hpp:52`。

### 2.2 配置层叠：YAML → cfg → C++

整体链路（单入口、单一真相）：

1. 用户入口：`projects/<case>/shud.yaml`（父仓库）  
   - QHH 示例的 baseline/nc profiles：`projects/qhh/shud.yaml:58`–`projects/qhh/shud.yaml:95`。
2. 编排层渲染：`tools/shudnc.py render-shud-cfg` 把 adapter YAML 渲染为 SHUD 运行时读取的 KEY VALUE `.cfg`  
   - 生成 `*.cfg.forcing`：`tools/shudnc.py:455`–`tools/shudnc.py:506`。  
   - Patch `*.cfg.para`（幂等、去重）：`tools/shudnc.py:563`–`tools/shudnc.py:593`、`tools/shudnc.py:596`–`tools/shudnc.py:635`。  
3. SHUD 解析 `.cfg.para`，根据 `FORCING_MODE`/`FORCING_CFG` 初始化 provider  
   - 默认 `FORCING_MODE=CSV`：`SHUD/src/classes/Model_Control.hpp:159`、`SHUD/src/classes/Model_Control.cpp:193`–`SHUD/src/classes/Model_Control.cpp:218`。  
   - `FORCING_MODE=NETCDF` 必须给 `FORCING_CFG`，并把相对路径解析为 input 目录相对路径且校验可读：`SHUD/src/classes/Model_Control.cpp:505`–`SHUD/src/classes/Model_Control.cpp:547`。  
4. SHUD 仍要求 `<prj>.tsd.forc` 作为 station list + `ForcStartTime`（即使 forcing 来自 NetCDF）  
   - NetCDF 模式读取 `<prj>.tsd.forc` 的 header 与 station records：`SHUD/src/ModelData/MD_readin.cpp:392`–`SHUD/src/ModelData/MD_readin.cpp:466`。  
5. NetCDF provider 读取 `<prj>.cfg.forcing`（KEY VALUE）并解析 DATA_ROOT/layout/vars  
   - KEY VALUE 解析：`SHUD/src/classes/NetcdfForcingProvider.cpp:511`–`SHUD/src/classes/NetcdfForcingProvider.cpp:543`。  
   - `DATA_ROOT` 以 run_dir 为基准解析为绝对路径：`SHUD/src/classes/NetcdfForcingProvider.cpp:697`–`SHUD/src/classes/NetcdfForcingProvider.cpp:706`。

## 3. 实现细节

### 3.1 关键文件清单（按职责）

- SHUD（`DankerMu/SHUD-up` 子模块）
  - `SHUD/src/classes/ForcingProvider.hpp:15`：ForcingProvider 接口 + `CsvForcingProvider`（复用 `_TimeSeriesData`）。
  - `SHUD/src/classes/NetcdfForcingProvider.hpp:22`：`NetcdfForcingProvider` 对外接口（含 `minTimeMin/maxTimeMin`）。
  - `SHUD/src/classes/NetcdfForcingProvider.cpp:336`：NetCDF 点读取器（按维度名解析 time/lat/lon、处理 `scale_factor/add_offset/_FillValue/missing_value`、fail-fast）。
  - `SHUD/src/classes/TimeSeriesData.cpp:161`：CSV forcing coverage 的 `getMaxTimeCovered()`（step function 覆盖期语义）。
  - `SHUD/src/ModelData/MD_readin.cpp:364`：根据 `FORCING_MODE` 选择 CSV/NetCDF 读入，并在 NetCDF 模式下初始化 provider。
  - `SHUD/src/ModelData/MD_readin.cpp:794`：`validateTimeStamps()`（覆盖期校验：CSV 用 `getMaxTimeCovered()`，NetCDF 用 `maxTimeMin()`）。
  - `SHUD/src/classes/Model_Control.cpp:193`：解析 `FORCING_MODE/FORCING_CFG`（默认 CSV，NETCDF 需 cfg）。
  - `SHUD/Makefile:91`：`NETCDF=1` 构建开关（`-D_NETCDF_ON` + link netcdf-c）。
- 父仓库工具链（`DankerMu/SHUD-NC`）
  - `tools/shudnc.py:455`：渲染 `*.cfg.forcing`（从 adapter YAML flatten 为 KEY VALUE）。
  - `tools/shudnc.py:479`：新增 `forcing.kv`（追加任意 KEY VALUE override，例如 `CMFD_PRECIP_UNITS`）。
  - `tools/compare_forcing.py:245`：forcing 回归对比（baseline CSV vs NetCDF），内置同款单位/量化逻辑用于验收。
  - `projects/qhh/shud.yaml:58`：QHH baseline/nc profiles（Phase A 验证期将 nc profile 设为 legacy output）。
  - `configs/forcing/cmfd2.yaml:11`：CMFD2 adapter 模板（layout/vars/conversion）。
- AutoSHUD / rSHUD（baseline forcing 作为对照）
  - `AutoSHUD/Rfunction/LDAS_UnitConvert.R:72`：baseline CMFD forcing 的单位换算（`Prec * 24`）与降水阈值（`1e-4`）。
  - `rSHUD/R/writeInput.R:35`：`write.tsd()` 写出 forcing CSV 的文件头与 time tag 语义。

### 3.2 CMFD2 NetCDF forcing 处理流程（SHUD 侧）

#### 3.2.1 文件发现（按月 yyyymm）与 off-by-one 修复

- CMFD2 使用按月文件集合（`{yyyymm}`），所需月份由模拟区间 `[sim_start_min, sim_end_min)` 推导。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:768`。
- 关键修复点：当 `sim_end_min` 刚好落在 “整天/整月边界” 时，forcing discovery 不能把 END 边界对应月份误加入（END 为 exclusive bound）。实现通过 `end_min_excl = nextafter(sim_end_min, -inf)` 避免 off-by-one。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:781`–`SHUD/src/classes/NetcdfForcingProvider.cpp:788`。

#### 3.2.2 维度解析与点读取（按维度名，不假设顺序）

- `openPointReader()` 从变量的 dim name 里定位 `time/lat/lon` 的位置，避免数据集维度顺序差异。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:389`–`SHUD/src/classes/NetcdfForcingProvider.cpp:417`。
- `readPoint()` 单点读取并 fail-fast：
  - 读失败（带 file/var/index/station）：`SHUD/src/classes/NetcdfForcingProvider.cpp:461`–`SHUD/src/classes/NetcdfForcingProvider.cpp:469`。
  - `_FillValue/missing_value` 直接报错：`SHUD/src/classes/NetcdfForcingProvider.cpp:482`–`SHUD/src/classes/NetcdfForcingProvider.cpp:499`。
  - 支持 `scale_factor/add_offset`：`SHUD/src/classes/NetcdfForcingProvider.cpp:501`–`SHUD/src/classes/NetcdfForcingProvider.cpp:507`。

#### 3.2.3 Station → grid 最近邻（NEAREST）与 lon 0..360 兼容

- 读取 `lat/lon` 坐标数组，并自动判断经度是否为 0..360（`grid_lon_is_0360`）。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1061`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1068`。
- 若数据是 0..360，经度会对 station lon 做归一化（`slon += 360; slon -= 360`）。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1078`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1085`。
- 最近邻索引 argmin(|Δ|) 预计算并在启动时打印前 3 个站点映射。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1087`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1125`。

#### 3.2.4 时间轴解析（minutes since ForcStartTime）与覆盖期

- `time.units` 解析为 `UnitsSince` 后，将 NetCDF 的 time 值转为 “相对 `ForcStartTime` 的分钟数（t_min）”，并校验单调不减。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1014`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1040`。
- provider 启动时会打印 NetCDF forcing 的 time coverage（min/max）。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1153`。

#### 3.2.5 单位转换 + 量化匹配（对齐 baseline CSV）

- CMFD2 precipitation 单位支持 auto-detect，也支持 `CMFD_PRECIP_UNITS` 显式 override：
  - override 解析 + auto-detect 失败时 fail-fast 并提示修复：`SHUD/src/classes/NetcdfForcingProvider.cpp:1180`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1216`。
  - `MM_HR` 走 `*24`，用于与 baseline CSV 对齐：`SHUD/src/classes/NetcdfForcingProvider.cpp:1251`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1254`。
- 为实现 “全量 diff=0” 的回归验收，provider 在换算后对 5 变量做与 baseline CSV 一致的量化与阈值/夹逼（先 quantize 再 threshold）：
  - Precip：4 dp + `<0.0001` 置 0：`SHUD/src/classes/NetcdfForcingProvider.cpp:1266`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1271`。
  - Temp：2 dp：`SHUD/src/classes/NetcdfForcingProvider.cpp:1277`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1279`。
  - RH：4 dp + clamp [0,1]：`SHUD/src/classes/NetcdfForcingProvider.cpp:1292`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1299`。
  - Wind：2 dp + `min=0.05`：`SHUD/src/classes/NetcdfForcingProvider.cpp:1305`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1310`。
  - RN：整数：`SHUD/src/classes/NetcdfForcingProvider.cpp:1319`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1321`。
- baseline 侧的对照来源（AutoSHUD）：
  - `unitConvert.CMFD()` 明确把 `Prec` 当作 mm/hr 并做 `*24`，且以 `1e-4` 作为 “无雨” 阈值。见 `AutoSHUD/Rfunction/LDAS_UnitConvert.R:84`–`AutoSHUD/Rfunction/LDAS_UnitConvert.R:90`。

#### 3.2.6 step function 语义与 maxTimeMin

- `movePointer(t_min)` 以单调前进方式推进索引，并在 time step 切换时刷新 cache。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1727`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1738`。
- `maxTimeMin()` 的语义：step function 下最后一个记录覆盖到 “最后时间戳 + 最后正 dt”，用于覆盖期校验。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1762`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1779`。
- CSV forcing 的对应语义由 `_TimeSeriesData::getMaxTimeCovered()` 提供。见 `SHUD/src/classes/TimeSeriesData.cpp:161`–`SHUD/src/classes/TimeSeriesData.cpp:171`。

### 3.3 ERA5 NetCDF forcing（实现已落地，待扩展验证）

- ERA5 子集按日文件（`{yyyymmdd}`），并处理 accumulated 变量（tp/ssr）：
  - 区间增量：`inc = A[k+1]-A[k]`，若 reset（负增量）则用 `A[k+1]`。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1630`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1637`。
  - tp(m) → Precip(mm/day)，ssr(J m-2) → RN(W/m²)：`SHUD/src/classes/NetcdfForcingProvider.cpp:1643`–`SHUD/src/classes/NetcdfForcingProvider.cpp:1645`。
- 相关 adapter 模板：`configs/forcing/era5.yaml:11`–`configs/forcing/era5.yaml:59`。

## 4. 工具链

### 4.1 `tools/shudnc.py`：render-shud-cfg 与 profile 编排

- `render-shud-cfg` 的核心能力：YAML（`projects/<case>/shud.yaml`）→ 运行期 `.cfg` overlay（KEY VALUE），避免 SHUD 解析 YAML。见 `openspec/specs/meta-runner/spec.md:30`、`tools/shudnc.py:596`。
- `forcing.kv`：允许在 adapter flatten 后追加任意 KEY VALUE override（用于 `CMFD_PRECIP_UNITS` 等产品开关）。见 `tools/shudnc.py:479`–`tools/shudnc.py:496`。
- `.cfg.para` patch：替换/去重/追加键，保证幂等。见 `tools/shudnc.py:563`–`tools/shudnc.py:593`。

### 4.2 `tools/compare_forcing.py`：forcing 回归对比（CSV vs NetCDF）

- 与 `NetcdfForcingProvider` 对齐的两类关键逻辑：
  - `CMFD_PRECIP_UNITS` override：`tools/compare_forcing.py:245`–`tools/compare_forcing.py:256`。
  - CSV 量化匹配（先 quantize 再 threshold；以及 wind min clamp、RN integer）：`tools/compare_forcing.py:437`–`tools/compare_forcing.py:465`。
- CLI 支持 `--fail-max-abs` 用于验收门禁（本次验证使用 `0`）。见 `tools/compare_forcing.py:509`。

### 4.3 SHUD 构建：`NETCDF=1`

- 默认不依赖 NetCDF；当 `NETCDF=1` 时：
  - 探测 `nc-config` / `pkg-config netcdf`，并启用 `-D_NETCDF_ON` + 链接 `libnetcdf`。见 `SHUD/Makefile:91`–`SHUD/Makefile:112`。
  - 若未找到 netcdf-c 则直接 `$(error ...)` fail-fast。见 `SHUD/Makefile:105`–`SHUD/Makefile:107`。

## 5. 验证结果（QHH 10-day run）

### 5.1 验证窗口与配置要点

- 10-day 模拟区间由 `START=1, END=10`（day）定义（SHUD 内部以分钟推进）。示例见 nc profile 运行期 `qhh.cfg.para`：`runs/qhh/nc/input/qhh/qhh.cfg.para:15`–`runs/qhh/nc/input/qhh/qhh.cfg.para:16`。
- Phase A 验证采用 **NetCDF forcing + legacy output**（先锁定 forcing 一致性；Phase B 再切 NetCDF output）。见 `projects/qhh/shud.yaml:74`–`projects/qhh/shud.yaml:95`（其中 `output_mode: legacy` 在 `projects/qhh/shud.yaml:92`）。
- 为与 baseline CSV 对齐，本次在 nc profile 强制 `CMFD_PRECIP_UNITS=MM_HR`：`projects/qhh/shud.yaml:84`–`projects/qhh/shud.yaml:87`，渲染结果落在 `runs/qhh/nc/input/qhh/qhh.cfg.forcing:24`。

### 5.2 SHUD 运行侧证据：FORCING_MODE / station→grid / time coverage

- SHUD 启动日志确认 `FORCING_MODE=NETCDF`，并自动推导 `RADIATION_INPUT_MODE`：`runs/qhh/nc/qhh_10d_nc_prec_units_fix.log:32`–`runs/qhh/nc/qhh_10d_nc_prec_units_fix.log:34`。
- station→grid 最近邻映射与 NetCDF forcing 覆盖期打印：`runs/qhh/nc/qhh_10d_nc_prec_units_fix.log:155`–`runs/qhh/nc/qhh_10d_nc_prec_units_fix.log:159`。

### 5.3 forcing 对比：5 变量 `max_abs=0`

- 对比产物：`runs/qhh/compare/forcing_10d_simwindow_v2.json`  
  - 抽样 stations：`[0, 50, 100, 200, 385]`，抽样时刻：`t_min=1440..14400`（3-hour 步长）见 `runs/qhh/compare/forcing_10d_simwindow_v2.json:6`、`runs/qhh/compare/forcing_10d_simwindow_v2.json:13`。  
  - 5 变量统计：全部 `max_abs=0.0`。见 `runs/qhh/compare/forcing_10d_simwindow_v2.json:88`–`runs/qhh/compare/forcing_10d_simwindow_v2.json:113`。
- 使用的命令（验收门禁 `--fail-max-abs 0`）：
  ```bash
  # t_min 覆盖 10-day 窗口：1440..14400（3-hour / 180min 步长）
  tmins=$(python3 - <<'PY'
  print(','.join(str(t) for t in range(1440, 14401, 180)))
  PY
  )
  python3 tools/compare_forcing.py \
    --baseline-run runs/qhh/baseline \
    --nc-run runs/qhh/nc \
    --prj qhh \
    --stations 0,50,100,200,385 \
    --t-min "$tmins" \
    --out-json runs/qhh/compare/forcing_10d_simwindow_v2.json \
    --fail-max-abs 0
  ```

### 5.4 legacy 输出：`*.dat` 二进制一致（md5sum）

- 对比目录：
  - baseline：`runs/qhh/baseline/output/qhh.out/`
  - nc：`runs/qhh/nc/output/qhh.out/`
- 结论：两边共 21 个 `*.dat` 文件 `md5sum` 全部相同（`diff -u` 无输出）。
- `md5sum`（baseline 与 nc 相同；取 baseline 列表作为证据）：
  ```text
  d41d8cd98f00b204e9800998ecf8427e  ./DY.dat
  6c97b77d19338e31dc082384c00bf186  ./qhh.eleveta.dat
  5f1ed82b936574556deaae2683de11f9  ./qhh.elevetev.dat
  4b8b27d79d5d7c863f735cb0d8bf24e7  ./qhh.elevetic.dat
  548f7f426a3a2dca09a7b45341fa648c  ./qhh.elevetp.dat
  379caa1a944553518cc29d92adc0f91a  ./qhh.elevettr.dat
  17f4f8069d675c66c1be98ec824c568f  ./qhh.elevnetprcp.dat
  34fa56a97b7b108253606d63432dd3b0  ./qhh.elevprcp.dat
  2d37f0d0152b2bc6149388149596f977  ./qhh.eleygw.dat
  c4f165880159aa705da0e560ced8d60c  ./qhh.lakatop.dat
  6b1ec3f616f68e89998d544775561357  ./qhh.lakqrivin.dat
  c0bbbef4f90a57ddf4446c4887fbb39d  ./qhh.lakqrivout.dat
  313bb5ebd5bdabef868029c7bb4a24d2  ./qhh.lakqsub.dat
  c0bbbef4f90a57ddf4446c4887fbb39d  ./qhh.lakqsurf.dat
  220b296eef30f261f131b5e4c0f3c395  ./qhh.lakvevap.dat
  fec860642aca3b1b76d8fe00de624f48  ./qhh.lakvprcp.dat
  22767e50fa48d3a9eb771253e885d08e  ./qhh.lakystage.dat
  87cc4571dcbd323f255b10ecd4c4da66  ./qhh.rivqdown.dat
  7a20329d74729e84a0d9be5195f7415e  ./qhh.rn_factor.dat
  d178b1f1a93481bd58f96ffffc900199  ./qhh.rn_h.dat
  26fcf399b07114e859c2b60d8ee183f3  ./qhh.rn_t.dat
  ```
- 用到的命令：
  ```bash
  (cd runs/qhh/baseline/output/qhh.out && find . -maxdepth 1 -name '*.dat' -print0 | sort -z | xargs -0 md5sum) > /tmp/baseline.md5
  (cd runs/qhh/nc/output/qhh.out && find . -maxdepth 1 -name '*.dat' -print0 | sort -z | xargs -0 md5sum) > /tmp/nc.md5
  diff -u /tmp/baseline.md5 /tmp/nc.md5
  ```

### 5.5 baseline 未破坏（同 profile 复跑稳定）

- baseline legacy `*.dat` 与一次运行前自动备份目录一致：
  - `runs/qhh/baseline/output/qhh.out` vs `runs/qhh/baseline/output/qhh.out.bak_pre_baseline_rerun_20260214_005500`
  - 对比方式同上（`md5sum` + `diff -u`），结果为无差异。

## 6. 修复的关键问题（与落地代码对照）

1. off-by-one：CMFD2 按月文件发现误包含 END 边界月份  
   - 修复：END 作为 exclusive bound，使用 `nextafter(sim_end_min, -inf)` 计算 `end_days`。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:781`。
2. CSV 量化匹配（实现 forcing diff=0 的关键）  
   - 修复：NetCDF provider 按 baseline CSV 的量化/阈值语义处理 5 变量（precip/RH 4dp；temp/wind 2dp；RN int；先 quantize 再 threshold；wind min clamp）。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1266`、`tools/compare_forcing.py:437`。
3. `CMFD_PRECIP_UNITS` 单位覆盖（兼容 baseline 与物理正确两种路径）  
   - 修复：支持 `AUTO|KG_M2_S|MM_HR|MM_DAY`，auto-detect 失败 fail-fast；并允许在 cfg.forcing 显式指定。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1180`、`tools/shudnc.py:479`、`projects/qhh/shud.yaml:84`。
4. `maxTimeMin` 的 step function 语义  
   - 修复：forcing 覆盖期校验使用 “最后时间戳 + 最后正 dt” 而不是简单 `time.back()`。见 `SHUD/src/classes/NetcdfForcingProvider.cpp:1768`。
5. `getMaxTimeCovered`（CSV forcing 覆盖期语义）  
   - 修复/明确：CSV forcing 覆盖期同样按 step function 扩展到 `maxTime + lastDtMin`。见 `SHUD/src/classes/TimeSeriesData.cpp:161`。

## 7. 相关 Issues 和 PRs（4 仓库）

> 数据来源：对四个仓库分别执行 `gh issue list --repo <repo> --state all --limit 50` 与 `gh pr list --repo <repo> --state all --limit 50`（并使用 `--json` 提取 url）。

### 7.1 `DankerMu/SHUD-NC`（父仓库）

#### Issues

| # | State | Title | Link |
|---:|:---:|---|---|
| 32 | OPEN | [B7] runner: 渲染 CRS_WKT 到 cfg.ncoutput | https://github.com/DankerMu/SHUD-NC/issues/32 |
| 31 | OPEN | [NC] 启用 nc profile 端到端运行（shud.run: true） | https://github.com/DankerMu/SHUD-NC/issues/31 |
| 30 | OPEN | [A5] compare_forcing.py: 扩展支持 ERA5 对比 | https://github.com/DankerMu/SHUD-NC/issues/30 |
| 29 | OPEN | [A6] 新增 forcing 适配器扩展点文档 + 模板 | https://github.com/DankerMu/SHUD-NC/issues/29 |
| 21 | CLOSED | [SHUD-NC] 跑通 QHH baseline（sf/terra 版本）并记录回归对比/容差 | https://github.com/DankerMu/SHUD-NC/issues/21 |
| 20 | CLOSED | [SHUD-NC] 增加 R 环境安装/自检脚本与环境文档 | https://github.com/DankerMu/SHUD-NC/issues/20 |
| 19 | CLOSED | [SHUD-NC] 以 submodule 管理 rSHUD + 落地 OpenSpec 提案 | https://github.com/DankerMu/SHUD-NC/issues/19 |
| 16 | CLOSED | [P1] Tools hardening: shudnc nc profile validation + strict compare_* time bounds | https://github.com/DankerMu/SHUD-NC/issues/16 |
| 11 | CLOSED | [Process] Enforce PR review before merge (branch protection + CI required) | https://github.com/DankerMu/SHUD-NC/issues/11 |
| 10 | CLOSED | [OpenSpec] Mark merged changes complete and archive (A/B migration) | https://github.com/DankerMu/SHUD-NC/issues/10 |
| 9 | CLOSED | [Docs] Align Phase B Output SPEC with implemented cfg.ncoutput keys (SCHEMA/OUT_DIR) | https://github.com/DankerMu/SHUD-NC/issues/9 |
| 8 | CLOSED | [Docs] Align Phase A Forcing SPEC with implemented cfg.forcing keys (LAYOUT_*/NC_*) | https://github.com/DankerMu/SHUD-NC/issues/8 |
| 4 | CLOSED | Epic: SHUD NetCDF forcing + output migration (A/B) | https://github.com/DankerMu/SHUD-NC/issues/4 |
| 3 | CLOSED | [R] tools: sampled regression compare (forcing + output) | https://github.com/DankerMu/SHUD-NC/issues/3 |
| 2 | CLOSED | [T2] tools/shudnc.py: enable nc profile validate/run | https://github.com/DankerMu/SHUD-NC/issues/2 |
| 1 | CLOSED | [T1] tools/shudnc.py: render SHUD cfg overlays (render-shud-cfg) | https://github.com/DankerMu/SHUD-NC/issues/1 |

#### PRs

| # | State | Title | Link |
|---:|:---:|---|---|
| 36 | MERGED | feat: Phase A NetCDF forcing validation pass (10-day QHH) | https://github.com/DankerMu/SHUD-NC/pull/36 |
| 35 | MERGED | chore: update rSHUD submodule ref (snap tol fix) | https://github.com/DankerMu/SHUD-NC/pull/35 |
| 34 | MERGED | chore: update SHUD submodule ref (TSR default on) | https://github.com/DankerMu/SHUD-NC/pull/34 |
| 33 | MERGED | fix: SHUD服务器环境 baseline Step1-3 运行验证 | https://github.com/DankerMu/SHUD-NC/pull/33 |
| 28 | MERGED | fix: update rSHUD submodule ref + river index mismatch testdata | https://github.com/DankerMu/SHUD-NC/pull/28 |
| 27 | MERGED | feat: QHH baseline Step1-3 regression pass | https://github.com/DankerMu/SHUD-NC/pull/27 |
| 26 | MERGED | chore: update submodule refs + add CLAUDE.md | https://github.com/DankerMu/SHUD-NC/pull/26 |
| 25 | MERGED | docs: environment setup + R env scripts | https://github.com/DankerMu/SHUD-NC/pull/25 |
| 24 | MERGED | chore: add rSHUD submodule + OpenSpec change | https://github.com/DankerMu/SHUD-NC/pull/24 |
| 23 | MERGED | docs: add PR review gate instructions | https://github.com/DankerMu/SHUD-NC/pull/23 |
| 22 | MERGED | ci: add gh-pr-review merge gate | https://github.com/DankerMu/SHUD-NC/pull/22 |
| 18 | MERGED | chore: update SHUD submodule to 8bfc65c | https://github.com/DankerMu/SHUD-NC/pull/18 |
| 17 | MERGED | fix: harden tools config + strict compare bounds | https://github.com/DankerMu/SHUD-NC/pull/17 |
| 15 | MERGED | chore: bump SHUD submodule ref | https://github.com/DankerMu/SHUD-NC/pull/15 |
| 14 | MERGED | ci: add OpenSpec + python smoke workflow | https://github.com/DankerMu/SHUD-NC/pull/14 |
| 13 | MERGED | openspec: archive completed migration changes | https://github.com/DankerMu/SHUD-NC/pull/13 |
| 12 | MERGED | docs: align Phase A/B specs with rendered cfg keys | https://github.com/DankerMu/SHUD-NC/pull/12 |
| 7 | MERGED | [R] tools: sampled regression compare | https://github.com/DankerMu/SHUD-NC/pull/7 |
| 6 | MERGED | [T2] tools/shudnc.py: enable nc profile validate/run | https://github.com/DankerMu/SHUD-NC/pull/6 |
| 5 | MERGED | [T1] tools/shudnc.py: render SHUD cfg overlays | https://github.com/DankerMu/SHUD-NC/pull/5 |

### 7.2 `DankerMu/SHUD-up`（SHUD 子模块）

#### Issues

| # | State | Title | Link |
|---:|:---:|---|---|
| 76 | CLOSED | [B7] runner: 渲染 CRS_WKT 到 cfg.ncoutput | https://github.com/DankerMu/SHUD-up/issues/76 |
| 75 | CLOSED | [B7] runner 侧: 渲染 CRS_WKT 到 cfg.ncoutput | https://github.com/DankerMu/SHUD-up/issues/75 |
| 74 | OPEN | [B6] NetCDF output: SCHEMA 字段解析与 schema 驱动输出控制 | https://github.com/DankerMu/SHUD-up/issues/74 |
| 73 | OPEN | [A5] NetCDF forcing: 恢复非 CSV 模式下的 forcing 范围检查 | https://github.com/DankerMu/SHUD-up/issues/73 |
| 69 | CLOSED | [P1] NetCDF output: CF/UGRID metadata + schema handling + Conventions + sink ownership hardening | https://github.com/DankerMu/SHUD-up/issues/69 |
| 68 | CLOSED | [P0] NetCDF forcing: apply RADIATION_KIND + fix ERA5 SSR (SWNET) double-albedo | https://github.com/DankerMu/SHUD-up/issues/68 |
| 66 | CLOSED | [Process] Enforce PR review before merge (branch protection + CI required) | https://github.com/DankerMu/SHUD-up/issues/66 |
| 53 | CLOSED | [B5] NetCDF output: metadata registry + masks + fill values | https://github.com/DankerMu/SHUD-up/issues/53 |
| 52 | CLOSED | [B4] NetCDF output: add riv/lake files | https://github.com/DankerMu/SHUD-up/issues/52 |
| 51 | CLOSED | [B3] NetCDF output: write UGRID mesh in element file | https://github.com/DankerMu/SHUD-up/issues/51 |
| 50 | CLOSED | [B2] NetCDF output core: element file + time axis append | https://github.com/DankerMu/SHUD-up/issues/50 |
| 49 | CLOSED | [B1] Print_Ctrl: add sink interface (legacy unchanged) | https://github.com/DankerMu/SHUD-up/issues/49 |
| 48 | CLOSED | [B0] Parse OUTPUT_MODE/NCOUTPUT_CFG in cfg.para (default LEGACY) | https://github.com/DankerMu/SHUD-up/issues/48 |
| 47 | CLOSED | [A4] NetCDF forcing provider: ERA5 subset (accumulated tp/ssr) | https://github.com/DankerMu/SHUD-up/issues/47 |
| 46 | CLOSED | [A3] NetCDF forcing provider: CMFD2 (NEAREST + unit conversion) | https://github.com/DankerMu/SHUD-up/issues/46 |
| 45 | CLOSED | [A2] Makefile: optional NetCDF build flag (NETCDF=1) | https://github.com/DankerMu/SHUD-up/issues/45 |
| 44 | CLOSED | [A1] Refactor forcing access behind ForcingProvider abstraction | https://github.com/DankerMu/SHUD-up/issues/44 |
| 43 | CLOSED | [A0] Parse FORCING_MODE/FORCING_CFG in cfg.para (default CSV) | https://github.com/DankerMu/SHUD-up/issues/43 |
| 42 | CLOSED | TSR: make terrain shortwave factor forcing-interval equivalent (daily forcing bias) | https://github.com/DankerMu/SHUD-up/issues/42 |
| 41 | CLOSED | TSR: make terrain shortwave factor forcing-interval equivalent (fix daily forcing bias) | https://github.com/DankerMu/SHUD-up/issues/41 |
| 40 | CLOSED | Bug: LakeInitialize() 计算 lake area 使用错误索引 (Ele[i] vs Ele[j]) | https://github.com/DankerMu/SHUD-up/issues/40 |
| 19 | CLOSED | [X1] Lake 模块 CVODE 调用疑似传错状态向量（可能影响 qhh 回归） | https://github.com/DankerMu/SHUD-up/issues/19 |
| 18 | CLOSED | [D2] 增补输入/输出时间语义文档（面向用户） | https://github.com/DankerMu/SHUD-up/issues/18 |
| 17 | CLOSED | [D1] 更新/替换 `docs/model_upgrade.md`：把“规划”与“真实实现”对齐 | https://github.com/DankerMu/SHUD-up/issues/17 |
| 16 | CLOSED | [C4] 生成验证报告（Markdown） | https://github.com/DankerMu/SHUD-up/issues/16 |
| 15 | CLOSED | [C3] Python 重实现 TSR（与 C++ 一致）并做数值对比 | https://github.com/DankerMu/SHUD-up/issues/15 |
| 14 | CLOSED | [C2] 实现输出读取器（支持 .dat 或 .csv） | https://github.com/DankerMu/SHUD-up/issues/14 |
| 13 | CLOSED | [C1] 设计验证目录结构与运行脚本（TSR off/on） | https://github.com/DankerMu/SHUD-up/issues/13 |
| 12 | CLOSED | [B4] 新增 TSR 调试/验证输出通道（rn_h/rn_t/factor） | https://github.com/DankerMu/SHUD-up/issues/12 |
| 11 | CLOSED | [B3] 把 TSR 集成到 `tReadForcing()`：修正 DSWRF，再走现有 `(1-Albedo)` 与 PM | https://github.com/DankerMu/SHUD-up/issues/11 |
| 10 | CLOSED | [B2a] 从 `.tsd.forc` 固化 lon/lat，并提供 v1 全域 lon/lat 策略与可追溯输出 | https://github.com/DankerMu/SHUD-up/issues/10 |
| 9 | CLOSED | [B2] 新增 Solar geometry 与 TSR factor 计算（独立模块） | https://github.com/DankerMu/SHUD-up/issues/9 |
| 8 | CLOSED | [B1] 计算并缓存 element 的坡度/坡向/法向量（独立于现有 slope[3]） | https://github.com/DankerMu/SHUD-up/issues/8 |
| 7 | CLOSED | [B0] 明确 forcing 辐射列语义（Rn vs DSWRF），并做可配置输入模式 | https://github.com/DankerMu/SHUD-up/issues/7 |
| 6 | CLOSED | [A6] 输出对齐：替换 `long(t)%Interval` 的脆弱触发 | https://github.com/DankerMu/SHUD-up/issues/6 |
| 5 | CLOSED | [A5] 恢复或移除 ET_STEP/LSM_STEP：让参数语义与实现一致 | https://github.com/DankerMu/SHUD-up/issues/5 |
| 4 | CLOSED | [A4] 统一推进所有会被使用的 TSD 指针（避免冻结） | https://github.com/DankerMu/SHUD-up/issues/4 |
| 3 | CLOSED | [A3] 时间列单调性与覆盖范围预检查（fail-fast） | https://github.com/DankerMu/SHUD-up/issues/3 |
| 2 | CLOSED | [A2] 实现 validateTimeStamps：统一校验 forcing 与所有 TSD 头部日期 | https://github.com/DankerMu/SHUD-up/issues/2 |
| 1 | CLOSED | [A1] 新增 TimeContext/TimeManager（最小可用版本） | https://github.com/DankerMu/SHUD-up/issues/1 |

#### PRs

| # | State | Title | Link |
|---:|:---:|---|---|
| 78 | MERGED | fix: NetCDF forcing month-range off-by-one + CSV quantization matching | https://github.com/DankerMu/SHUD-up/pull/78 |
| 77 | MERGED | feat: enable terrain solar radiation (TSR) by default | https://github.com/DankerMu/SHUD-up/pull/77 |
| 72 | MERGED | ci: add gh-pr-review merge gate | https://github.com/DankerMu/SHUD-up/pull/72 |
| 71 | MERGED | fix: NetCDF output metadata + CRS hook + sink ownership | https://github.com/DankerMu/SHUD-up/pull/71 |
| 70 | MERGED | fix: derive radiation semantics from FORCING_CFG RADIATION_KIND | https://github.com/DankerMu/SHUD-up/pull/70 |
| 67 | MERGED | ci: add GitHub Actions build workflow | https://github.com/DankerMu/SHUD-up/pull/67 |
| 65 | MERGED | Fix lake area accumulation index | https://github.com/DankerMu/SHUD-up/pull/65 |
| 64 | MERGED | [B5] NetCDF output: metadata + masks + fill values | https://github.com/DankerMu/SHUD-up/pull/64 |
| 63 | MERGED | [B4] NetCDF output: add riv/lake files | https://github.com/DankerMu/SHUD-up/pull/63 |
| 62 | MERGED | [B3] NetCDF output: write UGRID mesh in element file | https://github.com/DankerMu/SHUD-up/pull/62 |
| 61 | MERGED | [B2] NetCDF output core: element file + time axis append | https://github.com/DankerMu/SHUD-up/pull/61 |
| 60 | MERGED | [B1] Print_Ctrl: add sink interface (legacy unchanged) | https://github.com/DankerMu/SHUD-up/pull/60 |
| 59 | MERGED | [B0] Parse OUTPUT_MODE/NCOUTPUT_CFG in cfg.para | https://github.com/DankerMu/SHUD-up/pull/59 |
| 58 | MERGED | [A4] NetCDF forcing provider: ERA5 subset | https://github.com/DankerMu/SHUD-up/pull/58 |
| 57 | MERGED | [A3] NetCDF forcing provider: CMFD2 | https://github.com/DankerMu/SHUD-up/pull/57 |
| 56 | MERGED | [A1] Refactor forcing access behind ForcingProvider abstraction | https://github.com/DankerMu/SHUD-up/pull/56 |
| 55 | MERGED | [A0] Parse FORCING_MODE/FORCING_CFG in cfg.para (default CSV) | https://github.com/DankerMu/SHUD-up/pull/55 |
| 54 | MERGED | [A2] Makefile: optional NetCDF build flag (NETCDF=1) | https://github.com/DankerMu/SHUD-up/pull/54 |
| 39 | MERGED | docs(D2): add user-facing time semantics | https://github.com/DankerMu/SHUD-up/pull/39 |
| 38 | MERGED | docs(D1): align model_upgrade As-Is vs To-Be | https://github.com/DankerMu/SHUD-up/pull/38 |
| 37 | MERGED | feat(C4): add TSR validation report generator | https://github.com/DankerMu/SHUD-up/pull/37 |
| 36 | MERGED | feat(C3): add Python TSR implementation and cross-validation | https://github.com/DankerMu/SHUD-up/pull/36 |
| 35 | MERGED | feat(C2): add Python SHUD output reader and CLI tools | https://github.com/DankerMu/SHUD-up/pull/35 |
| 34 | MERGED | feat(C1): add TSR validation scripts and framework | https://github.com/DankerMu/SHUD-up/pull/34 |
| 33 | MERGED | feat(B4): add TSR debug/verification output channels (rn_h/rn_t/factor) | https://github.com/DankerMu/SHUD-up/pull/33 |
| 32 | MERGED | feat(B3): integrate TSR into tReadForcing() for terrain radiation correction | https://github.com/DankerMu/SHUD-up/pull/32 |
| 31 | MERGED | fix(X1): correct Lake CVODE state vector from u2 to u5 | https://github.com/DankerMu/SHUD-up/pull/31 |
| 30 | MERGED | feat(B2a): add lon/lat persistence and global strategy | https://github.com/DankerMu/SHUD-up/pull/30 |
| 29 | MERGED | feat(B2): add solar geometry and TSR factor calculation module | https://github.com/DankerMu/SHUD-up/pull/29 |
| 28 | MERGED | feat(B1): add terrain geometry computation for elements (#8) | https://github.com/DankerMu/SHUD-up/pull/28 |
| 27 | MERGED | feat(B0): add RADIATION_INPUT_MODE config for forcing radiation semantics (#7) | https://github.com/DankerMu/SHUD-up/pull/27 |
| 26 | MERGED | feat(A6): replace fragile output trigger with llround (#6) | https://github.com/DankerMu/SHUD-up/pull/26 |
| 25 | MERGED | feat(A5): restore ET_STEP substep logic (#5) | https://github.com/DankerMu/SHUD-up/pull/25 |
| 24 | MERGED | feat(A4): implement unified TSD pointer update mechanism | https://github.com/DankerMu/SHUD-up/pull/24 |
| 23 | MERGED | feat(A3): implement time monotonicity and coverage pre-check (fail-fast) | https://github.com/DankerMu/SHUD-up/pull/23 |
| 22 | MERGED | feat(A3): implement time monotonicity and coverage pre-check (fail-fast) | https://github.com/DankerMu/SHUD-up/pull/22 |
| 21 | MERGED | [A2] Implement validateTimeStamps for unified date validation | https://github.com/DankerMu/SHUD-up/pull/21 |
| 20 | MERGED | [A1] Add TimeContext/TimeManager minimal | https://github.com/DankerMu/SHUD-up/pull/20 |

### 7.3 `DankerMu/AutoSHUD`（AutoSHUD 子模块）

#### Issues

| # | State | Title | Link |
|---:|:---:|---|---|
| 2 | CLOSED | [AutoSHUD] Raster 迁移到 terra + 跑通 QHH Step1–Step3（sf/terra baseline） | https://github.com/DankerMu/AutoSHUD/issues/2 |
| 1 | CLOSED | [AutoSHUD] Step1–Step3：矢量/GEOS 操作迁移到 sf（移除 sp/rgdal/rgeos） | https://github.com/DankerMu/AutoSHUD/issues/1 |

#### PRs

| # | State | Title | Link |
|---:|:---:|---|---|
| 11 | MERGED | fix: terra compat — replace raster::projectRaster in Fun.Soil_Geol | https://github.com/DankerMu/AutoSHUD/pull/11 |
| 10 | MERGED | fix: complete sf/terra migration for Step2+Step3 pipeline | https://github.com/DankerMu/AutoSHUD/pull/10 |
| 9 | MERGED | fix: handle empty CRS from xyz2Raster in raster2Polygon | https://github.com/DankerMu/AutoSHUD/pull/9 |
| 8 | MERGED | fix: use terra API in raster2Polygon for SpatRaster compat | https://github.com/DankerMu/AutoSHUD/pull/8 |
| 7 | MERGED | fix: replace readOGR/gIntersects with sf equivalents in Step2 | https://github.com/DankerMu/AutoSHUD/pull/7 |
| 6 | MERGED | fix: drop empty geometries in read_sf_as_sp | https://github.com/DankerMu/AutoSHUD/pull/6 |
| 5 | MERGED | [AutoSHUD] Migrate raster to terra | https://github.com/DankerMu/AutoSHUD/pull/5 |
| 4 | MERGED | [AutoSHUD] Migrate vector/GEOS ops from sp/rgdal/rgeos to sf | https://github.com/DankerMu/AutoSHUD/pull/4 |
| 3 | MERGED | ci: add gh-pr-review merge gate | https://github.com/DankerMu/AutoSHUD/pull/3 |

### 7.4 `DankerMu/rSHUD`（rSHUD 子模块）

#### Issues

| # | State | Title | Link |
|---:|:---:|---|---|
| 8 | CLOSED | bug: FromToNode simplify=TRUE causes xy2ID total mismatch after force(coord) fix | https://github.com/DankerMu/rSHUD/issues/8 |
| 6 | CLOSED | Bug: shud.river() 中 FromToNode 索引错配导致 Slope 和 @point 系统性错误 | https://github.com/DankerMu/rSHUD/issues/6 |
| 4 | CLOSED | [rSHUD] Remove rgeos from mesh/triangle helpers (sp.Tri2Shape) | https://github.com/DankerMu/rSHUD/issues/4 |
| 1 | CLOSED | [rSHUD] 迁移到 sf/terra：去除旧空间栈硬依赖 + wrapper + tests | https://github.com/DankerMu/rSHUD/issues/1 |

#### PRs

| # | State | Title | Link |
|---:|:---:|---|---|
| 10 | MERGED | fix: revert snap_coords_to_ref tol to dynamic value | https://github.com/DankerMu/rSHUD/pull/10 |
| 9 | MERGED | fix: snap simplified coords back to original ref in FromToNode (#8) | https://github.com/DankerMu/rSHUD/pull/9 |
| 7 | MERGED | fix: resolve FromToNode index mismatch in shud.river() (#6) | https://github.com/DankerMu/rSHUD/pull/7 |
| 5 | MERGED | [rSHUD] Remove rgeos from sp.Tri2Shape | https://github.com/DankerMu/rSHUD/pull/5 |
| 3 | MERGED | [rSHUD] Migrate key GIS APIs to sf/terra | https://github.com/DankerMu/rSHUD/pull/3 |
| 2 | MERGED | ci: add gh-pr-review merge gate | https://github.com/DankerMu/rSHUD/pull/2 |

## 8. 后续工作（来自 open issues）

- Phase B（NetCDF output）
  - SHUD：`#74 [B6] NetCDF output: SCHEMA 字段解析与 schema 驱动输出控制`（OPEN）https://github.com/DankerMu/SHUD-up/issues/74  
  - Runner：`#32 [B7] runner: 渲染 CRS_WKT 到 cfg.ncoutput`（OPEN）https://github.com/DankerMu/SHUD-NC/issues/32
- ERA5 forcing 的工具/验证补齐
  - 工具：`#30 [A5] compare_forcing.py: 扩展支持 ERA5 对比`（OPEN）https://github.com/DankerMu/SHUD-NC/issues/30
- nc profile 端到端 run（把 `profiles.nc.shud.run=true` 真正跑起来）
  - `#31 [NC] 启用 nc profile 端到端运行（shud.run: true）`（OPEN）https://github.com/DankerMu/SHUD-NC/issues/31
- Forcing 校验/硬化
  - SHUD：`#73 [A5] NetCDF forcing: 恢复非 CSV 模式下的 forcing 范围检查`（OPEN）https://github.com/DankerMu/SHUD-up/issues/73
- Forcing adapter 扩展点文档化（便于新增产品/变量名差异）
  - `#29 [A6] 新增 forcing 适配器扩展点文档 + 模板`（OPEN）https://github.com/DankerMu/SHUD-NC/issues/29
