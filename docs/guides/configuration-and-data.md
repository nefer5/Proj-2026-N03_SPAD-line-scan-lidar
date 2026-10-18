# 配置、默认值与用户数据归属（现行）

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

## 当前默认值结构与继承

`config/defaults.yaml`使用内部布局schema 2。公共领域和平台差异在同一个文件内分组，避免tx.yaml/rx.yaml再复制一套工况。以下结构已实施；参数类型、单位与含义沿用现有工况协议。

```text
config/defaults.yaml
├── schema_version: 2
├── domains/
│   ├── tx/、scene/、rx/          公共光学；Tx全角域与Rx接收域各自独立
│   ├── spad/、readout/           器件、阵列与数字读出
│   ├── background/              环境光开关与强度
│   ├── acquisition/             PRF、门控、统计次数、seed与扫描帧数
│   ├── spectral_inputs/         filter/solar/other/pde，CSV与手动点分别保留
│   ├── motion/、scene_motion/   共用运动与场景运动参数
│   └── system_targets/          C与预算共用的系统目标
└── experiments/
    ├── a/                       单角能量、IFOV、A统计与历史串扰展示
    ├── spad/                    探测面直接照明
    ├── system/                  B显式差异（空映射表示全继承）
    ├── scan/                    历史周期扫描的专用计划参数
    ├── columns/                 C列级采集、曝光、输出与诊断
    ├── budget/                  预算专用覆盖和硬件假设
    └── scan_demo/               仅显式载入的示例覆盖
```

| 平台 | 组合方式 | 保留独立的含义 |
|---|---|---|
| A | 公共领域中适用字段→experiments.a，映射成原有平面工况 | 当前角通道Tx前能量、独立IFOV、统计与历史展示 |
| 独立SPAD | 公共器件/读出/时序/PDE/波形→experiments.spad | 探测面直照强度，无整机Tx/Rx |
| B | 公共Tx/场景/Rx/SPAD/背景/采集/曲线→experiments.system | 全Tx角域与静态空间模型 |
| C | B公共光学与差异→公共运动/帧数/系统目标→experiments.columns | 逐发曝光、列级采集与输出；不先构造历史周期扫描计划 |
| 预算 | B公共光学与差异→公共系统目标→experiments.budget | system下的均匀场、阵列、功率等专用覆盖，及assumptions/transport/geometry/rx_channel/electrical/range_reference |
| 历史扫描 | 公共光学/运动/帧数→experiments.scan | 旧帧率、机械端点、角bin等计划定义；不能替代C系统目标 |

`domains.tx.pulse_average_power_w`是B/C全Tx角域功率，A的`experiments.a.tx.pulse_energy_nj`是当前角通道能量，参考范围不同，继续独立。A的IFOV不由B阵列binning推导。周期视图的period_ns从公共laser_prf_hz按单位关系派生；C的列内逐发时刻仍由曝光列表定义，不把周期标量当成列级时钟。

默认组合与字段来源由`default_composition.py`共同维护，文件版本/布局与历史路径适配由`default_layout.py`维护。读取、预览和写回使用同一来源表；`configuration.default_values()`只是A旧平面接口的适配结果，不是另一份默认存储。B公共类型在`domains/optical_system.py`；旧模块路径保留兼容导出。

## 文件版本与旧任务兼容

内部defaults.yaml的schema 2与网页导入/导出工况的schema_version是不同协议。本轮不改变各平台工况字段、公开schema或旧任务版本。schema 1的YAML任务快照和恢复备份仍可读取，通过显式版本适配定位原始字段；不会自动重写历史任务或用户备份。

`python scripts/migrate-default-layout.py --check`检查现行布局。恢复schema 1备份后可继续读取/保存，也可用`--write`显式迁移：先逐平台校验迁移前后配置一致，备份原字节和摘要，再原子替换。迁移备份位于`artifacts/default-layout-migrations/`。不要仅改schema_version数字冒充迁移；缺失/未知分组或字段直接报错。

## 浏览器输入与用户方案

页面先取得初始值，再可能恢复草稿/历史任务或合并导入内容。浏览器草稿的完整字段可能覆盖新初始值；普通刷新不应悄悄替换用户输入，使用页面“恢复默认”或新建工况后再采集。

| 平台 | 保存机制 |
|---|---|
| A | 当前表单在内存；切换评估/调试使用sessionStorage的lidar-config；localStorage的lidar-a-job主要保存最后任务ID |
| 独立SPAD | localStorage：lidar-experiment-v2-spad |
| B | localStorage：spad-system-modular-v3 |
| 正式C | localStorage：spad-columns-v4；B→C临时转移使用sessionStorage |
| 预算 | localStorage：spad-hardware-budget-v1，含草稿与比较基准 |

存储按浏览器Profile和页面来源隔离。当前没有独立的服务端用户默认方案库；显式导入/导出可保存完整工况。普通网页编辑和导入不写回项目defaults.yaml；只有明确执行下节的“设为默认”会修改项目初始值。

## 将本页参数设为项目默认

A（含调试视图）、独立SPAD、B、C和系统预算的“恢复默认”旁提供“设为默认”。调整参数后点击，审查参数旧值、新值、YAML归属及受影响平台，再点击“确认写入默认配置”。取消或校验失败均不写入。

- 仅写入本次变化的输入，按现有继承链找到最后实际定义该字段的位置。共同场景/器件/读出和Tx/Rx默认写入`domains`，已有平台差异则写回实际覆盖分组；C专用曝光/采集参数与预算专用覆盖继续留在各自分组。时序周期按单位关系写回共有PRF。
- 预算角边界继续从VFOV、通道数和Rx宽度派生；不会把派生边界存成第二套默认。预算专用功率/阵列等覆盖保持独立，修改B的继承源不强行覆盖预算专用值。
- 保存前重新解析所有平台默认并严格校验；若共享修改导致其他平台配置非法，显示错误并拒绝整次写入。可在审查窗口看到实际受影响的平台；这不是“仅当前浏览器”的个人偏好。
- 后端先将原文件逐字节备份到`artifacts/defaults-backups/<时间和唯一ID>/defaults.yaml`，并保存含来源、配置版本和前后SHA256的`receipt.json`，再通过同卷原子替换写入固定的`config/defaults.yaml`。未修改的YAML内容和注释保留。
- 预览携带整套YAML的内容指纹；保存时指纹变化则拒绝覆盖，需重新预览。并行网页保存使用进程间锁。人工外部编辑文件仍应避免与保存同时进行。
- 写入成功后，后续请求立即读取新默认。已打开表单与浏览器草稿不自动刷新，请点击“恢复默认”；已有任务继续使用冻结快照。需要恢复原值时，可将备份覆盖回`config/defaults.yaml`后重新加载默认。

实现入口：`default_store.py`处理归属、校验、备份和写入；`webapi/defaults.py`提供`POST /api/defaults/{kind}/preview`与`/save`，其中kind为a/spad/system/columns/budget（兼容scan）；公共前端`shared/defaults.js`处理审查与确认。工况默认值仍只维护一份，没有新增用户默认数据库，也不修改算法配置。

## 提交、结果与文件

提交采集后，JobManager冻结实际工况、算法和整份YAML，写入每任务request.json；worker完成后写result.json，状态/进度保存SQLite，错误可有error.txt。参数预览不等于采集。位置、保留及恢复细节只维护在[运行数据](run-artifacts.md)。

系统预算calculate为同步请求，不自动创建采集作业或result.json；结果先在浏览器显示与比较，点击导出后成为用户下载文件。原始CSV/JSON留在用户选择的位置；解析的数据可进入草稿和任务快照，但没有自动收集原件附件库。

后台任务不追随后续默认值变化，重放不能改变PDE、死时间或恢复量化精度。schema_version描述配置格式，不是A/B/C范围或软件版本。
