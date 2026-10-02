# 0.6.8系统预算数据路径验收

日期：2026-10-03。正式页`http://127.0.0.1:8016/system/budget`。

后端相关52项测试通过；独立C配置/API及系统目标17项回归通过。共享光子文档同步检查、表单枚举序列化检查和修改JS语法检查通过。本次未修改展示公式。

浏览器验证：Range/全Hist/Echo切换，Echo三项配置可见；单缓冲隐藏片内搬移速率；全Hist隐藏DSP工作耗时并显示旁路；数值修改改变真实资源调度。普通刷新恢复v5草稿，新增脚本内容指纹生效，未依赖强制刷新，控制台无error。

- `normal-config.json`与`normal-snapshot.json`：用户原有光学、场景、FOV、slot与线数，载入新版电学初始示例。连续三帧观察下10Hz目标节拍满足，无slot延后/拖尾增长；端口数量未指定，不判整机可部署。
- `stress-config.json`与`stress-snapshot.json`：上述工况将每lane线速改为1Mbit/s、每link FIFO改为24B，暴露MIPI反向背压与积压。测试后恢复电学示例。
- `normal-dark.png`、`normal-light.png`：实际正式网页截图。
- `fifo-backpressure-dark.png`、`fifo-backpressure-light.png`：压力场景实际网页截图。

页面首次v4迁移保留`spad-hardware-budget-v1-before-v5`恢复副本。旧空FIFO容量保留未知；随后按用户默认授权加载电学示例。通过DOM完整工况确认`system`和`targets`与迁移前工作草稿完全一致。

参数唯一默认、算法策略、所有中间量及模型指纹在快照中。通用资源假设、全列FIFO策略和未实现的器件/协议细节见[数据处理设计](../../docs/design/spad-data-timing-design.md)。已自验，等待用户人工验收；不是长期稳定、器件实测或接收端CSI-2兼容认证。

用户后续反馈已处理：行距由39缩至30布局单位、色块高22缩至14；连接在色块边缘落点，端点实心点/短实线消除虚线断口，补齐输入→DSP及跨slot SRAM释放依赖。等待连接绕开标签。`compact-dark.png`、`compact-light.png`及`compact-backpressure-dark.png`为实际网页复核截图；计算和配置未变，压力场景测试后恢复正常电学工况。
