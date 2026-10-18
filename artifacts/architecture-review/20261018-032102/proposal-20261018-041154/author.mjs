import fs from 'node:fs';
const root='artifacts/architecture-review/20261018-032102',dir=`${root}/proposal-20261018-041154`;
const s=JSON.parse(fs.readFileSync(`${root}/snapshot.json`,'utf8'));
const prior=JSON.parse(fs.readFileSync(`${root}/shared-core.json`,'utf8'));
function R(file,name){const path=`src/spad_lidar/${file}.py`,sym=Object.values(s.modules).find(m=>m.path===path)?.symbols.find(n=>n.name===name);if(!sym)throw Error(path+':'+name);return {path,line:sym.line,end_line:sym.end,label:name}}
const M=(slug,title,repository)=>({title,locale:'zh-CN',output:`${dir}/${slug}.html`,quality_profile:'showcase',translations:prior.meta.translations,...(repository?{repository:prior.meta.repository}:{})});
const N=(id,label,sublabel,x,y,tag,sources,type='backend')=>({id,type,label,sublabel,pos:[x,y],size:[232,86],tag,...(sources?{sources}:{})});
const E=(from,to,label,variant='default')=>({id:`${from}-${to}`,from,to,label,variant});
const write=(slug,d)=>fs.writeFileSync(`${dir}/${slug}.json`,JSON.stringify(d,null,2)+'\n');
write('current',{schema_version:1,diagram_type:'architecture',meta:M('current','当前架构 · 页面分开、核心部分共享',true),components:[
 N('ui','五个研究页面','A / SPAD / B / C / 预算',40,50,'现状',[{path:'web/app.js',line:430,end_line:438,label:'A 后台采集'},{path:'web/system.js',line:179,end_line:179,label:'B → C 转移'},{path:'web/budget.js',line:113,end_line:113,label:'预算 → B'}],'frontend'),
 N('jobs','公共任务执行','JobManager / spawn',410,50,'已共享',[R('runtime/jobs','submit'),R('runtime/jobs','worker')]),
 N('uses','平台采集编排','A / SPAD / B / C',780,50,'各自编排',[R('experiments/a_acquisition','event_acquisition'),R('experiments/spatial_analysis','run_system_analysis'),R('experiments/columns','run_columns')]),
 N('budget','无状态系统预算','system_budget.calculate_budget',40,280,'独立用例',[R('webapi/budget','calculate'),R('system_budget','calculate_budget')]),
 N('optics','公共空间光学组合','experiments/spatial.py',410,280,'位于实验层',[R('experiments/spatial','project_illumination')]),
 N('adapters','各平台采集适配','A 源 / 周期 / 列级',780,280,'保留差异',[R('experiments/a_router','route_events'),R('experiments/lab','acquire_candidates'),R('experiments/columns','quantize_column_records')]),
 N('transport','两种输出调度实现','scan/transport · budget_pipeline',40,510,'当前分开',[R('scan/transport','transport_plan'),R('budget_pipeline','schedule_link')]),
 N('processing','测距与统计处理','公共测距 / 平台重复统计',410,510,'部分共享',[R('processing/ranging','_estimate_range'),R('experiments/spatial_analysis','run_system_analysis'),R('experiments/columns','run_columns')]),
 N('detector','公共器件与数字读出','AcquisitionSession',780,510,'已共享',[R('spad/acquisition','AcquisitionSession'),R('spad/readout/engine','ReadoutEngine')])
],connections:[E('ui','jobs','采集任务'),E('jobs','uses','按 kind 分派'),E('ui','budget','预算请求'),E('uses','optics','B / C 光学'),E('uses','adapters','各自组织'),E('budget','optics','光学参考'),E('optics','adapters','空间照明'),E('adapters','detector','事件模式','emphasis'),E('detector','processing','采集结果'),E('processing','transport','C 记录数'),E('budget','transport','预算资源')],cards:[
 {dot:'cyan',title:'现状证据',items:['基线 a19f273；未提交启动器改动在主报告另列。','源码标记是实际实现依据；箭头表示聚合后的调用/结果传递，不是完整执行时序。']},
 {dot:'amber',title:'图中省略的边界',items:['A 的 analytic_reference 绕过事件核心；SPAD 不经过整机光学。','C 和预算输出调度是两套实现，图中合放为一个领域框，不表示已共用调度器。','各平台配置、记录适配与统计协议仍有分叉；详见复用矩阵。']}
]});
write('proposed',{schema_version:1,diagram_type:'architecture',meta:M('proposed','建议架构 · 三个工作台、领域共用、用例独立',false),components:[
 N('ui','三个工作台','器件 / LiDAR / 系统方案',40,50,'建议整合',undefined,'frontend'),
 N('uses','四个采集用例','SPAD / A / B / C',410,50,'保留模式'),
 N('execution','公共实验执行器','TrialPlan / seed / 初始状态',780,50,'建议提取共用'),
 N('budget','系统预算用例','约束 / 电热 / 方案比较',40,280,'保持独立'),
 N('optics','公共光学服务','单角 / 空间投影策略',410,280,'建议下沉复用'),
 N('adapters','输入与记录适配器','A 单角 / 周期 / 列级',780,280,'保留专用适配'),
 N('transport','输出资源接口与策略','C 采集策略 / 预算硬件策略',40,510,'接口统一 · 策略独立'),
 N('processing','公共记录处理','量化工具 / 测距 / 统计',410,510,'分契约逐步共用'),
 N('detector','现有器件与读出核心','AcquisitionSession',780,510,'继续复用')
],connections:[E('ui','uses','采集研究'),E('uses','execution','实验计划'),E('ui','budget','系统方案'),E('uses','optics','A / B / C 按需'),E('execution','adapters','源 / 时序 / 记录'),E('budget','optics','同一光学能力'),E('optics','adapters','照明契约'),E('adapters','detector','统一状态执行','emphasis'),E('detector','processing','观测记录'),E('processing','transport','C 工作负载'),E('budget','transport','预算工作负载')],cards:[
 {dot:'amber',title:'讨论方案 · 尚未实施',items:['本图没有源码存在性声明；TrialPlan、工作台及目录名称均为建议。','以相同领域配置组合各用例，避免让 C / 预算依赖完整 B 实验配置。']},
 {dot:'emerald',title:'合并复用',items:['提取重复采集计划与执行器；光学组合从 experiments 下沉。','继续复用现有 SPAD/读出核心、Curve 和数值工具；记录/统计在契约一致处提取。']},
 {dot:'violet',title:'保留独立',items:['SPAD 直接照明；A 单角语义/解析分支/RNG；B 静态映射；C 运动/门碎片/列归属。','预算不生成最终混合记录；C 与预算的调度策略仍独立。','C 列间复位是另一个模型能力变更，本方案未实施或补造耗时。']}
]});
const changes=[
 {area:'页面与工作台',action:'整合入口',kind:'merge',current:'A、SPAD、B、C、预算各自页面和控制器。',proposed:'器件、LiDAR、系统方案三个工作台；LiDAR 内保留 A/B/C 模式。',boundary:'先共用外壳、任务和结果浏览；不把五种物理问题改成一个大表单。'},
 {area:'重复实验编排',action:'提取共用',kind:'merge',current:'A 三种统计计数；B 重复/噪声参考；C 重复记录各自编排。',proposed:'TrialPlan 明确角色、次数、首份观测、初始状态、seed 与保存级别；公共执行器运行。',boundary:'保留历史 RNG、各统计意义、取消检查与资源保护。'},
 {area:'光学组合',action:'下沉复用',kind:'merge',current:'空间投影位于 experiments/spatial.py；C、预算、部分视图调用。',proposed:'optics/ 提供照明、pixel_groups 和 OpticalAudit；Tx/scene/Rx 基础实现继续保留。',boundary:'A 单角适配、B 静态与 C 逐发姿态仍为不同策略；A 不自动等于 B 单通道。'},
 {area:'配置领域',action:'定义统一',kind:'merge',current:'A 扁平、Lab 分组、B 领域、C 继承 B、预算嵌套完整 B。',proposed:'领域类型放 domains/；各用例按需组合，不共享完整实验配置。',boundary:'默认仍仅 YAML；SPAD 无需填写孔径，预算无需构造采集作业。'},
 {area:'器件与读出核心',action:'继续复用',kind:'reuse',current:'四条事件路径已调用同一 AcquisitionSession。',proposed:'spad/ 保持独立、可注入和可测试，公共执行器消费它。',boundary:'核心不反向依赖网页、任务、整机配置或光学层。'},
 {area:'记录与处理',action:'按契约提取',kind:'merge',current:'A 直接直方图，B 周期记录，C 含列/绝对时间/门碎片。',proposed:'共用量化纯函数、直方图、测距和统计；保留 periodic / columns 适配。',boundary:'时间原点、TDC 身份和列归属不可悄悄改；真值仍与观测分开。'},
 {area:'SPAD / A / B / C 模式',action:'保留用例',kind:'keep',current:'输入参考面和实验问题不同。',proposed:'保留四个薄用例，选择照明、时序、记录和结果适配器。',boundary:'A 解析参考、历史数值/RNG、SPAD 直照、C 跨列连续状态继续明确。'},
 {area:'系统预算',action:'保持独立',kind:'keep',current:'确定性预算，借用 B 单角光学参考，不执行完整事件采集。',proposed:'system/budget.py 消费公共光学与领域类型，输出预算约束与方案比较。',boundary:'候选期望不当成混合记录；未知参数不按零计算。'},
 {area:'C / 预算输出调度',action:'统一接口 · 策略独立',kind:'keep',current:'transport_plan 与 schedule_link 具有不同硬件假设。',proposed:'先定义工作负载/拓扑/调度结果接口，保留 column_transport 与 hardware_budget 两种策略。',boundary:'同工况验证后再决定能共享多少；不直接合并 payload/缓冲/丢列规则。'},
 {area:'历史入口与 C 复位',action:'单独处理',kind:'keep',current:'历史 C 与兼容导出仍在；C 列间完全复位未接入。',proposed:'迁移期间保留兼容入口；复位另设设计与验收任务。',boundary:'不把结构重排当成复位实现，不删除旧配置/基线。'}
];
const directory=`建议目录草案 · 以下新名称均未创建

config/                          [保留] 默认、算法、帮助、公式仍唯一维护
src/spad_lidar/
├─ constants.py                 [保留] SI 常数
├─ configuration.py             [保留] YAML 加载、校验、快照
├─ legacy_config.py             [兼容] 历史配置迁移，不作为新参数源
├─ contracts/                   [扩展] 照明、事件、程序、记录契约
│  ├─ illumination.py           [保留] SensorIllumination
│  ├─ events.py                 [保留] 候选事件、显式程序
│  └─ records.py                [建议] 记录基础语义及扩展字段
├─ domains/                     [建议提取] 共享领域类型，不存默认数值
│  ├─ optical.py                Tx / scene / Rx / array
│  ├─ acquisition.py            时序、初始状态和统计计划类型
│  └─ hardware.py               硬件资源/预算配置，不捆绑 B 实验
├─ optics/                      [建议提取] 光学组合服务
│  ├─ service.py                照明 + pixel_groups + OpticalAudit
│  └─ angular_reference.py      A / 预算各自参考策略，语义不混同
├─ tx/ · scene/ · rx/            [保留] 公共光学基础计算
├─ numerics/                    [保留] Curve、时间/空间数值
├─ experiments/                 [精简] 每个文件只组装自己的研究用例
│  ├─ direct_spad.py            [建议名] 探测面直接照明
│  ├─ single_channel.py         [保留角色] A 单角/解析/兼容策略
│  ├─ static_optical.py         [建议名] B 静态全光斑
│  └─ column_scan.py            [建议名] C 显式扫描
├─ acquisition/                 [建议提取] 实验编排，位于器件核心之上
│  ├─ executor.py               公共执行/取消/限额/结果组织
│  ├─ trials.py                 TrialPlan / 角色计数 / seed 分流
│  └─ adapters/
│     ├─ a_legacy.py            A 源与历史 RNG 兼容
│     ├─ periodic.py            SPAD / B 周期记录
│     └─ columns.py             C 门碎片/触发参考/列级记录
├─ spad/                        [继续复用] 器件与数字读出公共核心
│  ├─ acquisition.py            AcquisitionSession / evolve_program
│  ├─ source.py                 公共固定/变化照明候选源
│  ├─ device/                   恢复、响应和诊断
│  └─ readout/                  OR / 符合 / TDC / FragmentAware
├─ timing/ · scan/              [保留专用] 周期预设 / 扫描计划和轨迹
├─ processing/                  [继续复用] 量化工具/重分箱/测距/统计
├─ system/                      [建议整理] 系统研究，不归属于 B 采集
│  ├─ budget.py                 确定性系统预算与方案约束
│  └─ output/
│     ├─ contracts.py           [先定义] 工作负载/拓扑/结果接口
│     ├─ column_transport.py    [独立策略] C 记录驱动调度
│     └─ hardware_budget.py     [独立策略] bank/chip/link/FIFO 预算
├─ reporting/                   [收敛] 结果展示/审计装配，避免持有新物理公式
├─ runtime/                     [保留] JobManager、进程池、任务快照
└─ webapi/                      [薄路由] 调用用例与公共预览服务

web/
├─ workbench.html               [建议] 共用外壳；旧 URL 可继续映射
├─ workspaces/
│  ├─ device.js                 独立 SPAD 工作台
│  ├─ lidar.js                  A / B / C 三种模式
│  └─ system-budget.js          系统方案工作台
└─ shared/                      [继续复用] 表单、曲线、图表、单位、主题

tests/                          [保留扩展] 数值基线、契约与跨平台对照
docs/                           [保留] 决策/模型/指南/验收
artifacts/                      [保留] 结果/快照/图表，不放模型实现

说明：acquisition/ 是上层实验执行，不替代 spad/acquisition.py 的状态核心。
目录名是职责草案；迁移时先增加接口/兼容导出，再决定物理移动与命名。`;
const mapping=[
 ['experiments/spatial.py','optics/service.py + experiments/static_optical.py','把公共光学投影与 B 用例组织拆开'],
 ['experiments/a_acquisition.py · spatial_analysis.py · columns.py','acquisition/trials.py + executor.py','提取重复计划/seed/取消/限额；专用源和记录适配保留'],
 ['experiments/system_config.py · configuration.py · scan/column_config.py','domains/* + 各 experiments 配置组合','共享领域类型，取消对完整 B 实验的过度依附'],
 ['spad/*','spad/*','继续复用现有核心，不复制也不为统一页面而重写'],
 ['system_budget.py · electrical_budget.py · budget_pipeline.py','system/budget.py + system/output/hardware_budget.py','整理预算职责，保持专用策略'],
 ['scan/transport.py','system/output/column_transport.py','在接口对齐之后评估移动，暂不合并调度算法'],
 ['web/app.js · shared/labs.js · system.js · columns.js · budget.js','web/workspaces/* + shared/*','外壳整合，研究模式、配置草稿和历史结果分开']
];
fs.writeFileSync(`${dir}/proposal-data.json`,JSON.stringify({status:'discussion-only',implemented:false,basis:s.revision,updated:'2026-10-18',headline:'三个工作台 · 五种研究模式 · 一套公共采集核心',changes,directory,mapping,phases:[['1 · 契约','先确认参考面、时序、统计角色、记录身份与初始状态；不改现有数值。'],['2 · 采集编排','提取 TrialPlan 与执行器，保留 A RNG/统计意义及各源/记录适配。'],['3 · 光学与配置','下沉公共光学；配置按领域组合；保留退化对照与兼容导出。'],['4 · 界面与系统','再整合三个工作台；C/预算输出接口对齐后做同工况对照。']]},null,2)+'\n');
console.log('Authored current implementation diagram and unimplemented proposal diagram.');
