# A/B/C 整体验收快照

当前：独立SPAD、B空间光学、C逐脉冲扫描均已完成实现和自检，等待整体验收。默认光学/扫描/场景为明确构造工况，不是实测整机性能。

## 直接查看

- [C默认完整结果](http://127.0.0.1:8015/system/scan?job=9e9a5ca623764bb38ad1dcf3dabbe316)
- [B静态光学](http://127.0.0.1:8015/system)
- [独立SPAD](http://127.0.0.1:8015/spad)
- [扫描模型与验收说明](../../docs/scanning.md)
- [最终自动验收记录](final/acceptance.md)

服务运行在8015。关闭后可在项目目录执行 `python run.py --port 8015` 重新启动；保存的任务仍在本地 `artifacts/runs/` 中。

## 源码与证据

| 材料 | 位置 |
|---|---|
| C开发前源码，提交522b16f | [baseline/source.zip](baseline/source.zip) |
| C开发前B七种数字模式数值 | [baseline/b-fixtures.json](baseline/b-fixtures.json) |
| 本次完整源码 | [final/source.zip](final/source.zip) |
| 最终测试结果 | [final/pytest.txt](final/pytest.txt) |
| 完整默认结果、逐发数组与点云 | [final/default-result.json](final/default-result.json) |
| 默认可导入配置 | [final/default-config.json](final/default-config.json) |
| 默认XYZ点云CSV | [final/default-point-cloud.csv](final/default-point-cloud.csv) |
| 网页真实导出的2000ps重放CSV | [final/browser-replayed-cloud-2000ps.csv](final/browser-replayed-cloud-2000ps.csv) |
| 七种工况汇总 | [final/case-summaries.json](final/case-summaries.json) |
| 数据文件指纹 | [final/manifest.json](final/manifest.json) |

完整案例包括default、static、timing-errors、phase-mismatch、gradient-motion、fixed-rx和partial-gate，各有配置及完整结果JSON。源码ZIP保留本机，不重复加入Git；数值、测试、说明和截图纳入版本管理。

历史浏览器收据包含启动等待、跨执行环境数组比较、原生下载事件等待等失败记录，用于追溯验收过程；最终以 `final/browser-acceptance-final.json`、`final/browser-delivery-verified.json` 和验收说明为准。下载虽未触发工具可见事件，实际文件已在标准下载目录确认，并复制至本目录。

之前A与B阶段的独立快照仍在 [architecture-upgrade](../architecture-upgrade/README.md)。
