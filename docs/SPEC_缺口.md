高优先级缺口 / 风险（建议写进 spec，避免返工）

适配层“翻译责任”需要锁死：SPEC A 说 SHUD 不解析 YAML，但 shud.yaml 又引用了 *.yaml。建议明确：*.yaml 仅供 shudnc.py 渲染为 KEY VALUE 的 <prj>.cfg.forcing，SHUD 只读后者（否则会出现两套真相）。
NetCDF 变量维度顺序不能假设：CMFD/ERA5 forcing 变量可能是 (lon,lat,time) 也可能是 (time,lat,lon)；目前 spec 只写“维度名”，缺少“必须按维度名匹配构造 start/count”的硬要求，风险是“读到了但轴顺序错了还不报错”。
CMFD 降水单位与 AutoSHUD 现状存在差异：AutoSHUD 里 unitConvert.CMFD 用 prec*24（mm/hr→mm/day，见 LDAS_UnitConvert.R (line 73)），而你的 SPEC A/总体方案强调本地 CMFD2 可能是 kg m-2 s-1（应 *86400）。你已经设计 AUTO‑detect + override，这是正确方向；建议把“识别失败必须报错并提示显式指定”的条款写得更硬。
ERA5 累积量语义风险：tp/ssr 的“累积窗口/重置”随数据导出方式可能不同；建议在 SPEC A 增加一条“通过样例文件 metadata + 与 baseline 对齐”来锁定算法（避免实现完才发现相位偏移/日累计错位）。
输出 NetCDF 要写全量维度时，Print_Ctrl 需保留 n_all：目前 Init(..., flag_IO) 会把 NumVar 改成“选中列数”，丢失全量列数；而 SPEC B 要把禁用列填 _FillValue，所以必须让 Print_Ctrl 额外保存 n_all（以及 icol[]）。SPEC B 的 onInit(n_all, num_selected, icol) 很关键，建议把“Print_Ctrl 必须持久化 n_all”的实现要求写进 spec。
ele/riv/lake 归类规则要更稳：靠变量名前缀一般可行，但现有也有 rn_h/rn_t/rn_factor 这类 element 维输出不带 ele 前缀（MD_initialize.cpp (line 242) 附近）。建议规定：优先按 n_all == NumEle/NumRiv/NumLake 归类，必要时再按名前缀兜底。
构建可移植性：Makefile (line 1) 偏 /usr/local；Apple Silicon Homebrew 常在 /opt/homebrew。引入 NETCDF=1 时建议 spec 里同时规定“优先用 nc-config/pkg-config netcdf 取编译链接参数”，减少环境坑。