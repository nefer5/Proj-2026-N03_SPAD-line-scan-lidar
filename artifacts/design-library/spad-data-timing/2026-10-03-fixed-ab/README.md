# SPAD固定分工双缓冲时序 · 长期设计存档

用户要求长期保留的设计参考，归档于2026-10-03。生成图稿当时正式网页尚未接入；现已接入，见[数据时序设计](../../../../docs/design/spad-data-timing-design.md)。本目录保留原演示场景，图片不是实际芯片能力或当前仿真工况结果。

| 文件 | 用途 |
|---|---|
| [fixed-ab-light.png](fixed-ab-light.png) | 用户认可的原浅色图，原文件按字节保留 |
| [fixed-ab-dark.png](fixed-ab-dark.png) | 平台深色配色版本，布局/文字/阶段时间相同 |
| fixed-ab-light.svg / fixed-ab-dark.svg | 同布局矢量原件，可缩放和编辑 |
| scenario.json | 演示条件、三列各阶段起止与FIFO占用断言结果 |
| render.py | 双主题生成源码；需要Python、Pillow和Microsoft YaHei字体 |
| original-light-renderer.py | 原浅色生成源码，保留历史 |
| theme-palette.json | 深色主题色快照、来源指纹和阶段配色映射 |
| manifest.json | 存档文件SHA256/大小与源图校验信息 |

## 已确认意图

优选为片内Hist、片内DSP、固定角色的A采集/B处理双缓冲，默认Range输出，每点完整字节数由用户配置。全Hist旁路DSP；Echo按每点最大回波数/窗口宽度评估上限，不强制填充。有限输出FIFO满时背压。单缓冲保留作为资源对照。图用三个slot、直角方块、细线、真实交接点的竖直依赖线。

## 图片中的演示假设

A→B整块搬移时占用A/B，搬完并清空A后A才采下一列；B在结果入FIFO后才释放；FIFO一列结果整块保留到发送完成。演示采集80、搬移10、A清空5、DSP100、打包10、发送160μs，一列结果块1KiB。资源断言验证采集开始0/95/205μs、FIFO等待0/60/60μs、FIFO最多一块。数值仅用于展示依赖，不复制为运行默认。

特别是160μs发送时间，是人为设置的慢链路压力场景。实际MIPI应由数据量、协议开销和有效发送速率计算；四条data lane各1.5Gbit/s时，理想1KiB发送仅约1.37μs，不能直接采用图中演示时间。

## 复现与维护

在此目录运行：

```powershell
python render.py --theme dark
python render.py --theme light
```

保留本目录作为固定参考；以后若调整架构或时间，另建版本目录，避免覆盖这一版。PNG/SVG和演示数据一致；深色基本色来自当日web/budget.css，阶段色按语义调亮/调暗，并非对原图做像素反相。正式接入及人工验收需要另行记录。
