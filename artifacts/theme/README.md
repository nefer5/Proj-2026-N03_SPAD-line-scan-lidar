# 深浅色主题验证（2026-09-28）

已实现、自验通过，待用户人工验收。范围包括正式A/专家调试、独立SPAD、B、C/历史C和系统预算；不调整历史设计原型。

- 所有正式HTML加载内容指纹版 `shared/theme.js` / `shared/theme.css`。默认深色；浏览器 `spad-lidar-theme` 保存偏好，切换无需刷新。
- 浅色文字、表单、半透明卡片、SVG和Canvas配色由公共色表提供。原有深色fallback保持不变；连续RGB/HSL科学色标不经反色处理。
- 浏览器实测系统预算、B、C、SPAD及A页面；浅色跨页继承、普通刷新保留。B切换前后draft序列化一致，A已有结果状态文字不变。无脚本报错。
- A半透明卡片由原固定深色修正为浅色下 `rgba(243,245,247,0.94)`，文字为深色；实际Canvas波形与光谱图可读。
- 页面与接口回归7项通过；现有 `check-form.cjs`、`check-histogram-rendering.cjs` 通过。所有正式JS通过 `node --check`，`build-theme.py --check`通过，`git diff --check`无空白错误。
- 验证截图：[预算浅色](budget-light.png)、[B浅色](b-light.png)、[C浅色](c-light.png)、[SPAD浅色](spad-light.png)、[A浅色](a-light.png)、[A深色](a-dark.png)。

生成维护：新增或改动页面展示色后运行 `python scripts/build-theme.py`。主题是展示偏好，不写入仿真YAML，也不修改计算参数或随机种子。
