# 架构重构与 B 空间光学快照

## 交付状态

- 前两阶段：公共核心重构、独立 SPAD 网页与整机入口，已自动验收。
- 第三阶段：B 全光斑实现、明确构造的数据和自检结果已准备，等待人工验收。
- C 扫描机制未实施。

## 快照索引

| 阶段 | 源码 | 验收材料 |
|---|---|---|
| 修改前 A 基线，提交 3fcfb23 | [baseline/source.zip](baseline/source.zip) | [141项测试](baseline/pytest.txt)、[八种模式数值基线](baseline/a-fixtures.json) |
| 前两阶段，提交 8fbbeab | [stage-1-2/source.zip](stage-1-2/source.zip) | [验收说明](stage-1-2/acceptance.md)、[页面与测试目录](stage-1-2) |
| B 空间光学及最终修正 | [stage-3/source.zip](stage-3/source.zip) | [验收说明](stage-3/acceptance.md)、[默认完整结果](stage-3/default-result.json)、[额外验证工况](stage-3/validation-cases.json)、[文件指纹](stage-3/manifest.json) |

源码ZIP保留在本机，不重复加入Git；测试、说明、配置、数据和页面截图纳入版本管理。历史浏览器失败收据也保留，用于追溯任务按钮刷新和窄屏布局问题；最终结果以 `browser-cancel-fixed.json`、`browser-review-fixed.json` 及最终验收说明为准。

## 复查入口

- [模块化架构说明](../../docs/design/architecture.md)
- [B 数据契约与人工验收步骤](../../docs/models/spatial-optics.md)
- [构造光学数据](../../data/synthetic/spatial-example.json)
- [当前B验收页面](http://127.0.0.1:8013/system?job=12daaa79d28943ec94c9405c253cf65f)
- [独立SPAD页面](http://127.0.0.1:8013/spad)

网页链接需要本地服务运行。可用 `python run.py --port 8013` 启动；后台任务及结果保存在 `artifacts/runs/`。离线复查可直接查看本目录的完整结果、源码ZIP和PNG截图。
