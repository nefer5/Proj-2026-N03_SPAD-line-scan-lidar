# V0.1.1 专家调试与参数配置手册

更新：A / V0.1.4 已加入 [光谱背景/PDE](spectral-background.md) 和 [事件读出模式](readout-modes.md)。下文首光子解析分布仍作为analytic_reference的推导；事件模式不复位有限死时间，也不使用该解析分布生成实际直方图。constant背景/PDE仅是新光谱模型的特殊情况。调试公式已集中在config/formulas.yaml并由本地KaTeX渲染。

本手册适用于A单角通道V0.1.3。后续阶段按 [A/B/C路线](roadmap.md) 执行。derived.filter 包含与预算共用的插值曲线、原始采样点、激光标记与加权带宽；清除曲线恢复参数化矩形滤光片。曲线区间外为0，采样点不随激光波长平移，参数化矩形滤光片则以激光波长为中心。

## 版本边界与入口

- 评估页：本机服务根路径（开发版为 http://127.0.0.1:8001/）。
- 专家调试页：同服务的 /debug（http://127.0.0.1:8001/debug）。
- 两个页面共用 SimulationConfig、simulate()；调试版只多返回中间量，不改变随机种子、分布或算法。
- Tx 角分布/Rx PSF 数据库、二维阵列 binning、转镜轨迹仍属于 V0.2。当前 PRF 不会自动推导角点驻留或空间扫描。
- 自由运行死时间、afterpulse、共享 TDC、coincidence 仍属于后续读出模型。spad_dead_time_ns 保留兼容并明确标为未生效。

## 配置的唯一来源

| 文件 | 责任 |
|---|---|
| config/defaults.yaml | 工况默认值，包括器件、光学、时间、随机种子；初始累计发数100仅为探索参数 |
| config/algorithms.yaml | 平滑核、质心窗口、成功容差、扫参范围、展示波形采样与资源限额 |
| config/parameter-help.yaml | 每个参数的名称、单位、物理意义、生效条件 |
| src/spad_lidar/models.py | 字段类型、物理范围、枚举、跨字段校验，不保存工况默认数值 |
| src/spad_lidar/constants.py | SI常数与数学恒等式 |
| AGENTS.md | 本项目参数配置铁律 |

YAML 默认值每次新建配置时读取；页面“恢复默认”重新请求磁盘上的默认值。编辑 YAML 后已有页面不会覆盖用户当前输入，点击恢复默认才使用新工况。算法文件在每次模拟开始时读取，报告保存当次完整算法配置。

网页可导入 YAML 或旧 JSON 配置并导出完整 YAML；导入和导出不修改服务端的 defaults.yaml。缺少的工况字段由默认 YAML 合并，未知字段、重复 YAML 键、非有限数值和非法范围会报错。配置包形式为：

~~~yaml
schema_version: 1
simulation:
  range_m: 50
  pulse_shape: gaussian
  laser_prf_hz: 1000000
~~~

未列出的字段从 defaults.yaml 读取。完整字段说明以 parameter-help.yaml 及调试页“参数含义与本次取值”为准。旧 examples/config.json 是首次原型的历史高累计配置（20000发），不是当前默认配置源。

## 能量参考面与功率

输入 E 是当前角通道在 Tx 光学前的单脉冲能量，单位由 nJ 换成 J。不是线阵总能量、目标接收能量或电功耗。显示的峰值/平均功率默认以同一参考面计算；另列乘 Tx 效率后的出射功率。

高斯脉冲：

$$
P(t)=P_{\mathrm{peak}}\exp\left[-4\ln 2\left(\frac{t}{w}\right)^2\right]
$$

$$
E=P_{\mathrm{peak}}w\sqrt{\frac{\pi}{4\ln 2}},
\qquad
P_{\mathrm{peak}}=\frac{E}{w\sqrt{\pi/(4\ln 2)}}
$$

矩形脉冲的 w 为全持续时间（也即 FWHM）：

$$
P(t)=\begin{cases}E/w,& |t|\le w/2\\0,&\text{otherwise}\end{cases}
$$

$$
P_{\mathrm{avg}}=Ef_{\mathrm{PRF}},\qquad
T_{\mathrm{acq}}=\frac{N_{\mathrm{shots}}}{f_{\mathrm{PRF}}}
$$

例如 E=5 nJ、w=700 ps、PRF=1 MHz，Tx前高斯峰值约6.710 W，矩形约7.143 W，平均功率均0.005 W。这是光学功率，不含电光转换效率；线阵整体功率必须按真实同步发射策略汇总。100发在1 MHz下的连续采集时间为0.1 ms，未包含扫描回程/调度开销。

门终点不得超过一个激光周期。本版不支持高PRF距离折叠、多周期解模糊；脉冲足够窄、各周期开始器件完全就绪是模型假设。

## 入瞳几何与光子预算

圆形用直径 d；椭圆用水平/垂直全轴长 W、H（非半轴）；矩形用宽高 W、H：

$$
A_{\mathrm{circle}}=\frac{\pi d^2}{4},\quad
A_{\mathrm{ellipse}}=\frac{\pi WH}{4},\quad
A_{\mathrm{rectangle}}=WH
$$

尺寸先从 mm 换成 m。面积影响信号和光学背景，不影响器件 DCR；IFOV 仍为独立输入，选择椭圆并不会自动改变通道视场。

$$
e_\gamma=\frac{hc}{\lambda},\quad
E_r=E\eta_{\mathrm{Tx}}\rho\frac{A}{\pi R^2}
\eta_{\mathrm{Rx}}T_f(\lambda)OT_{\mathrm{atm}}^2
$$

$$
\mu_s=\frac{E_r}{e_\gamma}PDE\cdot FF
$$

本实现的 PDE 指感光区概率；如数据手册已含 fill factor，则令 FF=1。入瞳远小于距离、目标正入射且充分填充被照角通道是方程前提。

滤光片无采样点时采用矩形宽度与峰值透过率。有采样点时依据 filter_interpolation 使用PCHIP或线性插值，区间外为0。背景的加权带宽为 $\int T_f(\lambda)d\lambda$，没有除以峰值透过率，代码沿用字段名 filter_enbw_nm，需避免与“峰值归一化等效带宽”混淆。

### 离散点、插值与图形

CSV和手动输入走相同的数据校验：每行波长nm与透过率0–1，至少两点，波长严格递增；不自动排序、去重或裁剪坏数据。手动区可使用逗号/空格/Tab分列，英文CSV表头可选。修改后点击“应用采样点”，未应用编辑会阻止仿真和配置导出，避免误用旧数据。

- 原始点以蓝色散点显示，YAML保存原始点，不用致密插值数据覆盖它们。
- 默认PCHIP为保形分段三次Hermite插值，通过原始点，一阶导连续且不产生区间内过冲；它不是降噪平滑或对某种滤光片物理模型做参数拟合。参见 [SciPy PCHIP官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html)。
- 线性模式以分段直线穿过原始点，两点输入时两种方式均退化成直线。
- 绘图对插值函数密集采样，并显式包含原始结点，图上用青色曲线显示；采样密度来自 algorithms.yaml 的 filter_plot_samples。
- 激光波长处直接求插值函数值。PCHIP背景带宽通过分段多项式解析积分获得；线性模式的梯形积分则是分段线性的精确积分。改变绘图密度不会改变物理计算。
- 无样本的参数化矩形模式不显示虚构的“实测散点”，其边缘仍为硬截止。
- 稀疏点不足以恢复未采样到的窄峰或陡峭截止带；结果依赖采样位置和插值假设，可用线性/PCHIP比较敏感性。

例如原始点(930 nm,0)、(940 nm,0.8)、(950 nm,0)，PCHIP在945 nm处为0.6，积分约10.6667 nm；线性模式为0.4、8 nm。背景预算随插值曲线改变是预期行为。调试JSON另含PCHIP分段系数，可按SciPy PPoly约定复核。

$$
\Omega \simeq \theta_H\theta_V,\quad
P_b=L_\lambda A\Omega\eta_{\mathrm{Rx}}\int T_f(\lambda)d\lambda
$$

$$
\mu_b=\frac{P_bT_{\mathrm{gate}}}{e_\gamma}PDE\cdot FF,\quad
\mu_d=DCR\,N_{\mathrm{SPAD}}T_{\mathrm{gate}}
$$

其他噪声按相同单SPAD率模型计算。背景输入已是接收方向场景辐亮度，不再乘目标反射率和双程大气透过率。背景谱、PDE在窄带内近似恒定；真实太阳谱/滤光片角度漂移不在本版范围内。

## 时间分布与门控

高斯 FWHM 与标准差满足：

$$
\sigma=\frac{\mathrm{FWHM}}{2\sqrt{2\ln 2}}
$$

高斯激光脉冲与独立电子/器件抖动按方差相加。矩形激光脉冲采用与高斯抖动的解析卷积，其激光方差为 $w^2/12$；未将矩形悄悄替换成高斯。测距搜索用高斯平滑作为启发式，调试报告中有说明。

$$
t_0=\frac{2R}{c}+t_{\mathrm{cal}},\quad
g_k=F(t_{k+1}-t_0)-F(t_k-t_0)
$$

F 是完整回波时间分布的 CDF。门截断后 $\sum g_k\le1$，丢失部分不重新分配。最后一个 bin 不足额定TDC宽度时，仅计算门内实际宽度；边界数组直接随结果输出。

## 首光子直方图

假设通道信号及光学背景均匀分配到 N 个独立SPAD：

$$
\mu_k=\frac{\mu_sg_k+\mu_{\mathrm{noise}}\Delta t_k/T_{\mathrm{gate}}}{N},
\quad
S_k=\exp\left(-\sum_{j<k}\mu_j\right)
$$

$$
p_k=S_k(1-e^{-\mu_k}),\quad
p_{\varnothing}=\exp\left(-\sum_k\mu_k\right)
$$

一张观测直方图使用带“无事件”类别的多项分布：

$$
(H_0,\ldots,H_K,H_{\varnothing})
\sim\operatorname{Multinomial}
\left(N_{\mathrm{shots}}N,\,[p_0,\ldots,p_K,p_{\varnothing}]\right)
$$

有首光子竞争时分箱并非独立泊松计数；纯噪声期望是在“关闭激光”条件下另行计算，不是实际混合直方图中逐事件标记出的背景。pile-up 损失以门内、首光子竞争之前的总期望数为分母，与门截断损失分开显示。

## 测距与统计检查

1. 对观测直方图取中位数背景。
2. 用算法配置指定尺度的归一化高斯核平滑并全门搜索最大值。
3. 在峰附近的质心窗口内，以 max(H-baseline,0) 为权重求平均时间。
4. 减去已知标定延迟，换算距离；没有有效权重时返回 null。
5. 重复构造独立观测直方图，保存每次估计和误差。

$$
\widehat R=\frac{c}{2}
\left(\frac{\sum_{k\in W}t_k\max(H_k-b,0)}
{\sum_{k\in W}\max(H_k-b,0)}-t_{\mathrm{cal}}\right)
$$

bias 是有效测距误差的平均值，precision 为有效估计值的样本标准差（ddof=1）。不足2个有效结果时精度为 null。成功率以请求的重复次数为分母，无结果算失败；0次重复不报告成功率。容差来自 algorithms.yaml，不是脉宽隐式决定。

当前算法在有纯噪声时仍可能给出峰，因此“有数值”不等于检测成功；尚未使用无目标样本校准虚警率。观测峰值评分只是平滑峰除背景尺度，不能作为严谨检测SNR。距离扫描曲线是未计pile-up/门截断的预算与理想统计界限，不能直接当最大测距指标。

## 串扰与专家审核清单

串扰分支矩阵满足：

$$
C_{\mathrm{total}}=(I-C)^{-1}-I,\qquad \rho(C)<1
$$

不满足稳定性会报错，不再自动缩小用户输入。当前矩阵独立于单通道直方图；没有恢复时间约束，返回本通道的级联诱发期望不代表立即可再次雪崩。真实空间PSF串扰与器件光学/电学串扰仍需分开标定。

调试页可查看/导出：

- 完整工况、算法参数、参数意义与生效条件；
- 配置 SHA256、模型版本与时间；
- 发射功率曲线、入瞳面积、单光子能量、各环节收光因子；
- 光学背景功率、每发信号和各噪声期望；
- 门内保留能量、逐bin强度、存活概率、首事件概率和归一化检查；
- 实际随机观测、平滑核及滤波输出、峰索引、质心窗口和权重；
- 每次重复测距误差、统计判据、串扰谱半径。

完整JSON包含所有bin，无表格分页截断；导出的报告可用来比较同一配置前后的算法差异。配置指纹只标识参数，不是源码哈希；严格跨机器复现还应保存Git提交和依赖版本。

## 文献与公式预览

物理模型参考 [Padmanabhan等，2019](https://doi.org/10.3390/s19245464) 与 [Incoronato等，2021](https://doi.org/10.3390/s21134481)，本版只实现这些文献涉及模型的明确子集。

VS Code内用 Ctrl+Shift+V 预览；本手册遵循 [官方数学语法](https://code.visualstudio.com/docs/languages/markdown#_math-formula-rendering)，不需要额外公式插件。
