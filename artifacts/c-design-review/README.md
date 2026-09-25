# C 列曝光工作台 · 设计审核快照

日期：2026-09-25。预览：`http://127.0.0.1:8016/static/prototypes/c-exposure/index.html`。

这是独立前端设计预览，尚未替换正式 C 页面，也未实现新的列调度、长尾模型、内部事件轨迹或带宽队列。按用户单独授权，B/C 默认读出阵列已改为 H×V=2×16；H 是兼容维度，V 是线数。当前核心仍计算两路 H，不将显示选择解释成硬件禁用。

## 来源与复现

- 设计说明：`docs/history/c-exposure-workspace-design.md`。
- 工况唯一默认源：`config/defaults.yaml`；说明：`config/parameter-help.yaml`。
- `python tools/build_c_design_preview.py`：从当前 SimulationConfig、算法配置、已有调度和公共波形函数生成参考 JSON，再为 CSS/JS/JSON 生成内容指纹。
- 只更新页面样式/交互时：`python tools/build_c_design_preview.py --assets-only`。
- 此次没有探测器随机仿真。参考发射与波形是真实现有函数输出；候选新策略和流水线关系明确为示意。
- `data/synthetic/spatial-example.json` 随当前阵列重新生成，保持光学参数不变。历史任务与已有验收数据保持原工况。

## 验证

- 改为 2×16 后，完整已有测试：225 passed（91.48 s）。
- 更新 H/V 参数说明后，B/C/API 针对性复核：28 passed（13.05 s）。
- 实际 8016 服务的 system、scan 默认接口均返回 H=2、V=16，响应为 `Cache-Control: no-store`。
- Tabbit 实际浏览器检查：全折叠/展开、H 路切换、标签偏差示意、起始列、纳秒缩放、精确时间输入、非法窗口反馈、全帧导航拖动、策略选择、因果示意、行选择、草案编辑/导出/恢复、流程弹窗、普通刷新。
- 规划区检查：单/双缓冲、三种数据格式、空的未知值、切换后保存草案值、恢复参考。所有操作未向生产接口发送 POST；没有页面 JavaScript 异常。
- 1536×1100 与 390×844 视口检查；移动端两工作区均无页面级水平溢出（内部时序图允许横向滚动）。
- 纳秒窗口参考：相对 S7 开始 30.660302831–30.673953550 μs；精确输入 30.65–30.69 μs 通过，终点小于起点时拒绝。

## 图像

1. `01-concepts.png`：点云帧、列 slot、触发周期和角标签概念。
2. `02-two-column-timeline.png`：S7/S8 两列时序、彩色观测窗口、精确时间输入和公共核心波形。
3. `03-resource-planning.png`：帧/列资源和双缓冲依赖关系。

`check-1.js`、`check-2.js`、`check-3.js` 保留交互验证步骤。`snapshot-sha256.json` 记录本轮源文件、数据和截图的哈希。

## 已知边界

当前均匀扫描参考下，一个角格恰好关联一个列 slot；这不是未来非均匀列调度的通用算法。Tx/Rx 覆盖角域没有随线数扩大，不能据此假定全部行都已照亮。处理、锁存、传输延迟和数据格式未定义，不提供虚构 Mbps 或流水线耗时。原 SPAD 核心的建模继续共用，正式 C 新计算逻辑等设计审核后推进。
