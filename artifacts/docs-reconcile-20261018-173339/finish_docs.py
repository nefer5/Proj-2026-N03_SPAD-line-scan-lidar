from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
def edit(path,fn):
    p=ROOT/path;s=p.read_text(encoding='utf8');out=fn(s)
    if out!=s:p.write_text(out,encoding='utf8',newline='\n')

edit('docs/models/spatial-optics.md',lambda s:re.sub(r'默认B/C阵列为[^\n]+',
 '读出通道行列数与通道内H/V分组分别定义：像素宽为channels_h×H_binning，像素高为channels_v×V_binning。当前初始数值、波形、环境开关和统计次数均从[配置说明](../guides/configuration-and-data.md)所列YAML加载，不沿用早期示例中的阵列/发数/重复次数。B/C的Tx输入覆盖配置的全角域，A仍为当前单角通道能量；不能只因复用核心就交换两种输入。光学宽度和双轴定义见[空间模型](spatial-profiles.md)。独立B初始条件和噪声参考按保存的算法定义，当前完全恢复/解析候选标量路径不等于C列间复位；强背景超限明确报错，不自动降低工况。',s,count=1))
edit('docs/models/spatial-optics.md',lambda s:s+'\n## 当前实现归属\n\n公共光学投影与数据装配已移至`optics/service.py`，字段类型来自`domains/`；`experiments/spatial.py`保留用例与兼容导出，B重复分析仍由`experiments/spatial_analysis.py`组织，公共重复执行在`acquisition/`。结构权威见[架构](../design/architecture.md)，此处不另维护目录副本。\n')

def columns(s):
    s=re.sub(r'高层默认值只定义于[^\n]+','高层初始值只定义于`config/defaults.yaml → experiments.system_targets`；Python共同核心生成帧周期、可分配扫描时间、每列目标和均匀角格参考，前端没有另一套预算公式。实际值以当前工况/任务快照为准，不沿用早期文档示例。',s,count=1)
    s=s.replace('H×V默认2×16；V表示线数','读出通道H/V与通道内H_binning/V_binning分开定义；读出通道V表示线数')
    s=s.replace('光学背景仍假定Rx局部角域内均匀平稳，但积分网格目前沿用Tx角域，不能视为完整Rx视场背景。Rx收光域与Tx照明域的独立建模是R01明确待办；没有臆造天空/场景纹理。','光学背景仍假定Rx局部角域内均匀平稳。当前independent_rx按显式Rx角域积分，旧算法快照可保留legacy_tx；没有臆造天空/场景纹理。独立接收域已有模型实现与自验，但配置域不等于实物完整视场，R01的实物域确认和人工验收仍待。')
    s=s.replace('16线阵列不会自动扩大','增加阵列线数不会自动扩大')
    s=s.replace('- `scan/planning.py`：','- `optics/service.py`、`domains/`：公共光学投影与字段类型；`acquisition/`维护重复计划及共用适配，列级量化仍保持专用。\n- `scan/planning.py`：',1)
    return s
edit('docs/models/column-scanning.md',columns)
edit('docs/models/noise-model.md',lambda s:s.replace('核心入口为 `simulator.py:photon_budget`、`spectra.py:spectral_components`、`readout.py:event_histogram/route_events`。','当前主要实现为`rx/budget.py:photon_budget`、`spectra.py:spectral_components`、`experiments/a_acquisition.py`及公共spad核心；simulator.py/readout.py保留兼容导出。').replace('当前增加了独立无目标样本校准的全门检测门限，未过门限返回“未检出”；原始寻峰距离保留供审计。门限关闭时仍是旧版无检测判定的质心结果。','常规A界面已停用检测门限/Pd/PFA，默认输出原始寻峰与测距统计。显式历史API启用检测时才执行独立无目标校准及阈值判定，原始距离保留供审计。').replace('见detection-performance.md。','兼容算法见[历史检测说明](../references/legacy-detection-performance.md)。').replace('后续优先级见 [A版审视与优化建议](../history/a-review.md)。','当前后续优先级见[路标](../roadmap.md)；[早期A审视](../history/a-review.md)只作历史依据。'))
edit('docs/models/readout-modes.md',lambda s:s.replace('# A版数字SPAD读出模式','# 数字SPAD读出模式与初始化',1).replace('本轮实现7类可参数化数字dToF架构，外加1个理想解析参考。','公共事件核心支持7类可参数化数字dToF架构；A另有理想解析参考，SPAD/B/C事件采集不使用该解析模式。',1))
edit('docs/design/architecture-decisions.md',lambda s:s.replace('整理日期：2026-09-25；当前实现0.6.3.dev0。依据本项目历次讨论和实际界面审核。这里只记录项目约定，不修改全局规则。','初次整理：2026-09-25；持续记录项目决策及演进，不修改全局规则。正文中的日期、数值和测试数量属于对应阶段；当前默认只以YAML为准，结构见[现行架构](architecture.md)，实现/验收状态见[路标](../roadmap.md)。后续已确认的决定可替代早期记录，不把历史叙述当成并行规范。',1))
edit('docs/design/spad-data-timing-design.md',lambda s:s.split('\n',1)[0]+'\n\n> 现行系统预算的资源机制契约；不自动适用于正式C的transport。下文v5/v6/v7迁移及自验为对应阶段记录，示例数值不构成默认源；当前字段/值以类型、YAML与[系统预算指南](../guides/system-budget.md)为准。\n'+s.split('\n',1)[1])
edit('docs/roadmap.md',lambda s:s.replace('更新：2026-10-15；','更新：2026-10-18；',1).replace('详细讨论与历史诊断保留在[列内累积和复位](design/column-accumulation-design.md)','已确认边界和历史诊断入口见[列内累积和复位](design/column-accumulation-design.md)'))
edit('docs/release-notes.md',lambda s:s.split('\n',1)[0]+'\n\n> 本页是按版本/日期保留的演进记录，包含历史默认、端口及当时测试数量；不是当前操作或参数规范。现行入口见[文档目录](index.md)，最新实现与人工验收状态见[路标](roadmap.md)。\n'+s.split('\n',1)[1])

index='''# 项目文档导航（现行）

更新：2026-10-18；研究版本0.6.14.dev0。先读现行说明，再按需查兼容参考或历史。文档示例和历史数值不构成第二份运行默认。

## 先读这些权威入口

| 内容 | 唯一维护入口 | 说明 |
|---|---|---|
| 安装与启动 | [项目首页](../README.md)、[启动器指南](guides/launcher.md) | 使用地址以启动器输出为准 |
| 当前结构与模块职责 | [C4架构说明](design/architecture.md) | C1系统、C2应用/存储、C3组件；已反映后台第一阶段 |
| 初始默认、覆盖和用户数据 | [配置与数据归属](guides/configuration-and-data.md) | 实际类型/数值分别在Python/YAML，网页草稿不写回默认 |
| 已确认的取舍与演进 | [架构决策](design/architecture-decisions.md) | 决策正文按日期保留，不把旧数值当当前默认 |
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
'''
(ROOT/'docs/index.md').write_text(index,encoding='utf8',newline='\n')

def readme(s):
    if '## 系统预算入口（2026-09-28）' in s:s=s.split('## 系统预算入口（2026-09-28）')[0].rstrip()+'\n'
    s=s.replace('| 规范与当前状态 |','| 当前架构 | [C4现行架构](docs/design/architecture.md)、[四页离线说明](artifacts/c4-architecture-20261018-172542/index.html) |\n| 参数和用户数据归属 | [初始值/草稿/覆盖/结果](docs/guides/configuration-and-data.md) |\n| 规范与当前状态 |',1)
    return s+'\n文档按当前说明、兼容参考、历史归档分开；[文档目录](docs/index.md)为统一导航，旧报告中的默认数值和架构快照不自动成为现行规范。\n'
edit('README.md',readme)
edit('AGENTS.md',lambda s:s.replace('## 公式书写与渲染约定','- 当前架构按C4的C1–C3维护在`docs/design/architecture.md`；参数默认/用户数据归属在`docs/guides/configuration-and-data.md`，实现与验收只以`docs/roadmap.md`为状态入口。references/history分别是参考/历史，旧记录不能覆盖现行定义。\n- HTML架构页属于artifacts中的带时间快照，必须标明来源、已实现/建议及快照边界；不能当作第二套持续维护的规范或实时目录。归档/迁移文档须同步导航、相对链接和生成/校验入口，保留可追溯原件。\n\n## 公式书写与渲染约定',1))
history=ROOT/'docs/history';rows=[]
for p in sorted(history.glob('*.md')):
    if p.name=='README.md':continue
    title=next((line.lstrip('# ') for line in p.read_text(encoding='utf8').splitlines() if line.startswith('# ')),p.stem)
    rows.append(f'- [{title}]({p.name})')
(history/'README.md').write_text('# 历史归档索引\n\n这里保留当时的设计、诊断、默认示例、端口和验证结果，不作为当前实现/规则来源。现行结构见[架构](../design/architecture.md)，当前能力和待验见[路标](../roadmap.md)，全部导航见[文档目录](../index.md)。\n\n'+ '\n'.join(rows)+'\n\n旧的[十页架构分析](../../artifacts/architecture-review/20261018-032102/index.html)和[最早运行/核心两图](../../artifacts/architecture-review/20261014-213640/runtime.html)均为固定旧快照。新[四页C4说明](../../artifacts/c4-architecture-20261018-172542/index.html)是后台第一阶段后的导出，仍需按其时间阅读。\n',encoding='utf8',newline='\n')
print('Updated navigation, current model scopes, local authority rules and historical entry boundaries.')
