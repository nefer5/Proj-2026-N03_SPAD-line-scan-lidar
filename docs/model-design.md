# 建模设计参考与演进路线

## 1. 系统边界

建议把系统拆成六个有明确输入输出的模块：

1. **扫描与时序**：转镜角度、角速度、激光 PRF、驻留时间、扫描角到发射/接收通道的映射。
2. **Tx 抽象**：VCSEL 线阵每个发射单元的脉冲能量、时间波形和二维角度能量分布。
3. **场景/传播**：目标距离、姿态、反射率或 BRDF、大气双程透过率；首版采用朗伯面。
4. **Rx 抽象**：不同入射角的收光效率，以及落在二维 SPAD 面阵上的归一化 PSF。
5. **SPAD/读出**：PDE、fill factor、DCR、时间抖动、死时间、afterpulse、光学/电学串扰、TDC、门控和仲裁。
6. **估计与指标**：直方图、背景抑制、峰值检测、距离估计、偏差、精度、成功率、动态范围和串扰污染。

这样做的关键好处是：将来替换 Tx/Rx 光学数据库时，不需要改 SPAD 或测距算法。

## 2. 首版物理链路

当前网页采用当前扫描角通道的单脉冲能量 \(E_t\)。对于正入射、足够大的朗伯目标：

\[
E_r = E_t\,\eta_{tx}\,\rho\,\frac{A_r}{\pi R^2}\,\eta_{rx}\,T_f(\lambda_0)\,O\,T_{atm}^2
\]

其中 \(A_r\) 是接收孔径面积，\(O\) 是 Tx/Rx overlap。每发的期望信号探测数为：

\[
\mu_s = \frac{E_r}{hc/\lambda_0}\,PDE\,FF
\]

首版把环境光输入定义为场景光谱辐亮度 \(L_\lambda\)，避免依赖光源谱型不明的 lux 换算：

\[
P_b = L_\lambda A_r \Omega_{ch}\eta_{rx}\int T_f(\lambda)d\lambda
\]

\[
\mu_b = \frac{P_b T_{gate}}{hc/\lambda_0}\,PDE\,FF
\]

暗计数为 \(\mu_d=DCR\cdot N_{SPAD}\cdot T_{gate}\)。

时间响应采用 VCSEL 脉宽、SPAD 抖动和其他电子抖动的高斯卷积；TDC 以矩形量化误差处理。当前直方图对每个 SPAD、每发只保留首个时间戳。若理想到达强度在第 k 个 bin 为 \(\mu_k\)，则记录到第 k 个 bin 的概率为：

\[
p_k=\exp\left(-\sum_{j<k}\mu_j\right)\left(1-\exp(-\mu_k)\right)
\]

这个模型会自然产生高通量下的 pile-up 和后部欠计数。

## 3. 二维 SPAD 面阵与线阵读出

不要在模型内部把二维 SPAD 直接压成一维计数。建议保留三个层次：

- `physical_spad[y, x]`：真实二维雪崩事件；
- `binning_matrix[channel, y, x]`：当前工作模式下的空间聚合；
- `readout[channel, event]`：仲裁、共享 TDC 和带宽限制后的输出。

每套 binning 策略用稀疏权重矩阵表示。二值矩阵代表硬件 OR/选择；浮点矩阵只用于期望值或数字域加权，不能等同于硬件事件合并。建议至少支持：

- 固定行/列 binning；
- 随转镜角变化的 ROI；
- PSF 自适应 binning；
- 多个 SPAD 共享一个 TDC 的 subgroup/minigroup；
- coincidence threshold 与 coincidence window。

## 4. 推荐数据文件格式

### 4.1 Tx 角度分布

首选 HDF5/NPZ，CSV 只适合小数据。分布必须归一化为每个发射单元的能量占比。

```text
tx_profile.npz
  h_angle_deg      float64 [Nh]
  v_angle_deg      float64 [Nv]
  energy_density   float32 [Nvcsel, Nv, Nh]
  pulse_energy_j   float64 [Nvcsel]
  pulse_time_ps    float64 [Nt]       # 可选
  pulse_shape      float32 [Nvcsel,Nt]# 可选，积分归一化
```

要求：角度坐标单调；`energy_density[i]` 乘以角度网格面积后的积分为 1；注明角度是空气中机械角、光线角还是远场角。

### 4.2 Rx 效率与 PSF 数据库

```text
rx_psf_db.npz
  h_angle_deg      float64 [Nh]
  v_angle_deg      float64 [Nv]
  wavelength_nm    float64 [Nw]
  collection_eff   float32 [Nw,Nv,Nh]
  psf              float32 [Nw,Nv,Nh,Ny,Nx]
  spad_x_um         float64 [Nx]
  spad_y_um         float64 [Ny]
```

要求：每个 `psf[w,v,h,:,:]` 的和为 1；`collection_eff` 表示到达整个感光面的功率比例，不能再次藏在 PSF 归一化中。插值时，效率可做三线性插值，PSF 建议先插值后截断负值并重新归一化。

### 4.3 滤光片

两列 CSV：

```csv
wavelength_nm,transmission
925,0.00
940,0.85
955,0.00
```

波长必须单调，透过率范围 0–1。信号用 \(T(\lambda_0)\)，背景用光谱积分；若将来同时输入太阳谱、目标光谱反射率和 PDE(λ)，应对四者联合积分，而不是只使用等效带宽。

### 4.4 噪声源

建议统一为带标签的事件率/时间分布：

```yaml
noise_sources:
  - name: solar_reflection
    kind: spectral_radiance
    spectrum_file: astm_g173_scaled.csv
    temporal: uniform
  - name: dark_count
    kind: per_spad_rate
    rate_cps: 1000
  - name: internal_reflection
    kind: delayed_impulse
    delay_ns: 8.5
    mean_events_per_shot: 0.02
```

## 5. 串扰模型

基础版用矩阵 \(C_{ij}\) 表示源通道 j 的一次雪崩直接触发通道 i 的平均概率。考虑串扰级联时，总诱发雪崩期望为：

\[
C_{total}=(I-C)^{-1}-I
\]

要求 \(C\) 的谱半径小于 1。后续应拆成：

- SPAD 邻近像素的光学串扰（有空间方向和延迟分布）；
- 共享电源/淬灭/数字读出导致的电学串扰；
- Tx 泄漏、窗口反射和 Rx PSF 尾部造成的系统通道串扰。

三者的实验标定方法和时间特征不同，不应只用一个比例长期代替。

## 6. 建议的版本路线

### V0.1：快速测距评估（当前）

- 单角通道光子预算；
- 滤光片、背景、DCR；
- 首光子直方图、pile-up、TDC 与测距统计；
- 简化串扰矩阵。

### V0.2：线扫和二维 SPAD

- 导入 Tx profile 与 Rx PSF DB；
- 转镜角/时间轨迹；
- PSF 映射到二维面阵；
- 用户定义 binning matrix；
- 输出整条线的 range × channel 图。

### V0.3：读出电路真实性

- 非瘫痪/瘫痪死时间；
- SPAD 与 TDC 独立死时间；
- 多 SPAD 共享 TDC、仲裁和 FIFO；
- afterpulse、多级串扰、coincidence/gating；
- 高通量 Monte Carlo 与解析模型交叉验证。

### V0.4：标定和设计优化

- 用实测直方图拟合 PDE/DCR/jitter/crosstalk；
- 距离、反射率、环境光、温度和 binning 策略的批量扫描；
- 参数敏感度、容差和 Pareto 优化；
- 与实测数据自动回归。

## 7. 首版尚未覆盖的风险

- 当前朗伯方程要求输入的是当前角通道能量；若误填整条 VCSEL 线阵总能量，测距性能会明显高估。
- PDE、PDP 和 fill factor 的器件口径经常不同，需要确认数据手册定义。
- 太阳光不能只以 lux 描述；精确模型需要光谱、目标反射谱、滤光片和 PDE(λ) 的联合积分。
- 首光子架构的 pile-up 与多 hit/shared-TDC 架构差异很大，读出拓扑必须在 V0.2 前确定。
- 转镜扫描期间若目标像跨过多个 Tx/Rx 角样本，需要在脉冲级更新角度，不能仅用驻留中心角。

## 8. 文献锚点

- P. Padmanabhan, C. Zhang, E. Charbon, [Modeling and Analysis of a Direct Time-of-Flight Sensor Architecture for LiDAR Applications](https://doi.org/10.3390/s19245464), *Sensors*, 2019。适合共享 TDC、像素分组、coincidence、time-gating 和太阳背景下的系统架构分析。
- A. Incoronato, M. Locatelli, F. Zappa, [Statistical Modelling of SPADs for Time-of-Flight LiDAR](https://doi.org/10.3390/s21134481), *Sensors*, 2021。用于 hold-off、afterpulsing、crosstalk、TDC 死时间/共享及解析模型与 Monte Carlo 对照。
- K. Pasquinelli et al., [Single-Photon Detectors Modeling and Selection Criteria for High-Background LiDAR](https://doi.org/10.1109/JSEN.2020.2977775), *IEEE Sensors Journal*, 2020。用于高背景下 SPAD/APD/SiPM 比较和测距成功率定义。
- D. B. Lindell et al., [High-flux single-photon lidar](https://doi.org/10.1364/OPTICA.403190), *Optica*, 2021。用于 detector/electronics dead time、pile-up 和高通量恢复模型。
- [ASTM G173 reference solar spectral irradiance](https://www.nrel.gov/grid/solar-resource/spectra-am1.5)（NREL/NIST 标准参考数据入口）。后续精细太阳背景模型应采用光谱积分。
