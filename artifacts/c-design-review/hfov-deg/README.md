# HFOV界面单位改为deg

2026-09-25。高层HFOV输入和系统资源页HFOV显示统一改为deg；内部保留hfov_mrad并显式换算。默认40 mrad对应2.291831180523293 deg，列目标仍为40 μs，不改变物理工况。

浏览器已验证：初始单位与数值、90 deg换算为1570.7963267948965 mrad、导出包含hfov_deg输入与内部mrad值、零/空白报错、恢复默认精确回到40 mrad、目标下发、资源页HFOV显示、普通刷新。无页面JavaScript异常。

截图：preview.png。复核脚本：check-browser.js。未修改正式探测器或预算模型。
