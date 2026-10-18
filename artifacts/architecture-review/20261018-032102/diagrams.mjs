import fs from 'node:fs';
const dir='artifacts/architecture-review/20261018-032102';
const data=JSON.parse(fs.readFileSync(`${dir}/snapshot.json`,'utf8'));
const repository={url:data.origin,revision:data.revision,link_mode:'local-only'};
const prior=fs.readFileSync('artifacts/architecture-review/20261014-213640/runtime.html','utf8');
const translations={...JSON.parse(prior.match(/<script id="archify-i18n-data" type="application\/json">([\s\S]*?)<\/script>/)[1]).messages,'viewer.passport.sourceMarker':'源码','viewer.passport.beacon.one':'源码依据：{count} 处，点击节点查看文件与行号','viewer.passport.beacon.other':'源码依据：{count} 处，点击节点查看文件与行号'};
function ref(path,name,label){
 const mod=Object.values(data.modules).find(m=>m.path===path);
 const symbol=mod?.symbols.find(s=>s.name===name);
 if(!symbol)throw Error(`Missing source symbol ${path}:${name}`);
 return {path,line:symbol.line,end_line:symbol.end,label:label||name};
}
const r=(file,name,label)=>ref(`src/spad_lidar/${file}.py`,name,label);
const meta=(slug,title)=>({title,locale:'zh-CN',output:`${dir}/${slug}.html`,quality_profile:'showcase',repository,translations});
const edge=(from,to,label,variant='default')=>({id:`${from}-${to}`,from,to,label,variant});
const node=(id,label,sublabel,x,y,sources,type='backend')=>({id,type,label,sublabel,pos:[x,y],size:[230,76],sources});
function save(slug,obj){fs.writeFileSync(`${dir}/${slug}.json`,JSON.stringify(obj,null,2)+'\n')}
save('shared-core',{schema_version:1,diagram_type:'architecture',meta:meta('shared-core','共享核心 · 连接契约与适配边界'),components:[
 node('optical','B / C 空间光学','tx + scene + rx + spectra',40,50,[r('experiments/spatial','project_illumination')]),
 node('illumination','探测面照明','SensorIllumination',410,50,[r('contracts/illumination','SensorIllumination'),r('experiments/lab','lab_illumination')]),
 node('source','候选雪崩采样','spad/source.py',780,50,[r('spad/source','sample_candidates'),r('spad/source','sample_varying_candidates')]),
 node('a','A 事件适配','a_acquisition → a_router',40,270,[r('experiments/a_acquisition','event_histogram'),r('experiments/a_router','route_events')]),
 node('session','连续采集协调','AcquisitionSession',410,270,[r('spad/acquisition','AcquisitionSession'),r('spad/acquisition','evolve_program')]),
 node('column','C 时序与投影适配','ColumnPulseProjection / program',780,270,[r('experiments/columns','_single'),r('scan/column_optics','ColumnPulseProjection')]),
 node('device','器件状态','DeviceState / TraceDevice',40,490,[r('spad/device/state','DeviceState'),r('spad/acquisition','advance')]),
 node('readout','数字读出','ReadoutEngine / FragmentAware',410,490,[r('spad/readout/engine','ReadoutEngine'),r('spad/readout/gates','FragmentAwareReadout')]),
 node('record','记录量化与重建','周期记录 / 列级记录',780,490,[r('experiments/lab','acquire_candidates'),r('experiments/columns','quantize_column_records'),r('processing/column_reconstruction','reconstruct_columns')])
],connections:[edge('optical','illumination','投影光子','emphasis'),edge('illumination','source','光谱输入','emphasis'),edge('source','session','候选事件','emphasis'),edge('column','source','逐发信号'),edge('column','session','显式采集程序'),edge('a','session','事件模式'),edge('session','device','雪崩判定'),edge('session','readout','推进读出','emphasis'),edge('readout','record','已记录时间','emphasis')],cards:[
 {dot:'cyan',title:'同一个核心，多种输入',items:['SPAD 直接构造 SensorIllumination；B 从静态光学投影得到照明。','C 复用 B 光学并引入逐发姿态；A 保留单角候选源和随机协议。']},
 {dot:'amber',title:'绕行与边界',items:['A 的 analytic_reference 绕过事件核心；系统预算不执行完整事件采集。','Session 的器件与读出可注入；C 的 FragmentAware/Trace 适配不等于另写 SPAD 核心。','源码 N 表示 N 处源码依据；点击节点查看路径与行号。']}
]});
const statusSource=[r('runtime/jobs','worker'),r('runtime/jobs','__init__'),r('runtime/jobs','cancel')];
save('job-states',{schema_version:2,diagram_type:'lifecycle',meta:meta('job-states','后台任务 · 持久化状态与退出条件'),lanes:[{id:'main',label:'正常执行'},{id:'terminal',label:'退出状态'}],states:[
 {id:'queued',type:'start',label:'queued',sublabel:'保存请求后排队',lane:'main',col:0,sources:[r('runtime/jobs','submit')]},
 {id:'running',type:'active',label:'running',sublabel:'worker 开始执行',lane:'main',col:1,sources:[r('runtime/jobs','worker')]},
 {id:'completed',type:'success',label:'completed',sublabel:'结果已写出',lane:'main',col:3,sources:[r('runtime/jobs','worker')]},
 {id:'cancelled',type:'failure',label:'cancelled',sublabel:'安全检查点确认取消',lane:'terminal',col:0,sources:statusSource},
 {id:'failed',type:'failure',label:'failed',sublabel:'异常或子进程失败',lane:'terminal',col:1,sources:[r('runtime/jobs','worker'),r('runtime/jobs','submit')]},
 {id:'interrupted',type:'failure',label:'interrupted',sublabel:'发现原任务所有者已退出',lane:'terminal',col:2,sources:[r('runtime/jobs','__init__')]}
],transitions:[edge('queued','running','开始'),edge('running','completed','完成'),edge('queued','cancelled','执行前取消','dashed'),edge('running','cancelled','检查到取消','dashed'),edge('running','failed','运行异常','security'),edge('queued','failed','进程失败','security'),edge('queued','interrupted','所有者退出','dashed'),edge('running','interrupted','所有者退出','dashed')],cards:[
 {dot:'amber',title:'取消请求不是一个新状态',items:['cancel() 设置 cancel_requested=1，任务暂时仍可显示 queued/running。','B/C 在阶段与处理块检查；A 兼容求解路径仍在整次求解后检查。']},
 {dot:'rose',title:'中断与重新提交',items:['新建 JobManager 时检查旧任务 owner_pid；已退出的任务标 interrupted。','未发现自动恢复进程作业的检查点接续；重新提交会生成新 id。','输入校验或队列限额拒绝发生在入队前，不产生 failed 作业。']}
]});
const p=(id,label,sublabel,type,sources)=>({id,label,sublabel,type,sources});
const messages=[['ui','api','提交 kind + config'],['api','jobs','manager.submit()'],['jobs','disk','保存 request / queued'],['jobs','worker','spawn 执行 worker','dashed'],['jobs','api','返回 job id','return'],['api','ui','返回任务信息','return'],['worker','disk','标 running / 更新进度'],['worker','core','执行核心（冻结 YAML 内）'],['core','worker','返回采集结果','return'],['ui','api','轮询 job 状态'],['api','disk','读取 SQLite 状态'],['disk','api','状态与进度','return'],['api','ui','状态与进度','return'],['worker','disk','写 result.json 后标 completed'],['ui','api','请求已完成结果'],['api','disk','读取 result.json'],['disk','api','原始结果','return'],['api','ui','结果 / 视图 JSON','return']].map(([from,to,label,variant='default'],i)=>({id:`step${i+1}`,from,to,label,variant,y:170+i*42}));
save('job-sequence',{schema_version:1,diagram_type:'sequence',meta:{...meta('job-sequence','采集调用时序 · 提交、执行与读回'),column_fit:'spread',viewBox:[1360,1010]},participants:[
 p('ui','网页','A / SPAD / B / C','frontend',[{path:'web/columns.js',line:180,end_line:194,label:'C 任务提交与轮询'}]),
 p('api','HTTP 路由','webapi/labs.py','backend',[r('webapi/labs','create_job'),r('webapi/labs','result')]),
 p('jobs','JobManager','主服务进程','backend',[r('runtime/jobs','submit')]),
 p('worker','worker','spawn 子进程','backend',[r('runtime/jobs','worker')]),
 p('core','实验核心','experiments/*','backend',[r('experiments/columns','run_columns'),r('experiments/spatial_analysis','run_system_analysis')]),
 p('disk','本地文件','SQLite + JSON','database',[r('runtime/jobs','connect'),r('runtime/jobs','result')])
],messages,cards:[
 {dot:'cyan',title:'逻辑时序，不是性能测量',items:['异步提交后网页轮询；图中的执行次序为可能的一次正常路径。','spawn 启动后 worker 与 HTTP 返回可并发，垂直间距不代表耗时。']},
 {dot:'amber',title:'需分开的几条路径',items:['无状态预算 calculate 不走 JobManager；A 同步 API 仍保留。','预览与结果读回不同：预览可重新调用光学核心，读回不重新生成采集记录。','结果页可补显示元数据，需保留原采集版本与配置指纹。']}
]});
const dn=(id,label,sublabel,stage,row,sources,type='backend')=>({id,label,sublabel,stage,row,width:stage===0?120:178,height:74,type,sources});
save('config-flow',{schema_version:1,diagram_type:'dataflow',meta:{...meta('config-flow','参数数据流 · 唯一源、解析与冻结'),viewBox:[1180,760]},stages:[{label:'配置输入'},{label:'合并与迁移'},{label:'严格类型'},{label:'执行快照'},{label:'审计输出'}],nodes:[
 dn('yaml','YAML 唯一源','defaults / algorithms',0,0,[r('configuration','read_yaml')],'database'),
 dn('overrides','用户覆盖值','当前平台配置结构',0,2,[r('models','for_experiment')],'frontend'),
 dn('resolve','统一配置入口','SimulationConfig',1,1,[r('models','for_experiment'),r('models','resolve_defaults')]),
 dn('models','各平台类型','A / Lab / B / Column / Budget',2,1,[r('experiments/configuration','resolve_experiment'),r('scan/column_config','resolve_columns'),r('system_budget','resolve_budget')]),
 dn('freeze','任务快照','实际配置 + YAML + 算法',3,1,[r('runtime/jobs','submit'),r('configuration','frozen_yaml')]),
 dn('result','审计结果','seed / 版本 / 指纹',4,1,[r('experiments/lab','stamp_result'),r('experiments/single_channel','simulate')],'database')
],flows:[{...edge('yaml','resolve','默认与策略'),labelAt:[208,217]},edge('overrides','resolve','当前覆盖'),{...edge('resolve','models','迁移后校验','emphasis'),labelAt:[423,233]},{...edge('models','freeze','规范化配置','emphasis'),labelAt:[638,233]},{...edge('freeze','result','固定快照执行','emphasis'),labelAt:[853,233]}],cards:[
 {dot:'emerald',title:'数值唯一源与定义唯一源',items:['工况值：defaults.yaml；策略/限额：algorithms.yaml；物理常数：constants.py。','帮助、公式、光子说明：parameter-help / formulas / formula-notes / photon-flow。']},
 {dot:'amber',title:'需要审计的映射',items:['A 为扁平字段；SPAD 为 device/readout/timing；B/C 为领域分组。','C 的默认继承经过历史 scan 配置；预算嵌套 BSystemConfig，但会构造单角通道参考。','同名值或默认值相等不证明语义相同；budget 的无状态计算冻结 YAML，但不保存作业。']}
]});
// Split the long trace into readable submission and result phases; no calls are dropped.
const trace=JSON.parse(fs.readFileSync(`${dir}/job-sequence.json`,'utf8'));
const submit={...trace,meta:{...trace.meta,title:'任务时序 · 提交与首次执行',viewBox:[1080,650]},messages:trace.messages.slice(0,9).map((m,i)=>({...m,y:170+i*40}))};
const result={...trace,meta:{...trace.meta,title:'任务时序 · 轮询与结果读回',output:`${dir}/job-result.html`,viewBox:[1080,650]},participants:trace.participants.filter(p=>['ui','api','worker','disk'].includes(p.id)),messages:trace.messages.slice(9).map((m,i)=>({...m,y:170+i*40}))};
save('job-sequence',submit);save('job-result',result);
const flow=JSON.parse(fs.readFileSync(`${dir}/config-flow.json`,'utf8'));
flow.meta.viewBox=[1080,640];flow.nodes.forEach(n=>{if(n.stage>0)n.width=160});save('config-flow',flow);
console.log('Authored 5 repository-backed Archify candidates.');
