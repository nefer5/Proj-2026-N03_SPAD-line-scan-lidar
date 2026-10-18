"""Append phase facts while preserving the existing launcher/responsive edits."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def append(path,heading,text):
    p=ROOT/path;data=p.read_bytes()
    if heading.encode() in data:raise RuntimeError('Already documented: '+heading)
    p.write_bytes(data+b'\n\n'+(heading+'\n\n'+text+'\n').encode('utf8'))

append('docs/design/architecture.md','## 2026-10-18：后台结构重构第一阶段',
'''本阶段按已讨论方案开始提取公共职责；五个平台、接口、配置格式与当前数值协议保留。三个工作台属于后续前端整合方案，尚未实施，2026-10-18已有的桌面/1080P适配不随本阶段重做。

- `domains/acquisition.py`：周期时序字段；`domains/optical.py`：统一光学字段与平铺兼容视图；`domains/system.py`：Tx/场景/Rx/阵列/背景/采集域类型。只定义类型与约束，不引入默认值。原实验模块保留同对象兼容导出。
- `optics/service.py`：接管`optical_dataset`与`project_illumination`；B、C、预算和相关HTTP/参数预览直接调用该入口。该层不导入experiments、reporting或网页/任务层；背景每bin数值移至`processing/background.py`，展示层保留兼容导出。
- `acquisition/trials.py`与`executor.py`：表达已有观测/重复/含信号均值/噪声角色和显式次数，按顺序逐次执行；不生成seed、不预取下一次、不新增取消点、不改初始化策略。A/B/C继续在各适配器中保留原随机分流、计数与资源检查。
- `acquisition/adapters/periodic.py`：接管SPAD/B/历史C的周期量化与直方图；原`experiments.lab.acquire_candidates`仍导出同一函数。列级C量化及门碎片保持独立；底层`spad/acquisition.py`仍是原状态核心。

`BSystemConfig`与`ColumnConfig`的外部schema、C对B配置的继承、预算嵌套B配置目前保留；本阶段提取字段唯一源，不声称已完成整个领域组合迁移。两种DSP/MIPI调度、A解析参考、历史C及核心检查点行为保留。

回退点、完整数值/配置等价证据与保护检查见[第一阶段验证](../../artifacts/refactor-phase1-20261018-170544/validation.json)。原Archify分析页是a19f273的历史源码快照，不能用它的行号判断本阶段新文件。''')

append('docs/design/architecture-decisions.md','## 2026-10-18：启动后台重构，前端统一后置',
'''用户授权：在没有待审模型问题时可开始重构；明确提醒保留另一聊天窗口已做的1080P适配，五个平台前端设计语言最后再统一。本轮选择保持行为的后台提取，不改变当前前端、默认值、随机协议、能量参考面和旧配置/API。

先提取公共领域字段、光学服务与重复采集编排，保留旧模块兼容导出及专用输入/记录适配。细节和实际实施边界唯一维护在[架构第一阶段](architecture.md#2026-10-18后台结构重构第一阶段)。完整三工作台方案仍未全部实施。

后续需要单独设计/验收的行为：C列间完全复位、A与B退化等价范围、C与预算调度模型合并、统计口径/RNG变化及真实前端工作流改版。本阶段不以结构调整替代这些决策。''')

append('docs/roadmap.md','## 2026-10-18：后台重构第一阶段进度',
'''已开始实施公共领域字段、独立光学服务、周期记录适配器和TrialPlan/顺序执行器，实际边界见[架构](design/architecture.md#2026-10-18后台结构重构第一阶段)。原模块兼容导出保留，外部参数/schema和数值协议对照验证；证据见[第一阶段验证](../artifacts/refactor-phase1-20261018-170544/validation.json)。

R03/R04没有整体完成：C/预算配置组合、平台参数语义与命名的系统审计仍待；R05按用户指示最后处理，当前桌面/1080P适配保留。三工作台、C列间复位、两种输出调度合并及C人工精细验收均不由本轮标记完成。''')

append('docs/release-notes.md','## 2026-10-18 后台结构提取（工作树增量）',
'''提取domains字段唯一源、optics公共光学服务、acquisition周期记录适配与TrialPlan/顺序执行；旧实验导入保持同对象兼容。光学计算与背景每bin数值不再由实验/展示模块持有。保留既有1080P前端改动、所有YAML、SPAD/读出状态核心、配置schema与API；未合并C/预算调度或实施C列间复位。

实施定义见[架构](design/architecture.md#2026-10-18后台结构重构第一阶段)，回退/数值/测试/保护证据见[第一阶段验证](../artifacts/refactor-phase1-20261018-170544/validation.json)。软件版本继续0.6.14.dev0，尚未发布。''')
print('Updated architecture, decisions, roadmap and release notes without replacing earlier entries.')
