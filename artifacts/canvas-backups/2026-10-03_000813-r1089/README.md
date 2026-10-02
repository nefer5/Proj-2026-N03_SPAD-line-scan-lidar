# LiDAR设计画板独立备份

完整保存本次画板的图形、文字、手写笔迹、嵌入图片和布局；不是只有截图。

- lidar-design-board.excalidraw：可编辑完整原件，图片已嵌入，不依赖原临时文件。
- whole-board-overview.png：全画板位置概览，仅用于快速查看。
- parameter-preview.png：本轮分组/颜色层级预览。
- manifest.json：来源画板ID、版本、元素/图片计数和SHA256。

恢复：在新的空白Excalidraw/AgentCanvas编辑画面通过打开文件导入.excalidraw原件。建议导入新画板，保留当前原板。

校验：JSON回读与源场景一致；所有活动图片引用齐全、base64解码通过；ZIP逐文件字节和哈希一致。未在当前原板执行导入覆盖。

范围：这份备份保存当前完整画板内容；不包含服务配置、接收凭据或全部历史提交记录。原画板及其历史仍保留。
