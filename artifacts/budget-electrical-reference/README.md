# 电学、距离参考与图表修正验收 · 2026-10-02

研究版本0.6.7.dev0，已实现/自验，人工验收待进行。

- 原图修改：slot样本按真实start/end摆到扫描区内，最后slot结束与扫描结束相等；局部图左/底轴；源功率旁增加全脉冲链路能量/光子柱图，雪崩不赋光学能量。
- 电学：SPAD输出无SPI，histogram/range两种格式。示例16bit、8B/range、16B/chip列头、2data lane/link、1500Mbit/s/lane、80%净效率。整体列头与chip头分开，链路/端口与lane分开。
- 真实网页：当前10线、100slot、10Hz。示例histogram需求328.96Mbit/s总计，每链路32.90Mbit/s；Range需求1.92Mbit/s总计。最忙hist链路每列13.71μs，帧末66.05ms。端口数和缓存未给定，不判真实硬件可部署。
- 限速测试：每lane降至5Mbit/s，histogram平均、slot无积压及帧内完成均不满足，最忙链路输出到411.2ms；验证后恢复1500Mbit/s。
- 理想参考：当前100m、两发矩形脉冲，signal面积51.25候选、理想IRF FWHM2ns、理想统计精度界11.49mm。不是标定结果；手动及CSV实测分开，无实际测量时保持空集。
- 60项完整专项通过（含原图修正、能量柱图、CSV输入校验和电学/参考专项）。B运行资源上限保持，硬件预算不分配全hist，超限禁止直接送B。
- 理论：独立Poisson候选、未知幅值干扰参数、背景已知、IRF+TDC+gate；无死时间/pile-up/温漂等实际误差。只参考文献原理，不宣称复现死时间论文。实测只作对照、不自动拟合或校正。

证据截图将保存electrical.png、reference.png、energy-chain.png及timeline-slot.png；完整配置及算法见current-audit.json，完整数值结果见snapshot.json。

实测导入验证点为临时测试数据，已清空；普通刷新后确认manual点数0、实测散点0。空输入以仅含CSV表头提交，错误提示独立保留，不被普通重算覆盖。
