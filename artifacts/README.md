# artifacts用途与保存边界

这里主要保存设计/执行产物与证据，**不是正式运行源码目录，也不等于全部临时文件**。正式计算在src/，正式网页在web/，唯一运行配置在config/，测试在tests/，共享校验工具在scripts/。

| 内容 | 用途 | Git与保留 |
|---|---|---|
| budget-*验收目录 | 当前/历史截图、输入配置、README、完整结果 | 选定截图/输入/报告入Git；大型原始snapshot只留本机 |
| design-library/spad-data-timing | 长期保存的双主题PNG/SVG、场景及复现绘图器 | 可编辑/可复现原件入Git，重复ZIP留本机 |
| canvas-backups | 用户画板、嵌入图片、摘要/哈希 | Excalidraw原件、预览和manifest入Git，ZIP副本留本机 |
| budget-parameter-design、budget-spad-design、timing-design* | 设计预览、画板场景、演示脚本 | 作为历史设计保留；目录内py/html/js不作为正式仿真代码使用 |
| timing-design/implementation-draft | 已撤回的试写代码 | 本机留存并忽略；不启用、不作为实现入口 |
| runs、runtime | 仿真任务/数据库、开发服务日志 | 本机运行资料，不提交 |
| paper-comparison等本地文献截取 | 原论文图/资料对照 | 本机参考，不作为发布资产或运行依赖 |

不要仅按文件扩展名判断用途：artifacts中的Python通常是绘图复现或一次性演示，json可能是输入、画板或大数组快照。设计图稿与画板有长期价值，不能整目录当垃圾删除。

当前权威说明见[系统预算指南](../docs/guides/system-budget.md)及[文档索引](../docs/index.md)。历史目录README记录当时状态，不能拿schema4草稿或演示耗时覆盖当前实现。新阶段记录与选定输入/哈希见budget-closeout-2026-10-03。

Git提交覆盖源码及选定证据，不包含被忽略的原始快照、数据库、日志和ZIP备份；这些文件仍在本机。若要整机/数据迁移，须另外备份本机运行材料。
