# 系统预算优化版验收 · 2026-10-02

版本0.6.5.dev0。已实现、自验通过；用户人工验收待进行。

- Python专项44项通过：test_line_budget、test_hardware_budget、test_budget_schematic、test_tx_rx_domains。覆盖功率/能量守恒、独立Rx背景、坐标转换、非法配置、旧工况迁移及原输入保护。
- JS语法检查通过；主题、Three.js供应文件及两份共享物理文档同步检查通过。
- 实际浏览器：16→32线，单通道17.5→8.75W、35→17.5nJ，V全角减半；全部收起保持有效摘要。通道V5和列500可选择，列H=0.06°。透视、正视、俯视、侧视、探测器及传播示意入口可用。
- 实际8016普通刷新恢复旧v2草稿，提示显式迁移并保留备份；H一路、空间均匀、Rx原全域转换为单通道宽。无浏览器三维错误，新增共享公式KaTeX无解析错误。
- 深色与浅色实际截图：[深色透视](dark-perspective.png)、[浅色侧视](light-side.png)。深色图使用用户迁移工况，Rx保留历史12mrad H全宽；浅色QA使用当前YAML初始值。
- 默认完整审计快照：[default-snapshot.json](default-snapshot.json)，包含工况、算法、版本、时间、配置指纹及single_channel中间量。

独立同型通道合计不是全阵列耦合光路；三维器件采用展开与放大示意。B/C核心坐标、PSF机制及C列间复位的原有验收状态未改写。功能与边界见[指南](../../docs/guides/system-budget.md)。


## 参数分组修正 · 2026-10-02

HFOV/VFOV成组、slot/线数成组；通道数右侧只读mrad，下面一行等价deg。移除B角边界继承，独立VFOV初始示例10°。当前网页保留用户5线及其他输入，VFOV更新为10°后单通道34.9066mrad=2deg；修改为10线时应为17.4533mrad=1deg，再恢复5线。专项46项通过；新增验证默认与B边界无关、mrad/deg一致以及空VFOV被拒绝。截图见[修正后分组](parameter-grouping.png)。旧默认快照属于修正前历史记录，不冒充新默认。

当前独立VFOV默认完整快照：[default-snapshot-vfov-independent.json](default-snapshot-vfov-independent.json)。


## 全视场与细节面板 · 2026-10-02

- 47项相关测试通过；最终扫描中心mrad元数据补充后11项线阵专项复验通过。JS语法、主题及共享两份物理文档同步检查通过。
- 实际8016验证整机全视场/单列切换、俯视中VCSEL与转镜沿Z对齐且Rx/SPAD沿X支路、mrad输入单位与deg注释、右侧整体角域/局部对照/成像分组、光谱内层12px次级标题和缩进。
- 当前用户工况500 slot、5线、HFOV120deg、VFOV10deg，自动采样角间距H4.18879×V34.9066mrad，等价H0.24×V2deg。保留用户每列2发。
- Rx V原显式值0.375mrad造成整列包络140mrad，而Tx为174.533mrad；网页对照文字明确此原因。点击跟随后Tx/Rx包络均174.533mrad；测试后恢复用户原显式Rx V。
- 测试全场图点选V带、局部快捷入口与探测器视图；三维无控制台错误。演示HTML只读取布局/说明源码作设计参考，没有引入其计算公式或数值默认值。
- 截图：[全场与局部面板](whole-field-details.png)、[规整俯视](aligned-top.png)。当前完整审计数据另存current-ui-audit.json。

全场的柱面/V放大与右侧角坐标展开均明示比例；它们为解释性绘图，没有新增镜面光线追迹或修改B/C历史数值坐标。人工验收仍待用户。
