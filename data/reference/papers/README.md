# 公开论文参考目录

此目录保存公开可获取论文的本地查阅副本，不作为仿真运行依赖。下载原文保留其版权和使用条件。PDF与未完成的`.part`下载文件默认不纳入Git；本索引及建模参数说明可纳入版本管理。

| 本地文件 | 论文与用途 | 原文入口 |
| --- | --- | --- |
| [van-sieleghem-2022-bsi-nir-spad.pdf](van-sieleghem-2022-bsi-nir-spad.pdf) | Van Sieleghem等，2022，A Backside-Illuminated Charge-Focusing Silicon SPAD with Enhanced Near-Infrared Sensitivity。第8页图7是默认PDE的来源 | https://arxiv.org/pdf/2203.01560v1 |
| [2023_230402.pdf](2023_230402.pdf) | SPAD depth sensor for automotive LiDAR systems，JSAP Review 2023，230402。用户已核验截图，用于DCR/抖动/死时间/TDC工程参考 | https://www.jstage.jst.go.jp/article/jsaprev/2023/0/2023_230402/_pdf |

PDE原文SHA256：`151dbf7415638fd7382c4f82a31940a63770c8d6c87a36346b5e8135bfe16419`，完整15页。960–1000nm的两个PDE点由本项目外插，不来自该论文。提取参数见 [PDE说明](../../../docs/references/pde-literature.md)。

器件参考条件见 [Sony参数说明](../../../docs/references/sony-reference.md)。本地PDF复制/下载仅供查阅，不表示当前模型完整复现该芯片。

2026-09-15下载状态：Sony站点多次连接重置，直连也超时，且不支持本次断点续传。PDF头声明完整文件应为3707345字节、4页，但本次所得文件均不完整，因此未作为正式PDF放入本目录。未完成下载已隔离到被Git忽略的`data/local-sources/*.part`，没有后台下载继续运行。可从原文入口手动下载后放在本目录。

## 2026-09-25 归档复核

上述2026-09-15下载失败为历史状态。当前Sony PDF已完整存在：3707345字节、4页，逐页可提取文本且无需修复。

- [Padmanabhan等2019起步建模论文](padmanabhan-2019-dtof-architecture.pdf)：27页，DOI https://doi.org/10.3390/s19245464 。来源：https://mdpi-res.com/d_attachment/sensors/sensors-19-05464/article_deploy/sensors-19-05464-v2.pdf 。
- [Incoronato等2021统计建模论文](incoronato-2021-statistical-spad.pdf)：23页，DOI https://doi.org/10.3390/s21134481 。来源：https://mdpi-res.com/d_attachment/sensors/sensors-21-04481/article_deploy/sensors-21-04481-v2.pdf 。
- 两篇均为CC BY 4.0开放论文；本地PDF保留原作者、版权和DOI说明。已归入Zotero的“spad研究”，Wiki提供中文笔记及项目分析快照。
- 起步论文身份经2026-09-13会话核对：用户提供2019论文，2021论文随后补充；分析在 `docs/history/model-design.md`。
