# 0.6.13系统硬件预算阶段收尾证据

2026-10-03用户确认阶段收尾，要求将当前网页参数设为默认并提交Git、整理日志。本目录是工况与验证证据，程序不从这里读取运行默认。

| 文件 | 用途 |
|---|---|
| selected-config.json | 点击高级JSON“载入当前表单”得到的当前输入，冻结前捕获 |
| verified-default-config.json | Python严格模型解析后的完整预算默认，用于与输入逐项比对 |
| freeze-validation.json | 输入/默认相等、其他平台默认不变、派生角域未复制及输入哈希 |
| browser-validation.json | 正式页实际点击“重新加载默认”后，结果工况逐项相等；页面状态及模型/定义/配置指纹 |
| defaults-loaded.png | 实际网页截图，显示192线、20° VFOV、1000 W、12发累计能量及计算完成状态 |
| default-budget-summary.json | 当前默认的电学、存储、时序和B可运行性摘要，来源为同一公共核心 |
| validation.json | 提交前测试及共享定义检查汇总 |
| manifest.json | 本目录选定证据的文件大小与SHA256 |

defaults-before.yaml与full-default-snapshot.json是本机恢复/完整审计资料，Git忽略；没有删除。审计工况和算法共同参与provenance配置指纹，freeze-validation的哈希仅针对规范化工况，两者定义不同。

当前保存的是Echo输出，距离参考关闭，固定A采集/B处理，192线单chip/单link/4 data lanes。完整数值以JSON和config/defaults.yaml为准。其他平台基线不随本次冻结变动。

记录与限制见[阶段日志](../../docs/history/2026-10-03-hardware-budget-phase.md)。用户阶段确认不代表全部专项人工验收、真实芯片实测或CSI-2接收兼容完成。
