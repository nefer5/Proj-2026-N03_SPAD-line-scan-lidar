# 项目文档导航（现行）

更新：2026-10-18；研究版本0.6.15.dev0。先读现行说明，再按需查兼容参考或历史。文档示例和历史数值不构成第二份运行默认。

## 先读这些权威入口

| 内容 | 唯一维护入口 | 说明 |
|---|---|---|
| 安装与启动 | [项目首页](../README.md)、[启动器指南](guides/launcher.md) | 使用地址以启动器输出为准 |
| 当前结构与模块职责 | [C4架构说明](design/architecture.md) | C1系统、C2应用/存储、C3组件；已反映公共后台与配置第二阶段 |
| 初始默认、覆盖和用户数据 | [配置与数据归属](guides/configuration-and-data.md) | 实际类型/数值分别在Python/YAML，普通草稿不写回，显式“设为默认”可保存 |
| 已确认的取舍与演进 | [架构决策](design/architecture-decisions.md) | 决策正文按日期保留，不把旧数值当当前默认 |
| 配置重构的步骤与门槛 | [第二阶段计划](design/configuration-refactor.md) | 按基线、迁移、组合、写回和验证顺序实施 |
| 实现、待办与验收 | [路标](roadmap.md) | 已确认意图、已实现、自验、人工验收分开 |
| 界面与桌面适配 | [UI规范](design/ui-design-guidelines.md) | 保留2026-10-18的1080P调整，五平台统一后置 |
| 数学/参数强约束 | [AGENTS](../AGENTS.md) | 共享YAML、常数、公式和可审计性 |

[C4四页离线网页](../artifacts/c4-architecture-20261018-172542/index.html)是对应时间的导出快照，不是实时目录或第二套规范。旧的十页架构分析仅留作[历史资料](history/README.md)。

## 模型与操作

| 主题 | 当前说明 |
|---|---|
| B空间光学与数据接口 | [空间光学](models/spatial-optics.md)、[双轴空间分布](models/spatial-profiles.md) |
| 正式C | [列级扫描](models/column-scanning.md)、[C人工验收](validation/c-manual-review.md) |
| 光子预算与参考面 | [共享生成的光子预算](models/photon-budget.md)、[A噪声模型](models/noise-model.md) |
| 光谱、滤光与PDE | [曲线输入](models/curve-inputs.md)、[光谱与背景](models/spectral-background.md) |
| 器件与读出 | [读出/初始化](models/readout-modes.md)、[H/V分组](models/binning.md) |
| 图层、统计与重放 | [直方图指南](guides/histogram-display.md)、[A调试指南](guides/debug-guide.md) |
| 运行记录与备份 | [运行数据](guides/run-artifacts.md) |
| 系统预算 | [操作与模型边界](guides/system-budget.md)、[预算数据时序契约](design/spad-data-timing-design.md) |
| C已确认但未完成的复位机制 | [列内累积与列间复位](design/column-accumulation-design.md) |
| 离线三维库 | [Three.js依赖与恢复](guides/threejs.md) |

光子预算和双轴空间模型文档由共享定义生成；改源YAML后运行对应render脚本的`--check`，不手工造另一套公式。

## 兼容与参考，不作当前默认

- [历史周期C](history/legacy-periodic-scanning.md)：旧kind=scan及旧任务的模型说明；正式入口以列级C为准。
- [历史检测算法](references/legacy-detection-performance.md)：仅显式历史API与旧结果；常规A界面检测/Pd/PFA已停用。
- [PDE文献](references/pde-literature.md)、[Sony参数参考](references/sony-reference.md)、[论文索引](../data/reference/papers/README.md)。
- [三维示意图提示词](references/lidar-3d-schematic-prompt.md)：可复用创作参考，不是架构或模型规范。
- [历史索引](history/README.md)：早期模型/界面方案、阶段复查、旧手册和重整前快照。

## 文档维护规则

design维护结构/已确认机制，models维护物理语义，guides维护操作，validation维护验收，references维护条件/兼容参考，history只供追溯。根目录仅保留索引、路标和版本记录。

新增内容先选权威位置，再以摘要/链接关联其他文档；不在多篇文档维护同一参数或不同的“当前”结论。移动正文时修正相对引用并保留必要旧链接跳转。报告、截图、运行和架构导出统一放artifacts，不自动成为设计规则。归档前原件与处理清单见[本次整理记录](../artifacts/docs-reconcile-20261018-173339/validation.json)。


在线查看：[C4架构分析快照（2026-10-18）](https://nefer5.github.io/Proj-2026-N03_SPAD-line-scan-lidar/)。该网页是静态分析快照，当前结构/参数/状态仍以上表权威文档为准；部署方式见[项目首页](../README.md#在线架构说明)。
