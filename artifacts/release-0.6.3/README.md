# 0.6.3.dev0 发布前核验

日期：2026-09-25。计算代码基线为 `7418b2a`；本次追加文档整理和分类、引用路径及文档检查工具更新，不改变仿真算法或工况数值。

## 检查结果

| 检查 | 结果 | 范围 |
|---|---|---|
| 完整Python回归 | 291 passed，88.55 s | 文档分类前，当前计算代码基线；不等于器件实测验收 |
| 分类后的定向回归 | 24 passed，4.22 s | `tests/test_photon_flow.py`、`tests/test_v011.py`，包含生成文档同步及递归Markdown公式约定 |
| 光子预算生成同步 | 通过 | `python scripts/render-photon-budget-doc.py --check`；新目标为 `docs/models/photon-budget.md` |
| 双轴模型生成同步 | 通过 | `python scripts/render-spatial-profiles-doc.py --check`；新目标为 `docs/models/spatial-profiles.md` |
| KaTeX解析 | 79个公式通过 | `scripts/check-math.cjs`现递归扫描整个docs；只读使用本机VS Code附带的KaTeX引擎，没有启动或操作编辑器 |
| 直方图绘图检查 | 通过 | `node scripts/check-histogram-rendering.cjs`；整数网格、柱宽/位置、统一全门纵轴和局部缩放 |
| 文档导航与链接 | 通过 | README、AGENTS与docs共31个文件、136个本地链接；全部docs页面已列入总索引 |
| Git差异空白检查 | 通过 | `git diff --check`；目录迁移后再次检查 |

本轮没有重做网页视觉审核或C人工验收；相关历史快照见[带外漏光](../filter-leakage/README.md)、[双轴光学](../optical-shapes/README.md)、[直方图核验](../histogram-display-audit/README.md)。C精细人工验收仍按[清单](../../docs/validation/c-manual-review.md)记录。

## 提交范围

- 当前分支 `codex/modular-spad-b`，远程 `origin`；推送当前分支，不合并或覆盖 `main`。实际提交编号以包含本文的Git提交为准。
- 文档总入口：[docs/index.md](../../docs/index.md)。根目录保留索引、路标和版本记录；正文按设计、模型、指南、验收、参考与历史归类。
- [路标](../../docs/roadmap.md)记录Rx/Tx角域分离、C人工验收、平台命名、参数/定义/后台共用、UI统一；没有将这些待办误记为已实现。
- 当前源码、配置、文档与选定的小型审计报告/快照纳入版本管理。`artifacts/runs/`、PDF、本地Zotero/研究同步检查点及三份B噪声原始重放JSON留在本机并被忽略，没有删除。
- 已检查待推送历史对象：最大blob约28.6 MB，未发现超过100 MB的单文件；旧版本历史和已提交的验收材料保留。

文档本身不是运行默认值的来源。参数值仍唯一维护在 `config/defaults.yaml`，算法策略在 `config/algorithms.yaml`；本次配置文件的差异仅更新参考文档路径。
