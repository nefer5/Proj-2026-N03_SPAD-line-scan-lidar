# 192线单芯片容量诊断

2026-10-03用户确认：192个角通道归属一颗SPAD芯片，一个MIPI接口含四条data lane。当前网页已将lane数设4、可用独立端口数设1，保留用户其余参数及64KiB/块SRAM声明。

真实API读取：每通道2048个bin、16bit计数，全芯片Hist为786432B/块（768KiB）；双缓冲最低1.5MiB，未计DSP工作区。Range完整点50B，192通道共9600B/slot，不等于片内Hist存储需求。

仅在隔离参考工况将bank扩大到最低需求，未修改网页：片内10Gbit/s搬移629.1456μs，目标slot111.1667μs；四lane MIPI服务时间16.0567μs。资源帧率必要上界约1.7125Hz，仍不能满足目标10Hz。

文件：current-config.json/current-snapshot.json是当前用户工况；minimum-bank-reference.json是标明扩容假设的完整参考结果；capacity-diagnostic.png是更新诊断后正式网页截图。后台新增容量需求/配置量诊断，15项pipeline测试通过，其中增加192线单芯片四lane回归。未自动扩容、压缩Hist或修改目标帧率。
