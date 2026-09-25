# 明确构造的光学样例

`spatial-example.json` 由当前 `SimulationConfig.for_experiment('system', {})` 和 `optical_dataset` 生成，包含生成参数、算法采样数、坐标/参考面、Tx角份额、Rx效率和像素积分PSF。

它是解析高斯/均匀模型生成的验证数据，不是测量或光学软件实测导出。默认参数唯一来源仍为 `config/defaults.yaml`；此文件是固定数据快照，不会自动跟随默认参数变化。

完整字段规范及损耗口径见 `docs/models/spatial-optics.md`。在整机网页导入本文件后，Tx/Rx模型切为dataset；图形和记录应与生成该快照时的同条件构造模型一致。
