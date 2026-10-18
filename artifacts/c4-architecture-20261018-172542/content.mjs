export const content={
 levels:{
  c1:{name:'C1 · 系统上下文',question:'谁使用系统？系统承担哪些研究工作？',scope:'一个研究软件系统；五个平台是研究模式，不是五个独立系统。',points:['研究者设置工况、导入曲线/光学数据，并查看或导出结果。','A 单角、独立 SPAD、B 空间、C 扫描、预算各有适用范围。','真实仪器、光学软件宿主和云端服务未作为已接通能力画入。']},
  c2:{name:'C2 · 应用与存储',question:'前后端如何协作？默认值和用户数据存在哪里？',scope:'浏览器应用 + 本地 Python 应用 + 数据存储；Container 不专指 Docker，也不等于每个子进程。',points:['浏览器管理输入、草稿和展示；FastAPI/任务进程调用同一 Python 核心。','项目默认在 config；浏览器草稿在浏览器；已提交采集工况和结果在 artifacts/runs。','进程池归同一后端应用；预算同步计算不自动创建采集结果文件。']},
  c3:{name:'C3 · 后端组件',question:'一个 Python 后端应用内部，哪些职责已共享？',scope:'只展开后端应用；目录和文件映射另页查看，不把源码文件当成 C2 运行单元。',points:['已提取 domains/、optics/、acquisition/；现有 spad/ 状态核心继续共用。','A/SPAD/B/C 用例、输入源与记录语义保留差异；输出调度仍为两种实现。','YAML 领域化、三个前端工作台和 C 列间复位尚未实施。']}
 },
 storage:[
  {name:'项目初始默认',where:'config/defaults.yaml',owner:'项目维护者',write:'编辑 YAML；网页输入不会写回它',life:'服务读取初始值；后台任务另存冻结快照',ref:['config/defaults.yaml',3,19]},
  {name:'算法策略 / 限额',where:'config/algorithms.yaml',owner:'模型/算法维护者',write:'编辑 YAML；类型严格校验',life:'任务提交时保存本次算法快照',ref:['src/spad_lidar/configuration.py',15,25]},
  {name:'正在编辑的输入',where:'浏览器内存；部分平台写 localStorage/sessionStorage',owner:'当前浏览器用户',write:'表单、文件导入、页面间转移',life:'持久性按平台区分；按浏览器 Profile 与页面来源隔离',ref:['web/system.js',62,65]},
  {name:'已提交采集工况',where:'artifacts/runs/<id>/request.json',owner:'Python 后端 JobManager',write:'提交时写入规范工况、算法和 YAML 快照',life:'不随之后修改默认值或表单而变',ref:['src/spad_lidar/runtime/jobs.py',123,150]},
  {name:'任务状态与结果',where:'jobs.sqlite3 + <id>/result.json / error.txt',owner:'Python 后端 / worker',write:'进度/取消写 SQLite；完成写结果，异常写错误',life:'刷新可重载历史；进程中断不等于自动续算',ref:['src/spad_lidar/runtime/jobs.py',60,101]},
  {name:'原始导入与导出文件',where:'用户选择的本机文件 / 浏览器下载位置',owner:'使用者',write:'CSV/JSON/YAML 显式导入或导出',life:'解析数据可进入草稿/任务快照；没有自动保存原件附件库',ref:['web/budget.js',110,113]}
 ],
 drafts:[
  ['A 单角','内存表单；sessionStorage: lidar-config','localStorage 主要记录 lidar-a-job；不能等同完整持久配置草稿。'],
  ['独立 SPAD','localStorage: lidar-experiment-v2-spad','恢复时经后端导入/校验。'],
  ['B 空间','localStorage: spad-system-modular-v3','参数草稿与已采集结果分开；支持显式载入历史任务工况。'],
  ['C 列级','localStorage: spad-columns-v4','B→C 的临时转移另走 sessionStorage。'],
  ['系统预算','localStorage: spad-hardware-budget-v1','保存草稿及比较基准；calculate 响应不自动写采集 result.json。']
 ],
 defaults:[
  ['A','simulation.*','当前角通道能量、独立 IFOV；同时作为已有公共值来源。'],
  ['独立 SPAD','simulation 引用 + experiments.spad.illumination','直接照明；不要求 Tx/Rx 光学配置。'],
  ['B','simulation 引用 + experiments.system.tx / rx','公共波长/效率/孔径来自共享值；空间角域、焦距、PSF 在 system 分组。'],
  ['C','继承 B 光学 + scan / columns','逐发列表、运动和输出参数保持 C 专用。'],
  ['预算','继承 B + experiments.budget_system 等','例如 uniform Tx、功率和 PSF 可有明确预算覆盖，部分角域由目标派生。']
 ],
 directory:[
  ['config/defaults.yaml','唯一初始工况源；当前仍为 simulation + experiments','保留，领域化待做'],
  ['config/algorithms.yaml','采样策略、阈值、容差与资源限额','保留'],
  ['config/parameter-help.yaml','单位、条件与生效说明；与参数路径关联','保留'],
  ['config/formulas.yaml / photon-flow.yaml 等','展示公式、光子说明、谱/曲线参考定义','保留横切分类'],
  ['src/spad_lidar/domains/','共享领域字段和约束；不存工况数值','第一阶段已提取'],
  ['src/spad_lidar/optics/','光学数据和探测面照明投影服务','第一阶段已提取'],
  ['src/spad_lidar/acquisition/','TrialPlan、顺序执行和周期记录适配','第一阶段已提取'],
  ['src/spad_lidar/spad/','候选源、器件恢复、数字读出和状态会话','原公共核心保留'],
  ['src/spad_lidar/tx/ · scene/ · rx/ · numerics/','发射、传播、接收、曲线和时空数值基础','原公共能力保留'],
  ['src/spad_lidar/experiments/ · scan/','研究用例、平台配置适配、扫描计划和运动','专用差异保留'],
  ['src/spad_lidar/processing/ · reporting/','记录/直方图/测距/统计；审计和展示装配','公共处理继续收敛'],
  ['src/spad_lidar/system_budget.py 等','系统预算；电学预算与 C transport 仍分开','不是完整采集仿真'],
  ['src/spad_lidar/webapi/ · runtime/','HTTP、任务执行、进度、快照和结果读回','同一后端应用'],
  ['web/ · web/shared/','五个平台页面及公共曲线/单位/绘图/主题','保留现有 1080P 调整'],
  ['artifacts/runs/','用户已提交任务、SQLite、配置快照与结果','运行数据，不是源码'],
  ['tests/ · docs/','回归、契约检查；设计、使用和验收状态','保留']
 ],
 currentTree:`config/
  defaults.yaml             当前：simulation + experiments
  algorithms.yaml           算法/限额
  parameter-help.yaml        参数定义说明
  formulas.yaml · photon-flow.yaml · 参考数据…
src/spad_lidar/
  domains/                  已提取：共享字段类型
  optics/                   已提取：公共光学服务
  acquisition/              已提取：重复编排 / 周期记录适配
  spad/                     原有器件 / 读出状态核心
  tx/ · scene/ · rx/         光学基础
  numerics/                 数值基础
  experiments/ · scan/      用例 / 扫描 / 配置适配
  processing/ · reporting/  处理 / 展示装配
  system_budget.py…         独立系统预算
  webapi/ · runtime/        HTTP / 任务与文件 IO
web/ · web/shared/          现有五平台前端
artifacts/runs/             已提交任务数据
tests/ · docs/              测试 / 文档`,
 targetTree:`后续目标草案 · 未实施的部分单独列出
config/defaults.yaml
  domains:                  建议：tx / scene / rx / spad / readout / timing / spectral_inputs
  experiments:              建议：只保存选择与确有必要的差异
src/spad_lidar/
  domains/ · optics/ · acquisition/ · spad/    继续收敛已有公共层
  experiments/              保留 A / SPAD / B / C 薄用例
  system/                   可再整理预算职责，输出策略先保持两种
web/
  器件工作台 / LiDAR工作台(A/B/C) / 系统方案工作台
用户命名方案                建议显式 JSON 导入/导出；是否增加本地方案库待定

不新增 tx.yaml / rx.yaml 的第二份数值源。
不把当前浏览器草稿冒充为项目默认值。`,
 reuse:[
  ['领域配置','A 扁平适配','器件/时序子集','领域类型已共享','继承 B，带扫描域','嵌套 B + 预算域','默认值的 YAML 领域化尚未完成'],
  ['光学计算','单角预算适配','直接照明，绕过','公共 optics','公共 optics + 逐发姿态','公共 optics 单角参考','A 与 B 单通道不自动等价'],
  ['器件 / 数字读出','事件模式共用','共用','共用','共用，带专用适配','不执行状态采集','A analytic_reference 绕过事件核心'],
  ['重复采集编排','TrialPlan / executor','单次采集','TrialPlan / executor','TrialPlan / executor','确定性预算','角色/次数/RNG 与初始状态保留原语义'],
  ['记录与处理','直接直方图适配','公共 periodic','公共 periodic','列级记录保持专用','仅容量/参考计算','测距、分箱等在契约一致处继续共用'],
  ['输出调度','—','—','—','scan/transport','budget_pipeline','接口可统一；两种调度策略尚未合并'],
  ['前端工作台','独立页面','独立页面','独立页面','独立页面','独立页面','已有公共组件；三个工作台是后续设计']
 ],
 decisions:[
  ['下一步：默认值按领域组织','仍保留 defaults.yaml 为唯一入口，明确公共值、实验差异与用户覆盖来源。类型共用不等于所有平台数值必须相等。'],
  ['前端最后统一','当前五个平台和已有1080P适配保留；后续再整合器件、LiDAR、系统方案三个工作台。'],
  ['模型语义变化另审','C列间复位、A/B等价范围、C/预算调度合并及统计/RNG改变，不随目录整理自动实施。']
 ]
};
