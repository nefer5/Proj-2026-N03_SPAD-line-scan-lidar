# 配置重构第二阶段实施与验证

日期：2026-10-18。范围：默认配置领域化、统一组合及来源追踪、正式C与预算的配置组合迁移。具体默认归属以[现行配置指南](../../docs/guides/configuration-and-data.md)为准，未完成事项以[路标](../../docs/roadmap.md)为准。

## 改动

- defaults.yaml内部schema 2以domains组织Tx、场景、Rx、SPAD、读出、背景、采集、光谱、运动、场景运动和系统目标；平台专用字段留在experiments。所有实际物理/统计默认值保持不变。
- default_layout负责布局/历史路径适配，default_composition负责六个兼容kind的组合与来源；读取与“设为默认”写回共用来源，不再独立推断两次。
- BSystemConfig归入domains/optical_system，扫描配置基础类型归入scan/config；旧导入路径仍导出同一对象。
- C不先创建历史扫描工况，预算使用同一公共组合层添加硬件差异；未修改C列间状态、C/预算调度策略或公开配置schema。

## 验证证据

- before.zip/before-hashes.json保存实施前源码、前端、配置、文档与测试。numerical-before.json.gz保存19组完整配置/schema与数值结果。
- numerical-comparison.json记录19组严格规范JSON逐项相等（只排除utc时间）；包括所有A读出模式、SPAD、B候选/采样参考、C重复采集和预算。
- full-suite-final.log为新布局隔离目录上的最终全量测试，482项通过。首次480通过、1失败为系统目标缺字段时的异常类型变化，已恢复原typed ValidationError并复验。
- job-compatibility.json对照97份现存历史请求：此前可解析25份保持相同，72份此前即不满足当前约束，本次未补造缺失默认；无新增回归。原始请求未改动。
- 浏览器验证使用18766端口、browser-config与browser-backups，测试值不写入正式配置。B/C/预算/A/SPAD检查实际表单、来源审查与保存，B普通刷新和恢复默认后读回新值。
- b-domain-source.png显示公共场景写入domains.scene；budget-source.png显示预算几何写入experiments.budget.geometry。前端布局及所有JS/CSS与实施前逐字节保留。
- validation.json记录文档引用、前端与算法保留及最终部署核验。生成公式文档同步检查通过。

## 迁移与回退

正式迁移只执行scripts/migrate-default-layout.py --write：逐平台验证解析结果一致，保留原始字节、SHA256与时间，再通过同卷原子替换写入。迁移备份位于artifacts/default-layout-migrations。内部文件schema与工况导入/导出版本互相独立，不改旧作业快照。

若仅需恢复旧布局，可把迁移目录的defaults.yaml覆盖回config/defaults.yaml；当前代码仍能读取合法schema 1。完整阶段回退需先停止本项目服务，再按before.zip恢复本阶段改动并重新启动；备份包含阶段开始时其他聊天的既有工作，不应以Git reset覆盖那些改动。

本阶段为实现及自动自验，用户人工验收待进行；不代表三个工作台、平台命名、C列间复位、调度统一或前端语言统一已完成。旧C4 HTML保留为对应时间快照，不能当成此刻实时目录。

正式8016服务已验证重启，六个平台默认与阶段开始前完全一致，默认预览无变化。正式配置与通过全量测试的candidate-config/defaults.yaml文本一致（测试副本CRLF，正式迁移LF）；迁移原件在artifacts/default-layout-migrations/6e22c73692774a8a9b2c7bbfe47d2238。
