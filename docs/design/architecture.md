# SPAD 项目架构（现行）

更新：2026-10-18。范围：0.6.15.dev0，包含公共后台和领域化配置两阶段实现。本文是当前结构、职责和依赖边界的权威说明，按C4前三层组织。

| 问题 | 权威入口 |
|---|---|
| 当前结构和数据边界 | 本文 |
| 参数定义、初始值和用户输入保存 | [配置与数据归属](../guides/configuration-and-data.md)，实际字段/数值以Python类型及YAML为准 |
| 为什么这样设计、哪些意图已确认 | [架构决策](architecture-decisions.md) |
| 实现、自验、人工验收到哪里 | [路标](../roadmap.md) |
| 具体物理含义、公式和限制 | [模型导航](../index.md#模型与操作)及其共享定义来源 |

[C4四页网页版](../../artifacts/c4-architecture-20261018-172542/index.html)为2026-10-18设计/实现过程的带时间离线快照，范围与当时版本以页内标记为准，包含C1/C2/C3、数据、目录及复用；它不是实时扫描或第二份规范。旧说明已保留于[重整前架构快照](../history/architecture-before-c4-20261018.md)。

## C1：系统上下文

研究人员使用同一套本地软件研究光子预算、器件/数字读出、空间光学、扫描和系统预算。导入曲线/光学数据及导出结果是文件交换，不等于已直连真实仪器、Zemax宿主或云端存储。

### 入口与模型范围

| 模式 / 入口 | 职责与边界 |
|---|---|
| A：`/`、`/debug` | 单角能量与独立IFOV；评估/调试是同一模型的视图；解析参考与事件模式分开 |
| 独立SPAD：`/spad` | 直接输入探测面照明；不要求整机Tx/Rx、距离或孔径 |
| B：`/system` | 静态Tx/场景/Rx映射到像素，再使用共同采集核心 |
| 正式C：`/system/scan`、`/system/columns` | 显式逐发与门程序、运动投影、跨列状态、列级重建及输出资源 |
| 系统预算：`/system/budget` | 确定性光学/时间/电热/硬件容量研究，不生成最终混合采集记录 |
| 历史周期C：`/system/scan/legacy` | 兼容旧模型与旧任务；[历史说明](../history/legacy-periodic-scanning.md)，不替代正式列级C |

三个工作台只是后续界面整合建议。当前五平台及2026-10-18桌面/1080P适配保留；界面规范见[UI规范](ui-design-guidelines.md)。

## C2：应用、存储与运行边界

| 单元 | 责任 | 数据归属 |
|---|---|---|
| 浏览器应用 | 参数输入、草稿、预览/结果绘图、文件导入导出 | 内存及各平台的localStorage/sessionStorage；A不具备与B/C完全相同的持久草稿机制 |
| 本地Python应用 | FastAPI路由、校验、JobManager、spawn进程池、物理计算与结果装配 | 进程池仍属同一后端应用，不是独立微服务 |
| 项目YAML | 初始工况、算法策略和共享说明 | 普通编辑保存草稿；“设为默认”经预览、跨平台校验和备份后写回defaults.yaml；目录和继承详见[配置说明](../guides/configuration-and-data.md) |
| 任务存储 | SQLite状态与每任务request/result/error | 具体字段、备份及跨路径恢复见[运行数据](../guides/run-artifacts.md) |
| 用户文件 | 原始导入文件及显式下载的配置/结果 | 没有自动保存原件附件库；预算响应不自动成为采集结果文件 |

采集任务提交时冻结完整YAML、规范工况和算法；运行不追随之后编辑。服务发现原任务所有者已退出后标为interrupted；核心checkpoint不等于作业能自动崩溃续算。取消时机保持各用例的安全检查点；A兼容求解仍在整次求解后检查。

## C3：后端组件

### 代码职责与依赖

| 组件 / 目录 | 公共职责 | 保留的专用部分 |
|---|---|---|
| `configuration.py`、`default_layout.py`、`default_composition.py`、`models.py`、`domains/` | 严格加载、领域默认组合/来源追踪、字段与约束 | 平台配置组合和历史迁移；默认值不放在类型里 |
| `default_store.py`、`webapi/defaults.py` | 默认变更预览、继承归属、跨平台校验、备份与原子保存 | 只有显式确认写入；不改任务快照或算法默认 |
| `optics/` + `tx/scene/rx/numerics` | 光学数据校验、谱/能量积分、探测面照明与审计 | A单角适配、静态与逐发姿态输入；不猜测退化等价 |
| `acquisition/` | TrialPlan、顺序重复执行、周期记录适配 | A/B/C原seed分流、统计角色、初始化及资源检查 |
| `spad/` | 候选源、器件恢复、OR/符合、TDC与状态会话 | 可注入后端；不反向导入整机、网页、实验或任务层 |
| `experiments/`、`scan/` | 用例组装、扫描计划/轨迹、数据与时序衔接 | A解析/旧RNG、SPAD直照、B静态、C门碎片与列归属 |
| `processing/`、`reporting/` | 记录、直方图、测距与统计；Python审计/展示装配 | 不在前端复制物理公式；观测记录与真值分离 |
| `system_budget.py`等、`scan/transport.py` | 预算和输出资源研究 | C电学仍在迭代；两套调度策略保留，按用户要求暂缓整合 |
| `webapi/`、`runtime/` | HTTP、校验与任务IO、结果读取/显示适配 | 预算为同步无状态路径；采集用例走任务管理 |

网页公共外壳由`webapi/chrome.py`装配五平台导航，`web/shared/workspace.css/js`维护阅读尺度与科学图可视区，主题仍由共享theme管理。它们不参与默认组合或数值计算；具体导航顺序和样式只维护在[界面规范](ui-design-guidelines.md#2026-10-18-五平台导航与1080p阅读尺度)。

`acquisition/`是器件核心之上的实验编排，`spad/acquisition.py`才维护状态和时间水位。旧`experiments.spatial`、`experiments.lab`等兼容导入继续导出同一公共对象；新增调用优先使用新归属模块。光学服务与领域定义不依赖实验/展示/任务/网页层，边界由测试维护。

### 稳定契约

- `SensorIllumination`：完整像素、PDE/FF之前的`[pixel,wavelength]`光子数/发或光子数/秒，已经包含光谱积分权重；稠密与精确外积表示含义一致。
- `CandidateEvents`：绝对时间ns与物理像素ID的候选雪崩；不能冒充光学输入。
- `AcquisitionProgram`：显式区间、器件门/读出门与测量标志；C可表达门并集与碎片。
- `AcquisitionSession`：跨块器件与读出状态、水位、记录；内置后端可checkpoint/restore，未知后端需自己的适配器。
- records：周期与列级格式各有时间原点/区间/硬件身份，C另有列/帧/触发参考；不借隐藏真值恢复丢失身份。合法重分箱只使用原TDC宽度整数倍。

## 实施状态与后续

<a id="2026-10-18后台结构重构第一阶段"></a>

第一阶段已提取领域字段、公共光学、周期适配和TrialPlan/顺序执行器。431项原回归、13项边界测试及19组完整数值/schema对照自验通过；已有前端、全部YAML、器件/读出核心和启动器字节保留。证据与回退见[第一阶段记录](../../artifacts/refactor-phase1-20261018-170544/validation.json)。

尚未完成：跨平台参数语义的剩余系统审计、三个工作台、C列间完全复位及C人工精细验收。C后续电学与C/预算调度整合按用户要求暂缓，移出当前结构重构范围。详细优先级只维护在[路标](../roadmap.md)，不以目录提取或图表检查代替功能验收。


## 2026-10-18：配置重构第二阶段

工况默认文件升级为领域化schema 2，公共Tx/Rx/器件/采集/运动/系统目标在domains下唯一维护，各平台差异保留在experiments。独立default_composition统一生成六种兼容工况并追踪原始字段来源；默认读取和“设为默认”写回复用同一映射，default_layout明确区分新布局与旧YAML快照。

BSystemConfig已归入domains/optical_system；ColumnMotion与ScanAcquisition归入scan/config，旧导出兼容。正式C直接组合公共光学、运动、系统目标和列级参数，不再先生成历史扫描工况；预算在同一组合层添加专用覆盖，再进入既有预算约束/派生计算。实际默认层级及兼容边界只维护在[配置说明](../guides/configuration-and-data.md#当前默认值结构与继承)。

这一阶段不修改采集随机协议、器件状态机制、物理公式或前端布局。C/预算调度统一随C后续电学迭代暂缓；C列间复位维持既有未完成状态。数值/schema对照及迁移证据见[第二阶段记录](../../artifacts/refactor-phase2-20261018-185756/README.md)。
