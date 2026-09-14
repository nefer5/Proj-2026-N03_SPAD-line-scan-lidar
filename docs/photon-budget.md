# 回波、太阳光与其他环境光：光子预算计算链路

> 本文由 scripts/render-photon-budget-doc.py 生成。公式、变量说明与步骤分别来自 config/formulas.yaml、config/formula-notes.yaml 和 config/photon-flow.yaml；评估页和专家页使用同一数据源。

文档、评估页和专家调试页共用此定义。所有中间值由Python计算；公式用于解释，不从展示字符串执行模型。

网页在每一步显示当前数值和单位；本页定义公式与计算逻辑，不固化随用户工况变化的结果。

## 参考面与统计口径

- 回波按完整单脉冲计算；背景按单个记录门计算。进入入瞳、到达探测面、候选雪崩和最终记录是不同层次。
- 背景原始光子数限定在比较波段B：采用当前滤光片配置有效域/采样范围，不是全光谱总量，也不一定等于滤光片FWHM。
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
\begin{aligned}\mu_j&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}T_{\mathrm{gate}}FF\\&\quad\cdot\int_B L_j(\lambda)T_f(\lambda)\mathrm{PDE}(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{j,\mathrm{ideal}}&=N_{\mathrm{shots}}\mu_j\end{aligned}
$$

**符号与单位：** PDE(λ)在积分内逐波长参与计算；FF在积分外乘一次。μj是当前背景来源的每门期望雪崩候选数，Nj,ideal是累计Nshots发的候选总数。实际输出还会受到SPAD恢复、OR/符合逻辑和TDC限制。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 填充因子 | 1 | `fill_factor` |
| 每门期望雪崩候选数 | events/gate | `solar_candidates_gate` |
| 本次累计的理想候选数 | events | `solar_candidates_acquisition` |
| 累计脉冲数 | shots | `shots` |

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
\begin{aligned}\mu_j&=A_{\mathrm{Rx}}\Omega\eta_{\mathrm{Rx}}T_{\mathrm{gate}}FF\\&\quad\cdot\int_B L_j(\lambda)T_f(\lambda)\mathrm{PDE}(\lambda)q(\lambda)\,d\lambda_{\mathrm{nm}}\\N_{j,\mathrm{ideal}}&=N_{\mathrm{shots}}\mu_j\end{aligned}
$$

**符号与单位：** PDE(λ)在积分内逐波长参与计算；FF在积分外乘一次。μj是当前背景来源的每门期望雪崩候选数，Nj,ideal是累计Nshots发的候选总数。实际输出还会受到SPAD恢复、OR/符合逻辑和TDC限制。

| 中间量 | 单位 | Python结果字段 |
|---|---|---|
| 填充因子 | 1 | `fill_factor` |
| 每门期望雪崩候选数 | events/gate | `other_candidates_gate` |
| 本次累计的理想候选数 | events | `other_candidates_acquisition` |
| 累计脉冲数 | shots | `shots` |

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

## 对照代码与模型边界

- simulator.py / photon_budget：分阶段回波能量、入瞳光子、探测面光子与各来源候选数。
- spectra.py / spectral_components：太阳lux归一化、反射、其他光倍率、同波段分层光谱积分。
- photon_flow.py：将真实中间量绑定到共享步骤定义；不从LaTeX执行计算。
- readout.py：候选事件经过死时间、OR/符合/TDC限制，得到混合直方图。
- 太阳反射假定灰朗伯面；其他光输入已经是接收方向辐亮度。光学入瞳、通道视场、PDE/FF的适用范围见同目录模型说明。
- 回波门内份额G是理想IRF参考。事件模式中的门控与电子时间抖动可能带来不同的边缘损失，以实际读出审计为准。
- 背景原始计数使用B波段作分层对照；波段外的光子没有被这张预算表计入，不应把它解释为硬件已经拒收。

运行 `python scripts/render-photon-budget-doc.py --check` 可检测此文档是否与共享定义一致。更新定义后运行不带参数的脚本输出新版Markdown，并更新本文件。
