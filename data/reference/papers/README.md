# 公开论文参考目录

此目录保存公开可获取论文的本地查阅副本，不作为仿真运行依赖。下载原文保留其版权和使用条件。PDF与未完成的`.part`下载文件默认不纳入Git；本索引及建模参数说明可纳入版本管理。

| 本地文件 | 论文与用途 | 原文入口 |
| --- | --- | --- |
| [van-sieleghem-2022-bsi-nir-spad.pdf](van-sieleghem-2022-bsi-nir-spad.pdf) | Van Sieleghem等，2022，A Backside-Illuminated Charge-Focusing Silicon SPAD with Enhanced Near-Infrared Sensitivity。第8页图7是默认PDE的来源 | https://arxiv.org/pdf/2203.01560v1 |
| Sony论文待补充完整PDF | SPAD depth sensor for automotive LiDAR systems，JSAP Review 2023，230402。用户已核验截图，用于DCR/抖动/死时间/TDC工程参考 | https://www.jstage.jst.go.jp/article/jsaprev/2023/0/2023_230402/_pdf |

PDE原文SHA256：`151dbf7415638fd7382c4f82a31940a63770c8d6c87a36346b5e8135bfe16419`，完整15页。960–1000nm的两个PDE点由本项目外插，不来自该论文。提取参数见 [PDE说明](../../../docs/pde-literature.md)。

器件参考条件见 [Sony参数说明](../../../docs/sony-reference.md)。本地PDF复制/下载仅供查阅，不表示当前模型完整复现该芯片。

2026-09-15下载状态：Sony站点多次连接重置，直连也超时，且不支持本次断点续传。PDF头声明完整文件应为3707345字节、4页，但本次所得文件均不完整，因此未作为正式PDF放入本目录。未完成下载已隔离到被Git忽略的`data/local-sources/*.part`，没有后台下载继续运行。可从原文入口手动下载后放在本目录。
