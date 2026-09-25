# 回波、太阳光与其他环境光：光子预算计算链路

> 本文由 scripts/render-photon-budget-doc.py 生成。公式、变量说明与步骤分别来自 config/formulas.yaml、config/formula-notes.yaml 和 config/photon-flow.yaml；评估页和专家页使用同一数据源。

文档、评估页和专家调试页共用此定义。所有中间值由Python计算；公式用于解释，不从展示字符串执行模型。

网页在每一步显示当前数值和单位；本页定义公式与计算逻辑，不固化随用户工况变化的结果。

## 参考面与统计口径

- 回波按完整单脉冲计算；背景按单个记录门计算。进入入瞳、到达探测面、候选雪崩和最终记录是不同层次。
- 背景原始光子数限定在比较波段B：零漏光基础模型或采样模式采用滤光片形状域/采样范围；非零基础带外值扩展到提供的源光谱并受已知Rx响应范围约束。实际B明确记录，不一定是全光谱或滤光片FWHM。
- 信号使用目标激光反射率；太阳使用独立的太阳灰反射率；其他环境光已经是接收方向辐亮度，不再乘反射率或1/R²。
- 最终直方图是回波、太阳、其他光和器件噪声共同竞争后的混合记录，不按各来源的候选比例线性拆分。
- 数据随有效输入实时更新；实际观测直方图仍需点击运行。专家调试采用该次仿真的参数快照。

## 共同几何与单位

### 空间binning与每通道SPAD数

H、V分别记录聚合方向数量，乘积是计算核心唯一使用的总SPAD数。A版不根据H/V自动改变通道IFOV或总光学通量。

$$
N_{\mathrm{SPAD}}=H_{\mathrm{binning}}\times V_{\mathrm{binning}}
$$

**符号与单位：** H_binning/V_binning分别为水平/垂直聚合的SPAD数；乘积是每角通道总数N_SPAD，不能再独立编辑。A版只用总数均匀分配信号和光学背景，暗计数按总数增长；不自动改变通道IFOV，尚未模拟像素间距、PSF或空间非均匀照明。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 水平聚合数量 | SPAD | `H_binning` |
| 垂直聚合数量 | SPAD | `V_binning` |
| 派生的每通道总数 | SPAD/channel | `spad_count` |

### 共同几何与单位

先把尺寸、角度和时间换到所需单位。面积进入信号和背景；通道IFOV在A模型中决定背景收集立体角。信号能量已按角通道分配，不再额外乘IFOV。

$$
\begin{aligned}A_{\mathrm{Rx}}&=\begin{cases}\pi d^2/4&\text{circle}\\\pi WH/4&\text{ellipse}\\WH&\text{rectangle}\end{cases}\\\Omega&\simeq(\theta_H10^{-3})(\theta_V10^{-3})\\e_\gamma&=\frac{hc}{10^{-9}\lambda_{0,\mathrm{nm}}},\quad q(\lambda)=\frac{10^{-9}\lambda_{\mathrm{nm}}}{hc}\end{aligned}
$$

**符号与单位：** A_Rx为入瞳面积（m²）；d为圆直径，W/H为椭圆全轴或矩形宽高（公式按m，输入为mm）；θH/θV为通道全IFOV（输入mrad）；Ω为立体角（sr）。λ0,nm为激光波长（nm）；eγ为单光子能量（J）；q为每焦耳对应光子数（J⁻¹）；h、c为SI常数。背景后续积分变量dλ均以nm计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 接收入瞳面积 | m² | `aperture_m2` |
| 所选入瞳形状 | shape | `aperture_shape` |
| 所选形状尺寸（已换算） | m | `aperture_dimensions_m` |
| 水平通道全IFOV | mrad | `ifov_h_mrad` |
| 垂直通道全IFOV | mrad | `ifov_v_mrad` |
| 通道立体角 | sr | `omega_sr` |
| 记录门宽 | s | `gate_s` |
| 激光波长 | nm | `lambda_nm` |
| 激光单光子能量 | J | `photon_j` |
| 背景比较波段B起点 | nm | `band_min_nm` |
| 背景比较波段B终点 | nm | `band_max_nm` |

## 回波信号

### 发射、传播到目标与反射

输入为当前角通道Tx前的单脉冲能量；先经过Tx效率和去程大气透过率，再按灰朗伯目标的激光反射率反射。

$$
E_{\mathrm{Tx,out}}=E_0\eta_{\mathrm{Tx}},\quad E_{\mathrm{target}}=E_{\mathrm{Tx,out}}T_{\mathrm{atm}},\quad E_{\mathrm{refl}}=\rho_{\mathrm{laser}}E_{\mathrm{target}}
$$

**符号与单位：** E0是分配给当前角通道、Tx光学之前的单脉冲能量（J）；ηTx是发射光学效率；Tatm是单程大气透过率；ρlaser是激光目标反射率。Etarget是抵达目标的能量，Erefl是目标反射到半空间的总能量，不是全部朝Rx传播。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| Tx前角通道能量 | J/pulse | `echo_input_j` |
| Tx光学后能量 | J/pulse | `echo_tx_j` |
| Tx光学效率 | 1 | `tx_efficiency` |
| 目标面入射能量 | J/pulse | `echo_target_j` |
| 目标半空间总反射能量 | J/pulse | `echo_reflected_j` |
| 目标激光反射率 | 1 | `rho_laser` |
| 单程大气透过率 | 1 | `atmosphere` |

### 返回Rx入瞳

朗伯目标按A/(πR²)将反射能量分配到接收孔径，再计返回程透过率和重叠因子O。这里是该角通道有效入瞳能量。

$$
E_{\mathrm{Rx,in}}=E_{\mathrm{refl}}\frac{A_{\mathrm{Rx}}}{\pi R^2}T_{\mathrm{atm}}O,\qquad N_{\mathrm{Rx,in}}=\frac{E_{\mathrm{Rx,in}}}{e_\gamma}
$$

**符号与单位：** R为目标距离（m）；A_Rx/(πR²)为正入射朗伯目标的小孔径收集比例；再乘一次Tatm代表返回程，O为Tx/Rx重叠因子。E_Rx,in和N_Rx,in是含O的角通道有效入瞳能量/光子数，尚未乘Rx光学或滤光片透过率。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 目标距离 | m | `range_m` |
| 朗伯几何收集比例 | 1 | `geometry` |
| Tx/Rx重叠因子O | 1 | `overlap` |
| 有效进入Rx的信号能量 | J/pulse | `echo_rx_j` |
| 有效进入Rx的信号光子数 | photons/pulse | `echo_rx_photons` |

### 经过接收光学和滤光片

用激光波长处的透过率计算窄带回波光学损耗。到达感光面的光子还未必触发雪崩。

$$
E_{\mathrm{sensor}}=E_{\mathrm{Rx,in}}\eta_{\mathrm{Rx}}T_f(\lambda_0),\qquad N_{\mathrm{sensor}}=\frac{E_{\mathrm{sensor}}}{e_\gamma}
$$

**符号与单位：** ηRx为接收光学效率，Tf(λ0)为激光波长处滤光片透过率。E_sensor和N_sensor是到达探测面、PDE/FF之前的能量和光子数，按完整回波单脉冲计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| Rx光学效率 | 1 | `rx_efficiency` |
| 激光处滤光片透过率 | 1 | `filter_at_laser` |
| 到达探测面的信号能量 | J/pulse | `echo_sensor_j` |
| 到达探测面的信号光子数 | photons/pulse | `echo_sensor_photons` |

### PDE、FF、门控与累计

再乘感光区PDE与FF得到完整回波候选数。门内份额G由当前时间响应计算；保留门截断损失，不重新归一化。

$$
\mu_s=N_{\mathrm{sensor}}\mathrm{PDE}(\lambda_0)FF,\quad \mu_{s,\mathrm{gate}}=\mu_sG,\quad N_{s,\mathrm{ideal}}=N_{\mathrm{shots}}\mu_{s,\mathrm{gate}}
$$

**符号与单位：** PDE(λ0)为输入谱探测概率，FF为独立面积/系统折减，输入若已含整像素收集效率应避免重复计入；μs为完整回波每发候选数，尚未经过死时间/读出限制。G为时间响应落在门内的份额（理想IRF参考，含抖动）；Nshots为累计脉冲数。μs,gate与Ns,ideal是门内理想参考，不是实际记录数。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 激光处感光区PDE | 1 | `pde_at_laser` |
| FF | 1 | `fill_factor` |
| 完整回波期望候选数 | events/pulse | `echo_candidates_pulse` |
| 时间响应门内份额G（参考） | 1 | `echo_gate_fraction` |
| 门内候选数（理想参考） | events/pulse | `echo_candidates_gate` |
| 累计候选数（理想参考） | events | `echo_candidates_acquisition` |

## 太阳背景

### 标准/自定义太阳谱按lux归一化

用完整可见光谱与CIE V(λ)计算参考照度，再按目标面设置的lux缩放整条谱。不能只拿近红外波段换算lux。

$$
\begin{aligned}E_{v,\mathrm{ref}}&=683\int E_{\lambda,\mathrm{ref}}(\lambda)V(\lambda)\,d\lambda_{\mathrm{nm}}\\\alpha&=\begin{cases}u_{\mathrm{sun}}E_{v,\mathrm{set}}/E_{v,\mathrm{ref}},&E_{v,\mathrm{ref}}>0\\0,&E_{v,\mathrm{ref}}=0,\ u_{\mathrm{sun}}E_{v,\mathrm{set}}=0\end{cases}\\E_{\lambda,\mathrm{sun}}&=\alpha E_{\lambda,\mathrm{ref}}\end{aligned}
$$

**符号与单位：** Eλ,ref为所选太阳参考谱，V(λ)为CIE明视觉光谱光效率函数；683的单位为lm/W。Ev,ref是参考谱照度（lux）；Ev,set是用户设置的目标面太阳照度；u_sun为开关0/1。α缩放整条谱。标准谱为W/(m²·nm)，自定义谱可为相对值；正lux必须有非零可见光积分，否则报错。太阳关闭或lux=0时输出0。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 太阳开关 | bool | `solar_enabled` |
| 设置太阳照度 | lux | `solar_requested_lux` |
| 当前生效照度 | lux | `solar_actual_lux` |
| 参考谱照度 | lux | `solar_reference_lux` |
| 所选参考谱 | source | `solar_source` |
| 归一化前全谱积分（自定义为参考量） | W/m²或相对值 | `solar_reference_irradiance` |
| 参考谱缩放系数α | 1 | `solar_scale` |
| 缩放后的全谱辐照度 | W/m² | `solar_irradiance_w_m2` |

### 目标反射到接收方向

太阳背景灰反射率将目标面谱辐照度变为朝Rx的谱辐亮度。目标被视为填充本通道视场的均匀灰朗伯面，未模拟太阳直射镜头。

$$
L_{\mathrm{sun}}(\lambda)=\frac{\rho_{\mathrm{sun}}}{\pi}E_{\lambda,\mathrm{sun}}(\lambda)
$$

**符号与单位：** ρsun是太阳背景灰反射率，与激光目标反射率分别设置。太阳谱辐照度经灰朗伯面反射转换为朝Rx的谱辐亮度Lsun，单位W/(m²·sr·nm)。灰表示反射率不随波长变化；本链不描述太阳盘直视。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 太阳灰反射率 | 1 | `rho_solar` |
| 激光波长处太阳谱辐照度 | W/(m²·nm) | `solar_irradiance_at_laser` |
| 激光波长处反射谱辐亮度 | W/(m²·sr·nm) | `solar_radiance_at_laser` |

### 进入Rx入瞳（光学损耗前）

在同一个比较波段B内积分。均匀场景辐亮度乘面积和立体角得到功率，逐波长换算光子数再乘门宽。

$$
\begin{aligned}P_{\mathrm{Rx,in},j}&=A_{\mathrm{Rx}}\Omega\int_B L_j(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{\mathrm{Rx,in},j}&=A_{\mathrm{Rx}}\Omega T_{\mathrm{gate}}\int_B L_j(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\end{aligned}
$$

**符号与单位：** j代表当前来源sun或other；Lj为该来源的谱辐亮度。B是本次明确声明的比较波段（取滤光片配置有效域），q(λ)=10⁻⁹λnm/(hc)。P_Rx,in为进入入瞳的带内功率（W），N_Rx,in为一个记录门内进入入瞳的原始光子数；均未计光学、滤光片、PDE或FF。不代表全光谱总量。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 进入Rx的带内功率 | W | `solar_rx_power_w` |
| 每门进入Rx的带内光子数 | photons/gate | `solar_rx_photons_gate` |

### 到达探测面（PDE/FF前）

接收光学效率与滤光片透过率衰减后，得到到达整个探测面的光功率和光子数。PDE与FF尚未加入。

$$
\begin{aligned}P_{\mathrm{sensor},j}&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}\int_B L_j(\lambda)T_f(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{\mathrm{sensor},j}&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}T_{\mathrm{gate}}\int_B L_j(\lambda)T_f(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\end{aligned}
$$

**符号与单位：** 同一波段B上，ηRx和Tf分别描述接收光学及滤光片。P_sensor为探测面光功率（W）；N_sensor为每门到达探测面的光子数，尚未乘PDE和FF。Tgate须以s代入。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| Rx光学效率 | 1 | `rx_efficiency` |
| 探测面背景光功率 | W | `solar_sensor_power_w` |
| 每门到达探测面的光子数 | photons/gate | `solar_sensor_photons_gate` |

### SPAD候选事件与累计数

PDE按波长放在积分内，FF只乘一次。候选事件随后进入SPAD与读出模型；这些候选数不是最终时间戳数。

$$
\begin{aligned}\mu_j&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}T_{\mathrm{gate}}FF\\&\quad\cdot\int_B L_j(\lambda)T_f(\lambda)\mathrm{PDE}(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{j,\mathrm{ideal}}&=N_{\mathrm{shots}}\mu_j\\\bar n_{j,\mathrm{bin}}&=\dot N_{j,\mathrm{candidate}}\Delta t_{\mathrm{bin}}\end{aligned}
$$

**符号与单位：** PDE(λ)在积分内逐波长参与计算；FF在积分外乘一次。μj是当前背景来源的每门期望雪崩候选数，Nj,ideal是累计Nshots发的候选总数。实际输出还会受到SPAD恢复、OR/符合逻辑和TDC限制。 每time_bin解析值直接由PDE/FF后的候选计数率乘分箱时长得到，不进行随机统计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 填充因子 | 1 | `fill_factor` |
| 每门期望雪崩候选数 | events/gate | `solar_candidates_gate` |
| 本次累计的理想候选数 | events | `solar_candidates_acquisition` |
| 累计脉冲数 | shots | `shots` |
| 每time_bin平均探测候选数（单角通道） | candidates/bin | `solar_mean_candidates_per_time_bin` |

## 其他环境光

### 直接输入接收方向的谱辐亮度

基础函数或采样点插值得到Linput，乘开关和强度倍率。这里不是灯的总功率，也不是目标面的谱辐照度；如果来源是这两者，须在外部先处理几何传播与反射。

$$
L_{\mathrm{other}}(\lambda)=u_{\mathrm{other}}\,m_{\mathrm{other}}\,L_{\mathrm{input}}(\lambda)
$$

**符号与单位：** Linput是用户基础函数或CSV/手动点插值得到的接收方向谱辐亮度（W/m²/sr/nm）；u_other为开关0/1，m_other为强度倍率。输入已代表场景朝Rx的亮度，不再乘目标反射率、1/R²或太阳lux换算。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 其他光开关 | bool | `other_enabled` |
| 其他光倍率 | 1 | `other_scale` |
| 输入谱在激光波长处的原始值 | W/(m²·sr·nm) | `other_raw_radiance_at_laser` |
| 倍率/开关作用后谱辐亮度 | W/(m²·sr·nm) | `other_radiance_at_laser` |

### 进入Rx入瞳（光学损耗前）

在同一个比较波段B内积分。均匀场景辐亮度乘面积和立体角得到功率，逐波长换算光子数再乘门宽。

$$
\begin{aligned}P_{\mathrm{Rx,in},j}&=A_{\mathrm{Rx}}\Omega\int_B L_j(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{\mathrm{Rx,in},j}&=A_{\mathrm{Rx}}\Omega T_{\mathrm{gate}}\int_B L_j(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\end{aligned}
$$

**符号与单位：** j代表当前来源sun或other；Lj为该来源的谱辐亮度。B是本次明确声明的比较波段（取滤光片配置有效域），q(λ)=10⁻⁹λnm/(hc)。P_Rx,in为进入入瞳的带内功率（W），N_Rx,in为一个记录门内进入入瞳的原始光子数；均未计光学、滤光片、PDE或FF。不代表全光谱总量。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 进入Rx的带内功率 | W | `other_rx_power_w` |
| 每门进入Rx的带内光子数 | photons/gate | `other_rx_photons_gate` |

### 到达探测面（PDE/FF前）

接收光学效率与滤光片透过率衰减后，得到到达整个探测面的光功率和光子数。PDE与FF尚未加入。

$$
\begin{aligned}P_{\mathrm{sensor},j}&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}\int_B L_j(\lambda)T_f(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{\mathrm{sensor},j}&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}T_{\mathrm{gate}}\int_B L_j(\lambda)T_f(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\end{aligned}
$$

**符号与单位：** 同一波段B上，ηRx和Tf分别描述接收光学及滤光片。P_sensor为探测面光功率（W）；N_sensor为每门到达探测面的光子数，尚未乘PDE和FF。Tgate须以s代入。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| Rx光学效率 | 1 | `rx_efficiency` |
| 探测面背景光功率 | W | `other_sensor_power_w` |
| 每门到达探测面的光子数 | photons/gate | `other_sensor_photons_gate` |

### SPAD候选事件与累计数

PDE按波长放在积分内，FF只乘一次。候选事件随后进入SPAD与读出模型；这些候选数不是最终时间戳数。

$$
\begin{aligned}\mu_j&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}T_{\mathrm{gate}}FF\\&\quad\cdot\int_B L_j(\lambda)T_f(\lambda)\mathrm{PDE}(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{j,\mathrm{ideal}}&=N_{\mathrm{shots}}\mu_j\\\bar n_{j,\mathrm{bin}}&=\dot N_{j,\mathrm{candidate}}\Delta t_{\mathrm{bin}}\end{aligned}
$$

**符号与单位：** PDE(λ)在积分内逐波长参与计算；FF在积分外乘一次。μj是当前背景来源的每门期望雪崩候选数，Nj,ideal是累计Nshots发的候选总数。实际输出还会受到SPAD恢复、OR/符合逻辑和TDC限制。 每time_bin解析值直接由PDE/FF后的候选计数率乘分箱时长得到，不进行随机统计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 填充因子 | 1 | `fill_factor` |
| 每门期望雪崩候选数 | events/gate | `other_candidates_gate` |
| 本次累计的理想候选数 | events | `other_candidates_acquisition` |
| 累计脉冲数 | shots | `shots` |
| 每time_bin平均探测候选数（单角通道） | candidates/bin | `other_mean_candidates_per_time_bin` |

## 候选输入到实际读出

### 合并候选输入，再经过读出

光学候选数加上DCR和其他电子噪声，按当前读出架构生成实际时间戳。事件模式会处理SPAD/TDC死时间、OR、符合检测及容量；解析参考使用理想首光子分布。

$$
\begin{aligned}\mu_{\mathrm{noise}}&=\mu_{\mathrm{sun}}+\mu_{\mathrm{other}}+\mu_{\mathrm{DCR}}+\mu_{\mathrm{electronic}}\\\mu_{\mathrm{DCR}}&=\mathrm{DCR}\,N_{\mathrm{SPAD}}T_{\mathrm{gate}}\\N_{\mathrm{recorded}}&=\sum_k H_k\end{aligned}
$$

**符号与单位：** μsun/μother分别为太阳和其他环境光候选数；μDCR和μelectronic为器件暗计数及其他电子随机噪声（它们不乘PDE/FF）。N_SPAD为物理SPAD数。Hk为实际观测直方图第k个bin计数，Nrecorded为混合记录总数；不同来源会竞争，不能按线性比例拆分最终记录。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 每门DCR候选数 | events/gate | `dark_gate` |
| 每门其他电子噪声候选数 | events/gate | `electronic_gate` |
| 每门全部光学背景候选数 | events/gate | `background_gate` |
| 每门总噪声候选数 | events/gate | `noise_gate` |
| 读出模式 | mode | `readout_mode` |

## B 全光斑：入瞳、探测面、候选雪崩与混合记录

Tx全光斑按角度单元分配，Rx效率与PSF将能量映射到真实像素；光子预算由Python计算。构造光学样例不代表实测器件或实际光学系统。

### Tx：配置角域内归一化与能量分配

输入单发能量定义于配置Tx角域内、Tx光学之前。高斯、均匀及导入Tx份额在该角域内归一化；只乘一次Tx光学效率，不额外扣除角域外能量。

$$
\begin{aligned}w_a&=\frac{q_a}{\sum_{b\in\mathcal D}q_b},\qquad \sum_{a\in\mathcal D}w_a=1\\E_{a,\mathrm{Tx,out}}&=E_{\mathcal D,\mathrm{Tx,in}}\eta_{\mathrm{Tx}}w_a\end{aligned}
$$

**符号与单位：** D为配置Tx角域；q为角单元内的积分形状权重（无量纲，不能全部为零），w为域内归一化份额。E_D,Tx,in为用户输入的域内单发能量（公式用J，界面用nJ），η_Tx为Tx光学效率。域内Tx后能量合计等于输入能量乘效率，不再扣除角域外能量；Rx像面与时间门损失仍分别计算。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 角域内Tx前单发能量 | J/pulse | `tx_input_j` |
| 角域内份额合计 | 1 | `tx_angular_coverage_fraction` |
| 角域内Tx后单发能量 | J/pulse | `tx_domain_output_j` |

### 回波：角度能量经过Rx映射到像素

先计算各角度单元入瞳能量，再分别乘Rx效率、滤光片及PSF像素份额。入射信号光子仍未乘PDE/FF。

$$
N_{i,\mathrm{sensor}}^{s}=\frac{1}{hc/\lambda_0}\sum_a E_{a,\mathrm{pupil}}\,\eta_{a}(\lambda_0)\,T_f(\lambda_0)\,p_{ai}(\lambda_0)
$$

**符号与单位：** a为角度单元，i为物理像素；入瞳能量E单位J，η为入瞳到无限像面的收光效率，Tf为滤光透过率，p为完整像素截获无限PSF的能量份额。p按像素积分，边缘截断后不再归一化。λ使用m，输出为每完整脉冲、PDE/FF前的光子数。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 角域内Tx前能量 | J/pulse | `tx_input_j` |
| 回波入瞳光子 | photons/pulse | `signal_rx_incident_photons_per_pulse` |
| 回波探测面光子 | photons/pulse | `signal_sensor_incident_photons_per_pulse` |

### 太阳：按明确波段积分并映射到像素

太阳光谱沿用标准谱或选定输入模式及lux归一化；背景角域由当前Tx角单元网格覆盖范围明确限定，不乘Tx能量权重。

$$
N_{i,\mathrm{sensor}}^{b}=T_{\mathrm{gate}}A_r\int_{\mathcal B}\sum_a L_{a,\lambda}^{b}\,\Delta\Omega_a\,\eta_a(\lambda)\,T_f(\lambda)\,p_{ai}(\lambda)\frac{\lambda}{hc}\,\mathrm{d}\lambda
$$

**符号与单位：** b分别表示太阳或其他环境光；L为W/(m²·sr·m)谱辐亮度，ΔΩ为sr，门宽为s。显示/输入可用每nm谱密度，Python积分采用相配的nm权重与波长到m换算。积分波段B明确记录；输出为完整像素、PDE/FF前的每门光子数。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 太阳入瞳光子（限定积分波段） | photons/gate | `solar_rx_incident_photons_per_gate` |
| 太阳Rx效率后光子 | photons/gate | `solar_after_rx_photons_per_gate` |
| 太阳滤光后无限像面光子 | photons/gate | `solar_after_filter_fullplane_photons_per_gate` |
| 太阳探测面光子 | photons/gate | `solar_sensor_incident_photons_per_gate` |
| 太阳每time_bin平均探测候选数（全阵列，含PDE/FF） | candidates/bin | `solar_mean_candidates_per_time_bin` |

### 其他环境光：独立输入谱的空间积分

其他光输入已经是接收方向谱辐亮度；不再额外乘目标反射率。背景原始光子数同样限定当前积分波段。

$$
N_{i,\mathrm{sensor}}^{b}=T_{\mathrm{gate}}A_r\int_{\mathcal B}\sum_a L_{a,\lambda}^{b}\,\Delta\Omega_a\,\eta_a(\lambda)\,T_f(\lambda)\,p_{ai}(\lambda)\frac{\lambda}{hc}\,\mathrm{d}\lambda
$$

**符号与单位：** b分别表示太阳或其他环境光；L为W/(m²·sr·m)谱辐亮度，ΔΩ为sr，门宽为s。显示/输入可用每nm谱密度，Python积分采用相配的nm权重与波长到m换算。积分波段B明确记录；输出为完整像素、PDE/FF前的每门光子数。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 其他光入瞳光子（限定积分波段） | photons/gate | `other_rx_incident_photons_per_gate` |
| 其他光Rx效率后光子 | photons/gate | `other_after_rx_photons_per_gate` |
| 其他光滤光后无限像面光子 | photons/gate | `other_after_filter_fullplane_photons_per_gate` |
| 其他光探测面光子 | photons/gate | `other_sensor_incident_photons_per_gate` |
| 其他环境光每time_bin平均探测候选数（全阵列，含PDE/FF） | candidates/bin | `other_mean_candidates_per_time_bin` |

### 器件转换与最终混合记录

PDE/FF转换后再由共用SPAD及读出核心处理DCR、恢复和竞争。最终记录是所有来源混合的结果，不能按候选比例线性拆分。

$$
\mu_i=\int_{\mathcal B}N_{i,\lambda}\,\mathrm{PDE}(\lambda)\,FF\,\mathrm{d}\lambda
$$

**符号与单位：** N为探测面光子谱密度；PDE与FF由器件模块应用一次，得到死时间与读出之前的候选雪崩期望。离散光谱实现使用已包含积分权重的单元光子数。DCR及其他电子候选另行加入。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 回波候选雪崩期望 | candidates/pulse | `signal_candidate_avalanches_per_pulse` |
| 太阳候选雪崩期望 | candidates/gate | `solar_candidate_avalanches_per_gate` |
| 其他光候选雪崩期望 | candidates/gate | `other_candidate_avalanches_per_gate` |
| 本次采集最终混合记录 | records/acquisition | `final_mixed_records` |

### 接收能量守恒与边缘损失

不通过PSF重新归一化补偿感光面外能量。守恒残差保留浮点误差，所有损耗参考面分别列出。

$$
E_{\mathrm{pupil}}=E_{\mathrm{sensor}}+E_{\mathrm{Rx\,loss}}+E_{\mathrm{filter\,loss}}+E_{\mathrm{edge\,loss}}
$$

**符号与单位：** 所有项单位J、按完整单脉冲计算。Rx损耗、滤光损耗、感光面边缘截断分别审计。Tx单发能量定义于配置角域内，角域份额归一化，不额外扣除角域外能量。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 入瞳信号能量 | J/pulse | `rx_pupil_signal_j` |
| 探测面信号能量 | J/pulse | `sensor_signal_j` |
| Rx效率损失 | J/pulse | `rx_loss_j` |
| 滤光损失 | J/pulse | `filter_loss_j` |
| PSF感光面边缘损失 | J/pulse | `psf_edge_loss_j` |
| 能量平衡残差 | J/pulse | `energy_balance_residual_j` |

## C 逐脉冲扫描：时序、实际发数与光子审计

扫描只组装逐发光学输入和控制时序；所有脉冲共享同一SPAD/读出状态。下列总量按完整测量帧的参考时隙统计，不代表检测成功率。

### 扫描与发射时序

单发能量定义于Tx角域内并按域内份额归一化。PRF生成名义触发时隙；帧预算决定时隙数。激光偏移/抖动改变实际发射时刻，机械角经倍率映射为光学角。

$$
t_k=kT_{\mathrm{PRF}}+\delta t+\epsilon_k,\qquad \theta_{\mathrm{opt}}(t)=g\,\theta_{\mathrm{mech}}(t)+\theta_0
$$

**符号与单位：** T_PRF为名义触发周期；δt为激光固定时序偏移，εk为保存seed的高斯时间扰动。公式中的时间采用s，界面和事件时钟以ns保存并在物理计算入口换算。g为机械到光学角倍率；配置角度为mrad。实际发射、控制参考和编码器读数分别保存。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 总测量帧时长 | ns | `duration_ns` |
| 名义触发时隙 | slots | `scheduled_slots` |
| 实际启用发射的测量参考时隙 | pulses | `emitted_reference_slots` |
| 测量参考时隙Tx前能量合计 | J | `reference_tx_input_energy_j` |
| 测量参考时隙角域内Tx后能量 | J | `reference_tx_domain_output_j` |

### 有限测量时间窗内的Tx功率

脉冲中心计数与实际时间积分分别记录。高斯/矩形波形在帧边界可能只有部分能量落入时间窗；这里积分时间波形，不补回边界能量。

$$
\bar P_{\mathrm{Tx}}=\frac{1}{T_{\mathrm{obs}}}\sum_k E_{k,\mathrm{Tx}}\int_0^{T_{\mathrm{obs}}}s_k(t-t_k)\,\mathrm{d}t
$$

**符号与单位：** tk为真实脉冲中心，sk为积分归一化的发射时间波形(1/s)，Ek,Tx为Tx后完整脉冲能量(J)。所有时间在公式中采用s。求和覆盖本次有限预热与测量计划中启用的源脉冲；只积分观察时间窗内的部分。中心落在窗内的发数乘完整能量另列，不等同有限时间窗积分功率。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 中心位于测量窗内的完整脉冲计账能量 | J | `center_accounted_tx_output_energy_j` |
| 测量时间窗内积分Tx后能量 | J | `actual_tx_output_energy_j` |
| 测量时间窗内积分Tx后平均功率 | W | `actual_tx_average_power_w` |

### 角bin累计数

编码器分配发数用于测量结果重建；真实有效发数是独立真值诊断。回扫、域外脉冲和空bin不补齐。

$$
N_{f,b}=\sum_k \mathbf{1}\{k\text{ is eligible},\ t_k\in F_f,\ \theta_k\in B_b\}
$$

**符号与单位：** F为半开时间帧，B为半开角bin。分别使用真实发射时间/角度和可观测编码器/参考时钟计算真实有效发数与分配发数，二者不可混用。静止、非匀速及边界情形均采用离散求和，不用驻留近似填补。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 分配到角bin的发数 | pulses | `assigned_pulses` |
| 真实有效角bin发数 | pulses | `true_useful_pulses` |

### 回波：逐发Rx指向与光子求和

每发在实际发射角照射场景，在各回波到达中心计算Rx指向与PSF。反射距离允许随全局H角和径向运动变化。

$$
t_{\mathrm{return},ka}=t_k+2R_{ka}/c,\qquad \theta_{\mathrm{Rx},ka}=\theta_{\mathrm{Tx}}(t_k)+\alpha_a-\theta_{\mathrm{Rx\,axis}}(t_{\mathrm{return},ka})
$$

**符号与单位：** a为Tx局部角单元，αa为其局部光学角；Rka为目标反射位置距离。公式中的t_k和t_return以s计，代码显式换算为ns；Rx指向在每个角单元回波中心到达时求值。该式不把电子标定延迟当成光程；有限脉宽内的扫描位移暂未展开。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 测量发射的目标入射能量 | J | `target_incident_j` |
| 测量发射的目标反射能量 | J | `target_reflected_j` |
| 信号入瞳光子总数 | photons/acquisition | `signal_pupil_photons_total` |
| 信号探测面光子总数 | photons/acquisition | `signal_sensor_photons_total` |
| 信号候选雪崩期望总数 | candidates/acquisition | `signal_candidates_total` |

### 构造场景：角向距离与径向运动

逐角单元计算真实反射距离，再确定回波时刻和Rx姿态。真值距离仅用于生成光子与误差审计，不交给距离估计器寻峰。

$$
R_{ka}=\frac{R_0+g_R\theta_{ka}+v t_k}{1-v/c}
$$

**符号与单位：** R为反射位置的径向距离(m)，R0为t=0、全局H=0处的距离；gR为m/rad梯度，θ为全局H角(rad)，v为径向速度(m/s)，tk为实际发射时刻(s)。分母来自恒速目标与出射光的截获关系。该构造模型不包含遮挡、横向运动、目标法线变化或多普勒谱移。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 测量发射的最小反射距离 | m | `reflection_range_min_m` |
| 测量发射的最大反射距离 | m | `reflection_range_max_m` |

### 太阳：记录门实际曝光

背景按接收机局部角域与明确波段积分。发射关闭不会自动关闭SPAD/TDC周期门。

$$
N_{\mathrm{sensor}}^{b}=\left(\sum_k T_{\mathrm{gate},k}\right)\dot N_{\mathrm{sensor}}^{b}
$$

**符号与单位：** 背景在接收机局部角域内假定均匀平稳。每个有效记录门的实际长度相加，包含回扫期间仍运行的周期门；最后截断门按真实时长计。原始光子积分波段明确列出。free_running门外背景也参与器件状态，其候选量另见采样审计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 所有记录门实际时长之和 | s | `gate_exposure_s` |
| 太阳入瞳光子（限定波段） | photons/acquisition | `solar_rx_incident_photons_total` |
| 太阳探测面光子 | photons/acquisition | `solar_sensor_incident_photons_total` |
| 太阳门内候选雪崩期望 | candidates/acquisition | `solar_candidate_avalanches_total` |
| 太阳每time_bin平均探测候选数（全阵列） | candidates/bin | `solar_mean_candidates_per_time_bin` |

### 其他环境光：独立积分

只使用当前环境光谱输入模式。原始光子数限定显示波段；不随Tx能量份额缩放。

$$
N_{\mathrm{sensor}}^{b}=\left(\sum_k T_{\mathrm{gate},k}\right)\dot N_{\mathrm{sensor}}^{b}
$$

**符号与单位：** 背景在接收机局部角域内假定均匀平稳。每个有效记录门的实际长度相加，包含回扫期间仍运行的周期门；最后截断门按真实时长计。原始光子积分波段明确列出。free_running门外背景也参与器件状态，其候选量另见采样审计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 其他光入瞳光子（限定波段） | photons/acquisition | `other_rx_incident_photons_total` |
| 其他光探测面光子 | photons/acquisition | `other_sensor_incident_photons_total` |
| 其他光门内候选雪崩期望 | candidates/acquisition | `other_candidate_avalanches_total` |
| 其他环境光每time_bin平均探测候选数（全阵列） | candidates/bin | `other_mean_candidates_per_time_bin` |

### 整次接收能量与最终混合记录

能量等式对测量参考时隙中启用发射的脉冲求和。最终记录包含源间竞争；角bin重建可以进一步排除回扫或域外记录。

$$
E_{\mathrm{pupil}}=E_{\mathrm{sensor}}+E_{\mathrm{Rx\,loss}}+E_{\mathrm{filter\,loss}}+E_{\mathrm{edge\,loss}}
$$

**符号与单位：** 所有项单位J、按完整单脉冲计算。Rx损耗、滤光损耗、感光面边缘截断分别审计。Tx单发能量定义于配置角域内，角域份额归一化，不额外扣除角域外能量。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 入瞳信号能量合计 | J | `pupil_energy_j` |
| 探测面信号能量合计 | J | `sensor_energy_j` |
| Rx损耗合计 | J | `rx_loss_j` |
| 滤光损耗合计 | J | `filter_loss_j` |
| 阵列外损耗合计 | J | `edge_loss_j` |
| 能量平衡残差 | J | `energy_balance_residual_j` |
| 全采集混合记录 | records | `final_mixed_records` |
| 进入角bin重建的记录 | records | `angle_assigned_records` |

## C 列级扫描：逐发列表、门并集、光学与器件审计

高层分配列时隙，每列按显式时间/能量列表发射。所有候选经过相同SPAD核心，最终混合记录不按源比例拆分。

### 列目标与逐发列表

高层确定帧/列节拍；列表确定列内波形中心与能量。名义参考、实际发射和编码器角标签分开记录，不把列数当发数。

$$
t_{f,c,i}=fT_{\mathrm{frame}}+cT_{\mathrm{slot}}+\tau_i+\delta t+\epsilon_{f,c,i},\qquad E_{f,c,i}=E_i
$$

**符号与单位：** f为帧序号，c为列序号，i为列内发射序号；tau_i是列内波形中心相对时间，E_i为本发Tx前全光斑能量。时间公式用s，输入/事件时钟用ns显式换算。delta t为激光偏移，epsilon为已保存seed的抖动。零能量是暗触发；首发延迟或空列表时列起点有无光参考锚点。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 事件观测时域长度（整帧或显式选区） | ns | `duration_ns` |
| 点云列数量 | columns | `column_count` |
| 列表触发次数（含暗触发） | triggers | `trigger_count` |
| 实际启用发射的测量参考时隙 | pulses | `emitted_reference_slots` |
| 测量参考时隙Tx前能量合计 | J | `reference_tx_input_energy_j` |
| 测量参考时隙角域内Tx后能量 | J | `reference_tx_domain_output_j` |

### 有限测量时间窗内的Tx功率

逐发能量允许不同，各发能量属于配置Tx角域，角度份额归一化且不扣角域外能量；对包含可选归一化拖尾的完整时间分布积分。名义测量列的完整脉冲能量、实际中心计数与观测时间窗能量分别审计，不补回边界尾部。

$$
\bar P_{\mathrm{Tx}}=\frac{1}{T_{\mathrm{obs}}}\sum_k E_{k,\mathrm{Tx}}\int_0^{T_{\mathrm{obs}}}s_k(t-t_k)\,\mathrm{d}t
$$

**符号与单位：** tk为真实脉冲中心，sk为积分归一化的发射时间波形(1/s)，Ek,Tx为Tx后完整脉冲能量(J)。所有时间在公式中采用s。求和覆盖本次有限预热与测量计划中启用的源脉冲；只积分观察时间窗内的部分。中心落在窗内的发数乘完整能量另列，不等同有限时间窗积分功率。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 中心位于测量窗内的完整脉冲计账能量 | J | `center_accounted_tx_output_energy_j` |
| 测量时间窗内积分Tx后能量 | J | `actual_tx_output_energy_j` |
| 测量时间窗内积分Tx后平均功率 | W | `actual_tx_average_power_w` |

### 参考时钟归属与门并集

记录依据触发/列锚点参考归档，不读取隐藏的光子来源。并集门避免重复背景曝光；跨列器件状态连续。

$$
r(t)=\max\{j:t^{\mathrm{ref}}_j\leq t\},\qquad c_{\mathrm{record}}=c_{r(t)},\qquad G(t)=\mathbf{1}_{t\in\bigcup_j G_j}
$$

**符号与单位：** t为内部读出触发判定时刻；r为最近的名义触发/列锚点参考，c为该参考所属列。后续电子时间抖动不借助源身份更改归属。G是所有名义接收门的并集，重叠只曝光一次；窗口内门碎片保持同一容量参考周期。SPAD恢复与TDC忙碌不会因换列重置；容量计数按显式参考周期管理。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 有列表项的触发参考数 | triggers | `trigger_count` |
| 测量门并集曝光时间 | s | `gate_exposure_s` |

### 回波：逐发Rx指向与光子求和

世界方向与接收机局部方向使用三维旋转。B的Rx效率/PSF在局部角度查询，再将探测面光子交给共同器件模型。

$$
\begin{aligned}t_{\mathrm{return},ka}&=t_k+2R_{ka}/c\\\mathbf d_{\mathrm{world},ka}&=R_y(\theta_{\mathrm{Tx}}(t_k))\mathbf d_a\\\mathbf d_{\mathrm{Rx},ka}&=R_y(-\theta_{\mathrm{Rx\,axis}}(t_{\mathrm{return},ka}))\mathbf d_{\mathrm{world},ka}\end{aligned}
$$

**符号与单位：** d_a方向正比于(tan H,tan V,1)，Ry为绕垂直轴的旋转。分别在发射中心和回波中心查询姿态，Rx局部H/V由对应向量x/z、y/z的atan2计算；全局120deg扫描不作为Rx局部小角度输入。时间使用s、角量rad，代码显式换算ns/mrad。光学不包含电子标定延迟；有限脉宽/长拖尾内的连续扫描拖影尚未解析。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 测量发射的目标入射能量 | J | `target_incident_j` |
| 测量发射的目标反射能量 | J | `target_reflected_j` |
| 信号入瞳光子总数 | photons/acquisition | `signal_pupil_photons_total` |
| 信号探测面光子总数 | photons/acquisition | `signal_sensor_photons_total` |
| 信号候选雪崩期望总数 | candidates/acquisition | `signal_candidates_total` |

### 构造场景：角向距离与径向运动

逐角单元计算真实反射距离，再确定回波时刻和Rx姿态。真值距离仅用于生成光子与误差审计，不交给距离估计器寻峰。

$$
R_{ka}=\frac{R_0+g_R\theta_{ka}+v t_k}{1-v/c}
$$

**符号与单位：** R为反射位置的径向距离(m)，R0为t=0、全局H=0处的距离；gR为m/rad梯度，θ为全局H角(rad)，v为径向速度(m/s)，tk为实际发射时刻(s)。分母来自恒速目标与出射光的截获关系。该构造模型不包含遮挡、横向运动、目标法线变化或多普勒谱移。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 测量发射的最小反射距离 | m | `reflection_range_min_m` |
| 测量发射的最大反射距离 | m | `reflection_range_max_m` |

### 太阳：记录门实际曝光

太阳背景按Rx局部角域和指定积分波段积分。此处报告记录门并集内量；free_running门外背景还参与器件状态，见候选采样审计。

$$
N_{\mathrm{sensor}}^{b}=\left(\sum_k T_{\mathrm{gate},k}\right)\dot N_{\mathrm{sensor}}^{b}
$$

**符号与单位：** 背景在接收机局部角域内假定均匀平稳。每个有效记录门的实际长度相加，包含回扫期间仍运行的周期门；最后截断门按真实时长计。原始光子积分波段明确列出。free_running门外背景也参与器件状态，其候选量另见采样审计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 所有记录门实际时长之和 | s | `gate_exposure_s` |
| 太阳入瞳光子（限定波段） | photons/acquisition | `solar_rx_incident_photons_total` |
| 太阳探测面光子 | photons/acquisition | `solar_sensor_incident_photons_total` |
| 太阳门内候选雪崩期望 | candidates/acquisition | `solar_candidate_avalanches_total` |
| 太阳每time_bin平均探测候选数（全阵列） | candidates/bin | `solar_mean_candidates_per_time_bin` |

### 其他环境光：独立积分

只使用当前环境光谱输入模式。原始光子数限定显示波段；不随Tx能量份额缩放。

$$
N_{\mathrm{sensor}}^{b}=\left(\sum_k T_{\mathrm{gate},k}\right)\dot N_{\mathrm{sensor}}^{b}
$$

**符号与单位：** 背景在接收机局部角域内假定均匀平稳。每个有效记录门的实际长度相加，包含回扫期间仍运行的周期门；最后截断门按真实时长计。原始光子积分波段明确列出。free_running门外背景也参与器件状态，其候选量另见采样审计。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 其他光入瞳光子（限定波段） | photons/acquisition | `other_rx_incident_photons_total` |
| 其他光探测面光子 | photons/acquisition | `other_sensor_incident_photons_total` |
| 其他光门内候选雪崩期望 | candidates/acquisition | `other_candidate_avalanches_total` |
| 其他环境光每time_bin平均探测候选数（全阵列） | candidates/bin | `other_mean_candidates_per_time_bin` |

### 整次接收能量与最终混合记录

接收能量等式对测量列源脉冲求和；器件输出保留全部混合记录，分析时间窗口可再排除区间外记录。DSP/MIPI丢列另报，不更改离线探测记录。

$$
E_{\mathrm{pupil}}=E_{\mathrm{sensor}}+E_{\mathrm{Rx\,loss}}+E_{\mathrm{filter\,loss}}+E_{\mathrm{edge\,loss}}
$$

**符号与单位：** 所有项单位J、按完整单脉冲计算。Rx损耗、滤光损耗、感光面边缘截断分别审计。Tx单发能量定义于配置角域内，角域份额归一化，不额外扣除角域外能量。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 入瞳信号能量合计 | J | `pupil_energy_j` |
| 探测面信号能量合计 | J | `sensor_energy_j` |
| Rx损耗合计 | J | `rx_loss_j` |
| 滤光损耗合计 | J | `filter_loss_j` |
| 阵列外损耗合计 | J | `edge_loss_j` |
| 能量平衡残差 | J | `energy_balance_residual_j` |
| 全采集混合记录 | records | `final_mixed_records` |
| 进入列内时间分析窗口的记录 | records | `angle_assigned_records` |

## 对照代码与模型边界

- simulator.py / photon_budget：分阶段回波能量、入瞳光子、探测面光子与各来源候选数。
- spectra.py / spectral_components：太阳lux归一化、反射、其他光倍率、同波段分层光谱积分。
- photon_flow.py：将真实中间量绑定到共享步骤定义；不从LaTeX执行计算。
- readout.py：候选事件经过死时间、OR/符合/TDC限制，得到混合直方图。
- 太阳反射假定灰朗伯面；其他光输入已经是接收方向辐亮度。光学入瞳、通道视场、PDE/FF的适用范围见同目录模型说明。
- 回波门内份额G是理想IRF参考。事件模式中的门控与电子时间抖动可能带来不同的边缘损失，以实际读出审计为准。
- 背景原始计数使用B波段作分层对照；波段外的光子没有被这张预算表计入，不应把它解释为硬件已经拒收。

运行 `python scripts/render-photon-budget-doc.py --check` 可检测此文档是否与共享定义一致。更新定义后运行不带参数的脚本输出新版Markdown，并更新本文件。
