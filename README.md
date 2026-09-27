# SPAD 线扫 LiDAR 建模器

当前研究版本 **0.6.4.dev0**：独立SPAD研究、B空间光学、C列级扫描共用同一Python器件与读出核心。网页负责配置、绘图和审计；构造光学/扫描样例不代表实测整机。

## 启动与入口

首次在项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

之后双击根目录 `start-dev.cmd`，或执行 `.\.venv\Scripts\python.exe run.py --reload --open`。默认端口由 `run.py` 统一维护为8016。启动脚本优先使用项目虚拟环境，未创建时使用PATH中的Python；后者也须已安装项目依赖。

| 入口 | 适用研究 |
|---|---|
| [独立SPAD](http://127.0.0.1:8016/spad) | 直接输入探测面照明，研究器件、门控与读出，无需设置整机光学 |
| [B空间光学](http://127.0.0.1:8016/system) | Tx角分布、场景、Rx效率/PSF、物理像素与通道采集 |
| [C列级扫描](http://127.0.0.1:8016/system/scan) | 系统目标、列内逐发时间/能量、转镜、返回角、DSP/MIPI资源规划 |
| [A评估](http://127.0.0.1:8016/) / [A调试](http://127.0.0.1:8016/debug) | 保留单角通道模型的两种视图及数值基线 |
| [历史周期C](http://127.0.0.1:8016/system/scan/legacy) | 查看旧周期扫描任务；不将其冒充正式列级C |

首次启动服务时保留原命令窗口，按Ctrl+C停止。已有同名服务时再次双击只打开网页，新窗口可以退出，不表示原服务停止。关闭网页不会停止服务。Python源码在开发模式下自动重载；HTML/CSS/JS通过内容指纹和禁用缓存支持普通刷新。修改启动器或安装依赖后需要重启原服务。

## 当前能力与使用原则

- **统一核心**：PDE/FF、DCR、抖动、SPAD恢复、TDC/容量/符合等机制在公共核心中实现，A/B/C不维护不同版本。
- **B光学**：Tx高斯/超高斯/均匀/导入分布；Rx双轴高斯/超高斯/均匀参考/导入响应。新配置使用倒置成像，H/V参数成组，PSF独立参数图与通道投影图分开。
- **Tx能量口径**：B/C输入是配置Tx角域内、Tx光学前的完整单发能量，域内份额归一化。Tx效率仍计入，Rx像面损失和时间门损失仍分别保留。
- **光谱与带外漏光**：四种基础滤光片都可配置带外透过率；非零时覆盖提供的源光谱，并明确受导入Rx已知波段约束。构造无色差Rx使用精确外积分解降低存储与计算量。
- **统计口径**：N是一次采集中的累计发数，M是独立重复次数。B蓝柱取首次采集，误差棒比较M份样本；单gate显示真实记录，不用slot结果除N代替。
- **直方图**：青色参考位于PDE/FF之后、死时间与读出损失之前；虚线密度与分箱积分点不同。整数纵轴支持全门固定或局部自适应，观察窗口可拖动也可精确输入。
- **背景计量**：太阳/其他光每time_bin值是候选率直接乘bin时长，不做额外随机统计。B/C按全阵列汇总；通道和像素分配并不均匀。
- **C工作台**：一个slot对应点云一列，线阵并行；逐发列表允许不同时间与能量。高层下发T_slot目标，HFOV以deg输入；DSP之后通过MIPI输出，支持双缓冲流水。

参数草稿、当前预览、历史采集和记录重放分别标记。修改物理参数后须提交新任务；只改变通道选择、观察窗口或合法重放分箱不会改写原记录。

## 必须一起理解的模型边界

1. **Rx接收域需按实物确认。** 背景已按独立Rx域积分，与Tx归一化域分开；域外设为不接收，不能把有限配置域等同于已实测的整机环境视场。
2. **C列间完全复位与复位开销尚未实现。** 用户已确认“列末完全复位、置于列间、额外计入帧时间”，当前C仍保持跨列连续器件状态，不能将示意图当成实现。
3. C直方图主要由事件重建，芯片累积器写入吞吐、计数饱和和锁存约束未完整建模；带宽位宽目前是负载预算。
4. 扫描光学按脉冲/回波中心姿态计算，未解析长尾期间的连续扫描拖影。B/C距离与点云为原始估计，没有专用Pd/PFA标定。
5. 未实现afterpulse、事件级雪崩串扰、温度/过压联动；PSF通道比值不等于器件串扰。

强背景完整帧可能超过资源限额。可显式选局部列实验，或载入具名快速示例；程序不静默关光、减少发数或降低采样来绕过限制。

## 配置、结果与文档

| 内容 | 唯一来源 / 入口 |
|---|---|
| 工况默认值 | `config/defaults.yaml`，网页“恢复默认”重新加载 |
| 算法、采样策略、资源限额 | `config/algorithms.yaml` |
| 参数说明与输入模式 | `config/parameter-help.yaml`、`config/curve-inputs.yaml` |
| 公式与光子链路 | `config/formulas.yaml`、`config/formula-notes.yaml`、`config/photon-flow.yaml` |
| 任务输入和结果 | `artifacts/runs/<任务ID>/request.json`、`result.json` |
| 任务状态索引 | `artifacts/runs/jobs.sqlite3` |
| 规范与当前状态 | [文档目录](docs/index.md)、[架构决策与偏好](docs/design/architecture-decisions.md)、[界面规范](docs/design/ui-design-guidelines.md)、[路标](docs/roadmap.md) |

运行数据、下载的论文PDF和本机客户端缓存不会随Git推送；需要另行备份。源码、配置、文档、选定验收报告和快照进入版本管理。保存与复现方式见[运行数据说明](docs/guides/run-artifacts.md)。

模型说明：[B空间光学](docs/models/spatial-optics.md) · [双轴空间模型](docs/models/spatial-profiles.md) · [C列级扫描](docs/models/column-scanning.md) · [统一光谱](docs/models/curve-inputs.md) · [光子预算](docs/models/photon-budget.md) · [直方图](docs/guides/histogram-display.md)。当前发布说明见[版本记录](docs/release-notes.md)；旧README已移入[历史记录](docs/history/readme-through-0.6.0.md)。

## 开发验证

```powershell
.venv\Scripts\python.exe -m pip install pytest httpx
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/render-photon-budget-doc.py --check
.venv\Scripts\python.exe scripts/render-spatial-profiles-doc.py --check
node scripts/check-histogram-rendering.cjs
```

模型变更验证量纲、能量、极限和共享核心一致性；界面变更实际检查表单、联动、普通刷新及图形。详细约束见[AGENTS.md](AGENTS.md)。
## 系统预算入口（2026-09-28）

启动平台后打开 `/system/budget`，或通过A/B/C顶部“系统预算”进入。支持单方案与基准对比、列时序、光子预算、硬件约束及可审计快照；初始值继承现有配置。[使用说明与模型边界](docs/guides/system-budget.md)。
