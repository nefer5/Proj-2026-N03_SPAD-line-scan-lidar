# A 评估与专家调试指南（现行）

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
