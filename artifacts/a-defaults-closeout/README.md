# 默认工况、共用继承与Git收口

2026-10-15。用户要求保存当前A参数、允许各平台继承，随后明确DCR默认4000kHz/SPAD并将界面输入改为kHz。

## 来源与最终值

实际Tabbit标签795277399的完整collectConfig输出与已完成任务7df6b057491c4ca3b2eac6df7f42f7f8一致，包含当前模式及各CSV/手动独立曲线数据。browser-current-receipt.json保留读取证据；原DCR为10000cps，按后续用户指令覆为4000000cps（4000kHz）。最终完整配置在default-config.json，来源、原结果指纹与最终配置指纹在default-source.json。生产默认唯一写入config/defaults.yaml；这些JSON是验收快照。

主要参数：100m、24nJ/角通道/发、23mm圆形入瞳、Rx效率0.6、IFOV H2.5×V2mrad、H8×V8、DCR4000kHz/SPAD、SPAD死时间9ns、100000lux、太阳灰反射率0.7、其他光关闭、接收门起点3ns/宽2048ns、累计6发、测距4次/含信号均值8次/纯噪声均值6次。A每份从完全恢复状态开始，无预热；单批200万、总任务1000万上限。

## 共用继承与单位

SPAD/B/历史C/列级C/系统预算继承同义的器件、背景、接收及采集字段，未添加保护旧默认的覆盖项。删除预算页共用Tx形状/效率、binning/FF、周期/发数覆盖，B统计次数随共用MC继承；专有空间布局、Tx全角域功率、扫描计划及曝光列表保留各自定义。shared-defaults-verification.json记录所有平台解析的共用器件值。

LidarUnits统一DCR显示换算：4000kHz↔4000000cps，1.25kHz↔1250cps。配置/API/导出及浏览器草稿仍保存cps，旧存储400000cps显示400kHz，不再乘一次。A、调试、SPAD、B、C及历史C中已有DCR输入统一显示kHz；预算页当前未提供DCR输入，继承后的内部值仍为4000000cps。共享单位脚本纳入全部7个页面内容指纹及no-store响应。

继承新binning使B密集空间×光谱工作量达188006400，超过原100000000上限；构造Rx明确无色差，既有精确外积路径将等价工作量降到313944。仅在原精确分离开关允许、Rx非数据集且需要资源压缩时采用，不降低采样或背景，不提高限额；审计显式记录resource_factorization和dense_integration_work，密集对照相对误差1e-12内。

## 验证

- 全量pytest：419 passed in 87.46s。数值实验显式使用tests/fixtures/numerical-reference-defaults.yaml固定参考工况，配置热加载及真实新默认测试保持使用当前YAML；原资源阈值假设改为按实际限额验证。5个平台共用默认专项通过。
- 表单枚举/输入、DCR单位、整数刻度与共享直方图Node检查通过；JS语法及主题同步、共享光子预算文档同步、Git空白检查通过。
- 新完全恢复8模式gzip基线使用旁置fixture-config.json固定完整输入，当前用户默认变化后仍精确通过；30MB原始JSON留本机，约1.92MB gzip夹具随版本保存。
- 实际浏览器：A/SPAD/B输入默认4000，提交4000000；SPAD/B小数1.25转换1250；C从真实导出按钮取得JSON，1.25kHz输出1250cps；预算继承值4000000。dcr-khz-default.png已查看。
- Tabbit独立临时页验证最终完整默认和实际新结果均相等，显示4000kHz、配置4000000cps；108周期、490517.2848897922候选，A模型0.2.2且fully_recovered。browser-defaults-verification.json记录成功回执。发现初次载入会展示旧任务后，明确重新采集验证；保留用户原标签与原last-job指针，不改写旧结果。
- 既有浏览器自定义草稿不被覆盖；普通刷新更新界面，恢复默认后运行才采用本次默认。

## Git边界

源码、配置、文档、选定截图/回执/输入和压缩基线提交；完整运行数组、全量测试日志及整浏览器标签库存留本机并忽略。此前架构图按其原版本354cb2e作为历史快照单独归档，delivery校验哈希与实际文件一致，不冒充更新后的当前逐行架构。
