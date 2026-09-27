# 项目文档目录

当前研究版本：0.6.3.dev0。先读当前说明，再按需回溯历史设计；文档中的示例数值不构成另一份运行默认值。

## 目录分类

根目录只保留本索引、路标和版本记录，正文按用途分一层目录。

| 目录 | 放什么 | 维护边界 |
|---|---|---|
| `design/` | 架构、已确认需求与偏好、UI规范、机制设计 | 区分已确认设计和已实现行为 |
| `models/` | 物理模型、数值定义、数据契约、模型限制 | 对应共享Python核心与配置；生成文档从共享定义更新 |
| `guides/` | 调试、图表阅读、数据保存和复现 | 面向使用操作，引用模型定义，不另立公式 |
| `validation/` | 人工验收清单与审核模板 | 逐项记录通过、待验、失败；自动测试不代替人工结论 |
| `references/` | 器件参数来源、文献条件与适用范围 | 原始数据/PDF索引留在 `data/reference/` |
| `history/` | 旧设计草案、阶段复查与历史版本记录 | 保留当时结论，当前状态以路标和现行文档为准 |

运行产物、报告、截图和验收快照统一留在仓库根目录 `artifacts/`，不混入 `docs/`。新增文档先选分类并更新本索引；移动时同步相对链接、代码/配置说明中的路径和生成/校验脚本。公式校验递归覆盖子目录。

## 当前入口与边界

- [系统预算](guides/system-budget.md)：确定性硬件预算、单方案与基准比较；复用B光学和C高层时间预算，保留未知参数与模型边界。

- [项目首页](../README.md)：安装、启动、各平台入口、当前能力与主要限制。
- [路标](roadmap.md)：A/SPAD/B/C已实现内容、用户已确认但尚未实现的机制、后续优先项。
- [版本记录](release-notes.md)：近期功能演进与发布验证。
- [C人工精细验收](validation/c-manual-review.md)：待用户复查的逐项记录模板。
- [运行数据与复现](guides/run-artifacts.md)：任务文件、Git范围、备份及报告口径。

## 已确认的设计与偏好

- [架构决策与偏好](design/architecture-decisions.md)：历次讨论结论及实现状态。
- [模块架构与契约](design/architecture.md)：依赖方向、输入输出、配置与随机数边界。
- [界面设计规范](design/ui-design-guidelines.md)：参数组织、图表、交互、术语、审核与验收。
- [列内累积与复位讨论](design/column-accumulation-design.md)：用户确认的硬件边界、历史诊断及待实现事项。
- [项目约束](../AGENTS.md)：简短强约束；细节通过上述文档按需查阅。

## 使用与物理模型

| 主题 | 文档 |
|---|---|
| B全光斑与数据接口 | [空间光学](models/spatial-optics.md) |
| H/V高斯、超高斯及宽度 | [双轴空间模型](models/spatial-profiles.md) |
| 正式C列级工作台 | [列级扫描](models/column-scanning.md) |
| 历史周期C | [扫描机制](models/scanning.md) |
| 统一光谱与带外透过率 | [曲线输入](models/curve-inputs.md)、[光谱与背景](models/spectral-background.md) |
| 计数、参考面与公式 | [光子预算](models/photon-budget.md)、[A噪声模型](models/noise-model.md) |
| 观测、理想曲线及误差棒 | [直方图](guides/histogram-display.md) |
| 器件和电子读出 | [读出模式](models/readout-modes.md)、[H/V分组](models/binning.md) |
| A检测与性能指标 | [检测与扫参](models/detection-performance.md)、[调试手册](guides/debug-guide.md) |
| 参数资料来源 | [PDE文献](references/pde-literature.md)、[Sony参考](references/sony-reference.md)、[论文索引](../data/reference/papers/README.md) |

`photon-budget.md`、`spatial-profiles.md`由共享定义生成，修改源YAML后运行对应生成脚本和`--check`；不要手工维护含义不同的公式副本。

## 历史设计与证据

- [早期模型设计](history/model-design.md)：保留研究依据与NPZ/HDF5等草案，实际接口以当前架构和B文档为准。
- [C界面设计草案](history/c-exposure-workspace-design.md)、[0.6.0实施记录](history/c-implementation-progress.md)：当时的设计、验证和未完成项，不自动代表当前状态。
- [A审视记录](history/a-review.md)、[历史README](history/readme-through-0.6.0.md)：保留早期问题及版本说明。
- 近期验收入口：[采集范围](../artifacts/b-acquisition-scopes/README.md)、[Tx归一化](../artifacts/tx-domain-normalization/README.md)、[直方图核验](../artifacts/histogram-display-audit/README.md)、[双轴光学](../artifacts/optical-shapes/README.md)、[带外漏光](../artifacts/filter-leakage/README.md)、[A/B背景差异](../artifacts/b-noise-audit/README.md)。部分原始数组仅保存在本机运行目录，报告会注明。
