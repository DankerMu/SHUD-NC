# SPEC（阶段 B）：SHUD 输出写规范 NetCDF（CF/UGRID 友好）

> Last updated: 2026-02-07  
> 目标：在 **不破坏 legacy 输出**（CSV/Binary）的前提下，为 SHUD 增加一个 NetCDF 输出通道，产出 **可被 xarray/netCDF4/QGIS/Panoply 直接读取** 的标准化 NetCDF 文件，并复用现有 `Print_Ctrl` 的“输出间隔 + 平均/积分语义”。

## 1. 范围与非目标

### 范围
- SHUD 增加 NetCDF 输出（可与 legacy 并存）：
  - 3 个文件：`<prj>.ele.nc` / `<prj>.riv.nc` / `<prj>.lake.nc`
- 复用 `Print_Ctrl` 的 buffer 机制，确保与 legacy 输出语义一致：
  - state：区间平均（`tau=1`）
  - flux：区间平均并折算到“每 day”（`tau=1440`）
  - time：沿用现有 “left endpoint (t-Interval)” 语义
- 写出 UGRID mesh（element 文件），使 element 变量可与非结构网格拓扑绑定。

### 非目标（阶段 B 不做）
- 不在本阶段重命名/语义重构所有变量（第一版优先“可回归 + 可读”）。
- 不强制对所有变量补全 CF `standard_name`（可选增强项）。

---

## 2. 配置与开关（`.cfg` 风格）

### 2.1 `.cfg.para` 新增键
在 `input/<prj>/<prj>.cfg.para` 增加：
- `OUTPUT_MODE LEGACY|NETCDF|BOTH`（缺省 `LEGACY`）
- `NCOUTPUT_CFG <path>`（当 `OUTPUT_MODE` 包含 `NETCDF` 时必填）

> 解析规则：相对路径相对 `input/<prj>/`。

### 2.2 `<prj>.cfg.ncoutput`（KEY VALUE）
建议文件：`input/<prj>/<prj>.cfg.ncoutput`：

**路径与文件组织**
- `OUTPUT_NETCDF_DIR <path>`：输出目录（相对/绝对）；若相对，则相对 **运行目录（run_dir）** 或 `output/<prj>.out`（需在实现中固定一条规则并记录）
- `OUTPUT_NETCDF_PREFIX <string>`（可选，默认 `<prj>`）

**格式与性能**
- `NETCDF_FORMAT NETCDF4_CLASSIC|NETCDF4`（默认 `NETCDF4_CLASSIC`）
- `DEFLATE_LEVEL 0-9`（默认 `4`）
- `CHUNK_TIME <int>`（默认 `1`；time 维 chunk）

**写出控制**
- `WRITE_MESH 1|0`（默认 `1`：在 ele 文件写 UGRID mesh）
- `WRITE_FACE_CENTER 1|0`（默认 `1`）

---

## 3. 输出文件与维度约定

### 3.1 文件
- Element：`<prefix>.ele.nc`
- River：`<prefix>.riv.nc`
- Lake：`<prefix>.lake.nc`

### 3.2 time 维与语义（关键）
- 维度：`time`（unlimited）
- time 值：以 SHUD 内部分钟 `t_min` 写入（double）
- `time.units = "minutes since <ForcStartTime YYYY-MM-DD> 00:00:00 UTC"`
  - `<ForcStartTime>` 来自 `<prj>.tsd.forc` 首行
- **time 语义必须与 legacy 输出一致**：沿用 `Print_Ctrl::PrintData()` 的写出时刻
  - 现有实现用 `t_quantized = floor(t) - Interval`（left endpoint）
  - NetCDF 输出必须写同样的 `t_quantized`

> 结果：NetCDF 与 legacy CSV/Binary 在 time 坐标上可逐行对齐。

---

## 4. UGRID mesh（写入 `<prefix>.ele.nc`）

> 目标：element 变量可在非结构网格上被可视化/后处理。

### 4.1 必需维度
- `mesh_node`：节点数 = `NumNode`
- `mesh_face`：三角形单元数 = `NumEle`
- `max_face_nodes`：常量 = `3`

### 4.2 必需变量（建议命名）
- `mesh_node_x(mesh_node)`：double，单位 `m`
- `mesh_node_y(mesh_node)`：double，单位 `m`
- `mesh_face_nodes(mesh_face, max_face_nodes)`：int32
  - 属性：`cf_role="face_node_connectivity"`
  - 属性：`start_index=1`（与 SHUD 输入 1‑based 一致）

### 4.3 mesh topology 变量
写一个标量变量 `mesh`（int32 或 byte）：
- `cf_role="mesh_topology"`
- `topology_dimension=2`
- `node_coordinates="mesh_node_x mesh_node_y"`
- `face_node_connectivity="mesh_face_nodes"`

### 4.4 面心坐标（可选但默认开启）
若 `WRITE_FACE_CENTER=1`：
- `mesh_face_x(mesh_face)`：double，单位 `m`（用 `Ele[i].x`）
- `mesh_face_y(mesh_face)`：double，单位 `m`（用 `Ele[i].y`）

---

## 5. element / river / lake 的索引坐标

### element 文件（推荐）
- `element_id(mesh_face)`：int32，值为 `1..NumEle`

### river 文件（推荐）
- `river_id(river)`：int32，值为 `1..NumRiv`
- 可选静态属性：
  - `river_down(river)`：int32（`Riv[i].down`，1‑based，0/NA 表示无下游）
  - `river_type(river)`：int32（`Riv[i].type`）

### lake 文件（推荐）
- `lake_id(lake)`：int32，值为 `1..NumLake`
- `lake_x(lake)` / `lake_y(lake)`：double（来自 `_Lake::x/y`）

---

## 6. 如何复用 `Print_Ctrl`：sink 机制（实现必须按此改造）

### 6.1 抽象接口
为 `Print_Ctrl` 增加可选 sink（伪接口）：

- `IPrintSink::onInit(const Print_Ctrl& ctrl, const char* legacy_basename, int n_all, int num_selected, const double* icol)`
- `IPrintSink::onWrite(const Print_Ctrl& ctrl, double t_quantized_min, const double* buffer_selected)`
- `IPrintSink::onClose(const Print_Ctrl& ctrl)`

其中：
- `legacy_basename`：来自 `Print_Ctrl::Init(..., const char* s, ...)` 的 `s`（例如 `.../qhh.eleygw`）
- `n_all`：Init 传入的原始列数（NumEle/NumRiv/NumLake）
- `num_selected` 与 `icol[]`：与 legacy binary header 一致（表示输出列选择）

### 6.2 输出列选择（cfg.output）
为兼顾“用户友好 + 与 legacy 一致”，NetCDF 输出要求：
- NetCDF 变量维度使用 **全量维度**（`mesh_face`/`river`/`lake`）  
- 对于 legacy 关闭输出的列，用 `_FillValue` 填充（默认 `9.96921e36f`）
- 同时写一个 mask（可选增强，但建议第一版就加）：
  - `element_output_mask(mesh_face)`：0/1
  - `river_output_mask(river)`：0/1
  - `lake_output_mask(lake)`：0/1

> 这样用户直接用 `(time, element)` 维度做计算，不需要先用 `icol` 重建索引。

### 6.3 变量命名（从 legacy basename 派生）
对任意 `legacy_basename`（如 `.../qhh.eleygw`）：
- 取最后一个路径段 `qhh.eleygw`
- 再取最后一个 `.` 后的后缀作为 NetCDF 变量名：`eleygw`

> 该规则与 `SHUD/src/classes/IO.cpp` 的命名体系天然一致。

---

## 7. 变量集合（第一版：覆盖现有 Print_Ctrl 输出）

### 7.1 原则
- NetCDF 输出变量集合以 `Model_Data::initialize_output()` 中启用的 `Print_Ctrl` 为准（由 `.cfg.para` 的 `dt_*` 控制）。
- 每个启用的 `Print_Ctrl` 对应一个 NetCDF 变量。
- 数据类型建议：`float32`（体积小），time 为 `float64`。

### 7.2 units 与 long_name（最小必需）
实现中建立一个 registry（按变量名后缀匹配），至少覆盖：

**Element storage（单位 m）**
- `eleyic`：interception storage
- `eleysnow`：snow depth
- `eleysurf`：surface water depth
- `eleyunsat`：unsat storage depth
- `eleygw`：groundwater head

**Element flux（单位 m/day）**
- `elevprcp`：precip (to land)
- `elevnetprcp`：net precip
- `elevetp`：potential ET
- `eleveta`：actual ET
- `elevrech`：recharge
- `elevinfil`：infiltration
- `elevexfil`：exfiltration
- `elevetic` / `elevettr` / `elevetev`：ET components

**Element/river exchange（单位 m3/day）**
- `eleqrsurf`：element→river surface
- `eleqrsub`：element→river subsurface

**Element inter‑cell flux（单位 m3/day）**
- `eleqsub` / `eleqsub1` / `eleqsub2` / `eleqsub3`
- `eleqsurf` / `eleqsurf1` / `eleqsurf2` / `eleqsurf3`

**River（单位 m3/day 或 m）**
- `rivqdown` / `rivqup` / `rivqsurf` / `rivqsub`：m3/day
- `rivystage`：m

**Lake（单位 m / m2 / m3/day / m/day）**
- `lakystage`：m
- `lakatop`：m2
- `lakvevap` / `lakvprcp`：m/day
- `lakqrivin` / `lakqrivout` / `lakqsurf` / `lakqsub`：m3/day

> 备注：以上单位是按 SHUD legacy 命名约定（`y/v/q`）推导；实现必须与现有 legacy 输出一致（即 `Print_Ctrl` 的 `tau` 语义）。

---

## 8. NetCDF 全局属性（建议第一版就写全）

每个文件写：
- `Conventions="CF-1.10, UGRID-1.0"`
- `title="SHUD output: <prj>"`
- `history`：追加一行（包含 SHUD 版本、运行时间、git sha 可选）
- `forcing_mode` / `forcing_product`（若可获取）
- `source="SHUD"`

---

## 9. 回归验证（必须）

最小回归：
1) 同一输入目录下，开启 legacy（CSV/Binary）输出跑 2–10 天（缩短 END）。
2) 开启 NetCDF 输出（可与 legacy 同时开启）。
3) 随机抽样 2 个变量（如 `eleygw`、`rivqdown`）：
   - legacy CSV 与 NetCDF 对齐同一 time、同一 element/river，数值一致（允许极小浮点误差）。

