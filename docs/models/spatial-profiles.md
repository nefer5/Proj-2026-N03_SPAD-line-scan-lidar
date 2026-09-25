# 双轴高斯与超高斯空间模型

> 公式本体来自 config/formulas.yaml，符号说明来自 config/formula-notes.yaml；运行 python scripts/render-spatial-profiles-doc.py 更新。

B与C共用数值核心。Tx的gaussian/super_gaussian表示空间角分布，时间脉冲形状仍由独立的pulse_shape配置。Rx的gaussian_psf/super_gaussian_psf是H/V可分离、无旋转和相关项的无色差PSF；不是径向超高斯或真实光线追迹。

这里采用指数2m的阶数约定，m=1退化为高斯，H/V分别配置。标准化密度对应 [SciPy generalized normal](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gennorm.html) 的beta=2m；下面的FWHM与方差换算由同一密度积分推导并通过数值积分测试。

## 强度密度与二维分离形式

$$
\begin{aligned}p&=2m,\quad m\geq1\\g(u;a,m)&=\frac{p}{2a\Gamma(1/p)}\exp\!\left[-\left|\frac{u}{a}\right|^p\right]\\P(x,y)&=g(x;a_H,m_H)g(y;a_V,m_V)\end{aligned}
$$

m为无量纲阶数，指数p=2m，m=1为高斯。a为正形状尺度；u和a同单位，g为该单位的倒数。P为H/V可分离二维密度，不含旋转或交叉项；Rx坐标用μm，密度用μm⁻²。

## Tx与Rx的宽度定义

$$
\begin{aligned}a_{\mathrm{Tx}}&=\frac{W_{\mathrm{FWHM}}}{2(\ln2)^{1/p}}\\a_{\mathrm{Rx}}&=\sigma\sqrt{\frac{\Gamma(1/p)}{\Gamma(3/p)}}\end{aligned}
$$

各式分别对H、V应用。Tx的W为角分布FWHM（mrad），域内归一化后仍使用该未截断形状的FWHM参数；Rx的σ是实际边缘标准差（μm），不是指数尺度a。改变m时保持所配置的宽度定义。

## 能量与参考面

- Tx：先精确积分各角单元，再在配置角域内归一化。单发能量为该域内Tx光学前能量；Tx效率另乘一次，不额外扣角域外尾部。窄域裁切后实际剩余形状可能不再出现两侧半高点，参数FWHM仍定义母函数宽度。
- Rx：σ_H、σ_V始终是无限PSF各边缘分布的实际标准差，改变m会换算指数尺度a。按真实物理像素边界积分，有限阵列外仍记为边缘损失，不补回。
- 超高斯的形状、σ和FWHM均指光强/能量分布，不是电场振幅。
- 旧psf_sigma_um只在兼容层迁移为两轴相同σ；与新双轴字段混用报错。新导出仅保留双轴字段。旧采集结果及配置快照不改写。

## 参数图与投影图

参数图的PSF使用独立密度视图，横纵方向以自身中心为原点，圆点/菱点与不同虚线区分H/V；相同曲线自然可重合，不平移数据。二维图不画SPAD通道。它与下方按物理像素积分、叠加通道编号的投影图单位不同。

构造PSF显示采样数、单侧σ范围、导入PSF显示区能量分位分别由algorithms.yaml管理。图窗裁切不重新归一化。导入或均匀像素模型只展示实际采样区域的平均密度与裁切区域，不凭空构造阵列外PSF。

阶数上限由max_super_gaussian_order显式限制；超限报错，不裁剪。显示策略及完整算法配置保留在结果审计中。

## 验证

tests/test_spatial_profiles.py覆盖m=1高斯极限、密度归一化、实际方差、FWHM、H/V独立性、Tx域内能量、Rx边缘损失、旧字段迁移与非法配置。artifacts/optical-shapes/保留当前用户旧任务的逐事件一致性和网页验收证据。
