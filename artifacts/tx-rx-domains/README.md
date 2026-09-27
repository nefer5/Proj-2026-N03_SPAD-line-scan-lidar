# Tx/Rx角域与功率输入验证（0.6.4.dev0）

用户确认：全Tx角域VCSEL出光、Tx光学前的单脉冲等效平均功率默认280W；总单发能量=功率×脉宽，高斯以FWHM为等效时长。预算Tx H全宽2mrad、V全宽=VFOV，Rx域独立。VFOV尚无实物值，当前继承原6mrad（约0.343775°）。

## 自验结果

- `test_hardware_budget / test_spatial_optics / test_b_platform / test_column_scan / test_scanning / test_filter_leakage / test_tx_rx_domains`：127项通过。
- `test_columns_api / test_photon_flow / test_spatial_profiles / test_binning`：32项通过。合计159项不同测试。
- 单独复跑硬件预算与新角域测试31项通过。生成光子文档同步、VS Code内置KaTeX 79公式解析、JS语法和主题表同步通过。
- 固定Rx/环境，改变Tx域、形状或能量，背景数组/候选率保持一致；均匀Rx的角域立体角扩大2倍，背景2倍，域内信号不被重新归一化。
- Tx信号落在显式Rx域外时记为接收损失；导入Rx表未完整覆盖配置接收域时报错，不外推。
- A退化极限使用相同单发能量、角域、均匀接收和光谱对照，通过所有入瞳/探测面参考面验证；未拿A的12nJ默认直接与新B的560nJ比较。
- 280W×2ns=560nJ；改变为4ns得到1120nJ。旧12nJ/2ns迁移成6W，能量不变；同时提供旧能量和新功率时报错。
- V分区份额和为1；各Tx分区功率/能量和为280W/560nJ；物理Rx V组信号/背景和与全阵列一致。

## 真实页面

当前IAB旧草稿成功保留原12nJ/12mrad迁移，显示迁移提示；随后按本次用户指定将功率改280W、H全宽改2mrad。实际页面显示560nJ和独立Rx边界。

将VFOV临时改为1°，页面显示Tx V全宽17.4533mrad，Rx仍为H[-6,6]/V[-3,3]mrad，背景仍为9815.32候选/列。之后恢复原VFOV，保留用户指定280W/2mrad。

默认快照：[default-snapshot.json](default-snapshot.json)，配置指纹 `81808cba61c785689cd2c2a57ca69f2c23847c1c79f511380b8d6879cafa6767`。

当前IAB实拍：[280W与独立角域页面](budget-updated.png)。普通刷新后仍为280W/560nJ/H=2mrad；16行V分区显示，公式渲染错误0，整页无横向溢出。

## 限制

已实现并自验，实物收光域及用户人工验收待确认。Rx域是明确的硬接收边界，域外不接收；真实过渡形状需响应数据支持。空间/光谱积分仍受显式采样策略约束，不能把此自验视为任意大VFOV的收敛证明。

Tx V表按已有角格内常密度守恒重分区；Rx V表按真实物理分组汇总H路。二者索引不保证一一对应。历史算法快照缺新策略时明确采用legacy_tx；当前新计算用independent_rx。C列间复位、PRBS解码及C人工验收状态未改变。
