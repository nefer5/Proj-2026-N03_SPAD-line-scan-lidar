from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
documents={
'docs/design/architecture.md':'''# SPAD 项目架构（现行）

更新：2026-10-18。范围：0.6.14.dev0及已完成的后台第一阶段工作树；不是已发布的新版本。本文是当前结构、职责和依赖边界的权威说明，按C4前三层组织。

| 问题 | 权威入口 |
|---|---|
| 当前结构和数据边界 | 本文 |
| 参数定义、初始值和用户输入保存 | [配置与数据归属](../guides/configuration-and-data.md)，实际字段/数值以Python类型及YAML为准 |
| 为什么这样设计、哪些意图已确认 | [架构决策](architecture-decisions.md) |
| 实现、自验、人工验收到哪里 | [路标](../roadmap.md) |
| 具体物理含义、公式和限制 | [模型导航](../index.md#模型与操作)及其共享定义来源 |

[C4四页网页版](../../artifacts/c4-architecture-20261018-172542/index.html)为本次工作树的离线导出，包含C1/C2/C3、数据、目录及复用；它不是实时扫描或第二份规范。旧说明已保留于[重整前架构快照](../history/architecture-before-c4-20261018.md)。

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
| 项目YAML | 初始工况、算法策略和共享说明 | 网页编辑不写回项目默认；目录和继承详见[配置说明](../guides/configuration-and-data.md) |
| 任务存储 | SQLite状态与每任务request/result/error | 具体字段、备份及跨路径恢复见[运行数据](../guides/run-artifacts.md) |
| 用户文件 | 原始导入文件及显式下载的配置/结果 | 没有自动保存原件附件库；预算响应不自动成为采集结果文件 |

采集任务提交时冻结完整YAML、规范工况和算法；运行不追随之后编辑。服务发现原任务所有者已退出后标为interrupted；核心checkpoint不等于作业能自动崩溃续算。取消时机保持各用例的安全检查点；A兼容求解仍在整次求解后检查。

## C3：后端组件

### 代码职责与依赖

| 组件 / 目录 | 公共职责 | 保留的专用部分 |
|---|---|---|
| `configuration.py`、`models.py`、`domains/` | 严格加载、字段与约束、统一配置入口 | 平台配置组合和历史迁移；默认值不放在类型里 |
| `optics/` + `tx/scene/rx/numerics` | 光学数据校验、谱/能量积分、探测面照明与审计 | A单角适配、静态与逐发姿态输入；不猜测退化等价 |
| `acquisition/` | TrialPlan、顺序重复执行、周期记录适配 | A/B/C原seed分流、统计角色、初始化及资源检查 |
| `spad/` | 候选源、器件恢复、OR/符合、TDC与状态会话 | 可注入后端；不反向导入整机、网页、实验或任务层 |
| `experiments/`、`scan/` | 用例组装、扫描计划/轨迹、数据与时序衔接 | A解析/旧RNG、SPAD直照、B静态、C门碎片与列归属 |
| `processing/`、`reporting/` | 记录、直方图、测距与统计；Python审计/展示装配 | 不在前端复制物理公式；观测记录与真值分离 |
| `system_budget.py`等、`scan/transport.py` | 预算和输出资源研究 | C与预算仍是两套调度策略，尚未统一算法 |
| `webapi/`、`runtime/` | HTTP、校验与任务IO、结果读取/显示适配 | 预算为同步无状态路径；采集用例走任务管理 |

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

尚未完成：默认YAML领域化、C/预算完整配置组合迁移、三个工作台、C列间完全复位、C/预算调度统一及C人工精细验收。详细优先级只维护在[路标](../roadmap.md)，不以目录提取或图表检查代替功能验收。
''',
'docs/guides/configuration-and-data.md':'''# 配置、默认值与用户数据归属（现行）

更新：2026-10-18。本文解释参数类型、初始值、用户覆盖和持久数据；结构见[架构](../design/architecture.md)，运行备份见[运行数据](run-artifacts.md)。不在文档复制另一套可运行默认值。

## 唯一来源

| 内容 | 权威来源 |
|---|---|
| 工况初始值 | `config/defaults.yaml` |
| 算法、采样策略、容差与资源限额 | `config/algorithms.yaml` |
| 类型、枚举、范围与跨字段约束 | `models.py`、`domains/`、平台配置组合类型 |
| 单位、适用条件、生效说明 | `config/parameter-help.yaml` |
| 光谱/曲线模式与参考数据 | `curve-inputs.yaml`、`spectral-data.yaml`、`pde-datasets.yaml` |
| 展示公式与光子步骤 | `formulas.yaml`、`formula-notes.yaml`、`photon-flow.yaml` |
| SI常数 | `src/spad_lidar/constants.py` |

`SimulationConfig`合并默认和覆盖后严格校验，YAML拒绝重复键，缺默认键、未知键、非有限值或非法范围均报错；不通过静默裁剪或补造默认绕过限制。

## 当前默认值继承

| 模式 | 解析来源 | 专用含义 |
|---|---|---|
| A | `simulation.*` | 当前角通道Tx前能量、独立IFOV |
| 独立SPAD | 引用simulation的器件/读出/时序/PDE，再合并`experiments.spad` | 探测面直接照明，无整机Tx/Rx |
| B | 公共simulation字段按领域映射，再合并`experiments.system.tx/rx/...` | 全Tx角域、静态Rx/PSF/像素映射 |
| C | B光学默认→历史scan配置基础→`experiments.columns` | 列目标、运动、曝光列表和输出参数 |
| 预算 | B默认→`experiments.budget_system`及其他budget分组 | 单角参考、系统目标、硬件假设，部分角边界由目标派生 |

所以目前没有独立tx.yaml/rx.yaml。代码层共享不要求不同参考面的能量、角域或硬件假设具有相同数值。后续建议在defaults.yaml内部组织domains并只保留实验差异；尚未迁移，不能把建议字段当成可导入配置。

## 浏览器输入与用户方案

页面先取得初始值，再可能恢复草稿/历史任务或合并导入内容。浏览器草稿的完整字段可能覆盖新初始值；普通刷新不应悄悄替换用户输入，使用页面“恢复默认”或新建工况后再采集。

| 平台 | 保存机制 |
|---|---|
| A | 当前表单在内存；切换评估/调试使用sessionStorage的lidar-config；localStorage的lidar-a-job主要保存最后任务ID |
| 独立SPAD | localStorage：lidar-experiment-v2-spad |
| B | localStorage：spad-system-modular-v3 |
| 正式C | localStorage：spad-columns-v4；B→C临时转移使用sessionStorage |
| 预算 | localStorage：spad-hardware-budget-v1，含草稿与比较基准 |

存储按浏览器Profile和页面来源隔离。当前没有独立的服务端用户默认方案库；显式导入/导出可保存完整工况。网页编辑和导入不会写回项目defaults.yaml。

## 提交、结果与文件

提交采集后，JobManager冻结实际工况、算法和整份YAML，写入每任务request.json；worker完成后写result.json，状态/进度保存SQLite，错误可有error.txt。参数预览不等于采集。位置、保留及恢复细节只维护在[运行数据](run-artifacts.md)。

系统预算calculate为同步请求，不自动创建采集作业或result.json；结果先在浏览器显示与比较，点击导出后成为用户下载文件。原始CSV/JSON留在用户选择的位置；解析的数据可进入草稿和任务快照，但没有自动收集原件附件库。

后台任务不追随后续默认值变化，重放不能改变PDE、死时间或恢复量化精度。schema_version描述配置格式，不是A/B/C范围或软件版本。
''',
'docs/guides/debug-guide.md':'''# A 评估与专家调试指南（现行）

更新：2026-10-18。适用`/`和`/debug`，二者共享配置与计算，调试视图增加审计，不构成第二套模型。启动地址以[启动器](launcher.md)输出为准，不沿用早期手册端口。

## 使用顺序

1. 载入初始值、导入工况或恢复历史任务；来源和覆盖见[配置与数据归属](configuration-and-data.md)。
2. 确认单角通道能量、IFOV、谱输入、器件与读出、门和统计次数。A不自动获得B的二维PSF或C扫描语义。
3. 提交后台采集，观察任务进度；取消在求解安全边界确认。下方历史结果不因编辑表单而改变。
4. 同时核对首次观测、解析GT、噪声参考、MC范围和原始测距，含义见[直方图指南](histogram-display.md)。
5. 导出配置、直方图或调试JSON，核对configuration、版本、时间、seed、指纹、中间预算与模型限制。

## 需要明确的边界

- A事件模式每份采集从完全恢复状态开始，无预热；同份内跨发状态连续。analytic_reference为另一条理想解析路径。
- 测距统计、含信号均值、纯噪声均值是不同计数角色；次数来自工况，不从旧手册示例推断。
- 常规界面已停用检测门限/Pd/PFA；原始峰或距离不等于已标定成功检出。显式历史API仍兼容，算法参考见[兼容检测说明](../references/legacy-detection-performance.md)。
- 候选雪崩、最终混合记录、解析GT与独立噪声参考不可混用；PSF分配不等于事件级雪崩串扰。

## 物理与源码入口

公式、参考面及单位只引用[光子预算](../models/photon-budget.md)、[谱与背景](../models/spectral-background.md)、[A噪声](../models/noise-model.md)和[读出模式](../models/readout-modes.md)，不在本手册维护旧公式副本。

当前A用例为experiments/single_channel.py；单角预算为rx/budget.py；事件源为experiments/a_acquisition.py，经a_router调用spad状态核心。simulator.py、readout.py等仍为兼容导出。

早期解析推导、旧端口和历史检测说明已保存在[旧调试手册](../history/debug-guide-through-v0.2.md)，不作为当前操作说明。
''',
'docs/guides/histogram-display.md':'''# 直方图、参考线与统计（现行）

更新：2026-10-18。此页维护图层与统计语义；布局和1080P/缩放适配规则见[UI规范](../design/ui-design-guidelines.md)。默认次数及其继承只看[配置说明](configuration-and-data.md)和实际工况。

## 各图层是什么意思

| 图层 | 含义 | 不表示什么 |
|---|---|---|
| 首次蓝色观测 | 一份实际含噪数字采集 | 不取多次平均 |
| 浅蓝MC范围 | 各bin在保存的独立重复中取最小/最大；包含首次观测 | 不是置信区间或理论保证范围 |
| 青色纯信号GT | Python共同数值核心的解析参考，含确定性的配置时域展宽 | 不含背景、随机抽样、死时间、逻辑竞争及读出容量损失 |
| A橙色噪声参考 | 独立纯噪声采集均值 | 不等于混合记录中可相减的精确噪声分量 |
| B默认橙色参考 | 候选噪声率按正式曝光和标准bin宽得到解析标量 | 未计数字读出竞争，不是输出噪声均值 |
| 历史B / C噪声层 | 以保存的算法协议和实际噪声样本为准 | 未保存时不补造 |

改变seed、背景或读出模式不应改变同一纯信号解析GT；改变光学、PDE/FF、门、波形或抖动定义可能改变它。各模型的输入参考面仍需对齐。

## 统计角色与初始化

A的monte_carlo_trials、readout_mean_trials、noise_mean_trials分别控制测距/范围、含信号均值与纯噪声均值。每份独立采集新建完全恢复的状态，无预热；同份多发保持死时间连续。

B的首次观测包含在完整重复中；当前默认候选标量参考不额外执行关激光采集，历史sampled_output_mean按原快照显示。独立B的初始条件由保存的b_initial_condition定义。不能用当前默认值解释旧任务。

正式C保存显式trial_count/noise_trial_count对应的完整扫描记录和seed。选列/通道及合法重分箱后再计算范围、噪声均值与测距样本统计；C仍跨列连续，不等于列间复位。单次观测或零次噪声没有伪造误差棒/期望线。

## 观察与重放

时间窗口拖动、缩放、精确输入只改变显示，不重新采集、不改变原数组或寻峰范围。硬件TDC量化与观察分箱分开；重放只能取原bin宽整数倍并保持门原点，先对各次采集重分箱再计算最小/最大，不能简单相加旧范围。

清空、非有限、反向或越界观察范围须明确报错，保留上一有效视窗。当前参数预览与历史结果分开；导出须注明原始采集、显示范围与处理bin。

旧24/40、10/10/10及历史预热示例是当时工况，不是当前默认。原说明完整保留于[历史图表指南](../history/histogram-guide-before-20261018.md)。
''',
'docs/design/column-accumulation-design.md':'''# C 列内累积与列间复位：确认意图及实现差距

更新：2026-10-18。此页维护已确认机制边界；旧B失败诊断、历史默认次数和优化讨论已归档至[原讨论](../history/column-accumulation-discussion-20260925.md)。实际完成状态以[路标](../roadmap.md)及[人工验收](../validation/c-manual-review.md)为准。

## 已确认意图

- 一个slot对应输出点云一列，同列读出通道参与共同列计划；累计发数为同一列内的曝光次数。
- 各次曝光以自己的Tx触发参考写相对ToF直方图；同列曝光之间允许门重开，器件死时间继续。
- 列末要求完全复位，位于两个slot之间，复位耗时额外计入帧时间；不能猜为零。
- 复位不清除已锁存的上一列输出，也不能删除已在传播的光子；门关闭、器件状态、TDC/逻辑、直方图和输出缓冲需明确区分。

## 当前实现与待补部分

| 机制 | 状态 |
|---|---|
| 逐发时间/能量、门并集/碎片、跨列尾部与列归属 | 正式列级C已有模型实现，见[列级扫描](../models/column-scanning.md) |
| 同次扫描内SPAD/TDC状态 | 当前跨列连续；后台第一阶段提取未改变它 |
| 列间完全复位及其耗时 | 尚未接入，需要明确作用状态、时刻、回扫/帧末关系和验收 |
| 芯片内直方图计数饱和、写入、锁存/读出资源 | 尚未完整模拟；主要由事件记录重建直方图，位宽预算不能冒充计数器行为 |
| 输出双缓冲、DSP/MIPI | C与预算模型保持分开；预算固定角色A/B不自动成为C的复位架构 |

A无预热、B独立实验完全恢复，均不能证明C列间复位已实现。B统计次数及噪声参考已经由当前公共工况/算法定义，此页不维护旧“默认10次”等数值副本。
'''
}
for name,text in documents.items():
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8',newline='\n')
print('Rewrote current architecture and four current guides/design notes; added configuration/data guide.')
