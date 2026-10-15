# A直方图显示与观察窗口恢复

2026-10-15，A评估页 `/` 与调试页 `/debug`；本轮自验通过，用户人工验收待进行。

## 退化来源

2026-09-24提交aaa9249（ship modular B workspace and shared C scanning interface）把A的drawLines替换为PhotonHistogram，共享A/B绘制逻辑。旧函数固定逻辑高度260px；新组件读取实际DOM尺寸，而A只保留HTML height、CSS width:100%，由默认300px画布宽度的纵横比推高显示高度。修复前1920px视口实测图宽1056px、高915.265625px。图内图例没有迁移，坐标字体由11px变成9px。B的概览拖动/精确输入未接回A。

当时验收文件强调A八模式预算、直方图、指标、检测和读出数值一致；该项不能覆盖A显示高度、图例和交互。未找到证据说明有意简化A。原A有自动聚焦图；可拖动窗口是在B开发时新增，因此不把它描述为从旧A删除的交互。

## 实现

- 评估和调试继续共用web/index.html、app.js及PhotonHistogram。
- 局部图360px、窄屏300px；全门概览90px，均用CSS固定，位图尺寸与显示高度分离。
- 恢复五项图例，A坐标使用11px字体，其他平台保留原字体。误差棒不可用时隐藏对应图例。
- 橙色窗口可整体移动/拖边界；精确输入、Enter、聚焦目标峰和显示全门。非法输入拒绝，不裁剪；resize与主题切换保留有效视窗，新结果恢复目标峰。
- 共享窗口绑定返回清理函数，A更换结果时移除旧监听，避免反复采集累积事件处理器。

## 自验

- 实际运行的8016服务，Chromium agent-browser独立session；qa.js分别在评估/调试页执行。精确600.125–700.875ns、空值、反向、负起点、越界终点、全门/目标峰按钮、重绘和主题切换均通过。
- 用实际mouse move/down/up拖动概览。评估页500–900ns整体移动到659.7503900156006–1059.7503900156007ns，再拖动左边界到715.6817472698908ns；调试页整体移动到602.6052104208418–1002.6052104208418ns。窗口整体移动保持宽度，拖边界改变宽度。
- 窗口操作期间fetch请求为0，完整lastResult JSON不变。局部纵轴刻度为整数。
- 1920px视口360/90px；390px视口300/90px，无页面横向溢出，resize保留有效窗口。
- 普通导航/刷新获取新内容指纹资源；评估和调试使用相同绘图资源。深浅截图已实际查看。
- node --check两个修改JS、node scripts/check-histogram-rendering.cjs、python scripts/build-theme.py --check通过。
- python scripts/capture-a-baseline.py artifacts/architecture-upgrade/baseline/a-fixtures.json --check：八模式预算/直方图/指标/检测/读出精确一致。
- python -m pytest tests/test_histogram_ranges.py tests/test_histogram_preview.py -q：16 passed。

截图：[评估深色](evaluation-dark.png)、[调试浅色](debug-light.png)。qa.js在加载结果后通过agent-browser eval -b执行；操作只改变独立浏览器会话中的显示，不改YAML或保存结果。
