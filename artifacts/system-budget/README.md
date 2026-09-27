# 系统预算第一版验证（2026-09-28）

范围：`/system/budget`。已实现、自验通过；用户人工验收待进行。保留既有A/B/C能力边界，未实现PRBS解码或C列间复位。

## 数值与接口

- `python -m pytest tests/test_hardware_budget.py tests/test_system_planning.py tests/test_photon_flow.py -q`：38项通过。其中新增22项覆盖默认继承、未知值、B光学一致性、能量守恒、阵列聚合、发数/功率/电热量纲、超时与输出超限、零能量/门外目标、PRBS独立性、非法配置、默认缺键和重载、API导入与内容指纹。
- `python -m pytest tests/test_spatial_optics.py tests/test_columns_api.py tests/test_b_platform.py tests/test_curve_inputs.py tests/test_filter_leakage.py tests/test_column_scan.py -q`：93项通过。
- 共享光子文档和空间模型文档两个生成脚本 `--check` 均通过。
- `node scripts/check-math.cjs <本机VS Code markdown-math/notebook-out/katex.js>`：79个现有Markdown公式解析通过。新增展示公式在网页本地KaTeX中实际渲染；本次未新增Markdown公式。
- `node --check web/budget.js` 与 `node --check web/system.js` 通过。

## 浏览器实测

使用agent-browser隔离会话，真实服务端口8016，未修改系统浏览器配置。

| 检查 | 结果 |
|---|---|
| 默认加载、表单和图形 | 66.7 μs/列、12 nJ/列；复位未知显示待提供。时间SVG与光子SVG实际显示。 |
| 单方案联动 | 1发改4发后48 nJ/列；设置1000 ns复位后余量33.652 μs。 |
| 超限与错误 | 8发且1000 ns复位时余量−6.348 μs，显示超限；1.5发报“必须为整数”，不作为有效新结果。 |
| 基准 | 保存单发基准，当前4发显示逐项数值及输入差异；普通刷新后基准指纹不变。 |
| 枚举与缓存 | 矩形脉冲以字符串提交并在普通刷新后保留。 |
| PRBS | 127码片、10 ns、64开码片：1270 ns周期、768 nJ/码、名义周期距离190.368 m；主方案指标不被替换。 |
| 旧缓存 | 注入schema_version 0草稿，明确报错，保留rejected恢复副本，显示当前默认；随后恢复测试草稿。 |
| 公式和布局 | 本地KaTeX 17处渲染、0错误；1500×1000与390×844均无整页横向溢出，图形窄屏局部滚动。 |
| 导出 | 原生Enter激活导出按钮，读取实际生成Blob验证完整配置、指纹和基准；保存为ui-snapshot.json。CLI的独立download命令曾超时，未将该命令计为通过。 |
| 送入B | B实际页面ready=true，保留4发与rectangular；session传递内容被消费。未自动采集，未混入系统预算特有参数。 |

## 证据

- [默认页](01-default.png)、[四发时序](02-four-pulses.png)、[光子与约束](03-photon-budget.png)、[两方案比较](04-comparison.png)、[窄屏](05-mobile.png)、[公式与审计](06-audit.png)、[B继承](07-b-transfer.png)。
- [默认快照](default-snapshot.json)：配置指纹 `eab0365fc47862f8db90cf39ec5086bfe43ccf961abc5db26430828b9080d3e1`。
- [四发＋1μs复位快照](four-pulses-snapshot.json)：配置指纹 `e3884c4d4b75aa3246f33b917a6a514e9f67d6cc976d96e2de209d2f8a8aba49`。
- [UI导出的矩形四发＋PRBS参考快照](ui-snapshot.json)：包含单发对比基准。所有快照均为确定性预算，无随机事件数组。

图中参数仅为软件验证工况，非用户实物标定参数。未修改原有 `artifacts/paper-comparison/`。
