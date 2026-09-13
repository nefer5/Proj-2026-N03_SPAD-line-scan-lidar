# SPAD + VCSEL + 转镜一维线扫 LiDAR 建模器

这是一个用于快速评估 dToF 测距性能的基础版本。它把当前扫描角通道建模为：

`VCSEL 脉冲能量 -> 朗伯目标 -> 接收孔径/滤光片 -> SPAD 面阵按线 binning -> 首光子 TCSPC 直方图 -> 距离估计`

当前版本不做光线追迹。Tx 角度分布、Rx 收光效率/PSF 数据库的接口和推荐格式见 [docs/model-design.md](docs/model-design.md)。

## 已实现

- 网页输入和修改核心参数；
- 标准扩展朗伯目标光子预算；
- 太阳/环境光谱辐亮度、滤光片曲线、DCR 和自定义噪声；
- VCSEL 脉宽、SPAD 抖动、TDC 分箱；
- 每个 SPAD 每发只记录首光子的 TCSPC pile-up 模型；
- 期望直方图和随机观测直方图；
- 质心测距、重复仿真的偏差/精度/成功率；
- 距离扫描性能曲线；
- 通道间直接串扰矩阵及级联串扰期望模型；
- 配置 JSON、滤光片 CSV 和直方图 CSV 导出。

## 启动

本机已有 FastAPI、Uvicorn、NumPy 和 SciPy 时，可直接运行：

```powershell
python run.py
```

然后打开 <http://127.0.0.1:8000>。

如需安装依赖：

```powershell
python -m pip install -e .
python run.py
```

运行测试：

```powershell
python -m pytest
```

## 首版的重要定义

- `脉冲能量` 是分配到当前被评估扫描角通道/VCSEL 单元的能量，不是整条线阵总能量。
- `PDE × fill factor` 是光子到达 SPAD 感光面后的有效探测比例。如果器件给出的 PDP 已含填充因子，请将 fill factor 设为 1。
- `背景光谱辐亮度` 是目标/场景射向接收机的谱辐亮度，单位 W/(m²·sr·nm)，不是照度 lux。
- 当前读出假定每个 SPAD 每次激光发射最多输出一个时间戳；死时间和共享 TDC 的多事件模型属于下一阶段。

