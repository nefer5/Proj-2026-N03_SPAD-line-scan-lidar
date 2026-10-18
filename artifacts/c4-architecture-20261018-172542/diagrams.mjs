import fs from 'node:fs';
const dir='artifacts/c4-architecture-20261018-172542';
const S=JSON.parse(fs.readFileSync(`${dir}/snapshot.json`,'utf8'));
const i18n=await import('file:///C:/Users/admin/.codex/skills/archify/renderers/shared/i18n.mjs');
const translations=Object.fromEntries(i18n.catalogKeys().map(k=>[k,i18n.translateMessage('zh-CN',k)]));
translations['viewer.passport.sourceMarker']='源码';
fs.writeFileSync(`${dir}/translations.json`,JSON.stringify(translations,null,2));
const repository={url:'https://snapshot.invalid/spad-lidar-c4-20261018-172542.git',revision:S.proofRevision,link_mode:'local-only'};
const R=(file,name,label)=>{const path=file.startsWith('src/')||file.startsWith('web/')||file.startsWith('config/')?file:`src/spad_lidar/${file}.py`;const n=S.symbols[path]?.find(x=>x.name===name);if(name&&!n)throw Error(path+':'+name);if(!S.sources[path])throw Error(path);return {path,line:n?.line||1,end_line:n?.end_line||Math.min(S.sources[path].lines,45),label:label||name||path.split('/').pop()}};
const N=(id,type,label,sublabel,x,y,sources,w=236)=>({id,type,label,sublabel,pos:[x,y],size:[w,86],sources});
const E=(from,to,label,variant='default')=>({id:`${from}-${to}`,from,to,label,variant});
const M=(id,title)=>({title,locale:'zh-CN',output:`${dir}/${id}.html`,quality_profile:'showcase',repository,translations});
const write=(id,d)=>{if(id==='c1'){d.components[0].icon='person';d.meta.legend={entries:{external:{label:'使用者'},backend:{label:'研究软件系统'}}}}if(id==='c2')d.meta.legend={entries:{database:{label:'数据存储'},backend:{label:'Python 后端应用'},frontend:{label:'浏览器应用'}}};if(id==='c3')d.meta.legend={entries:{backend:{label:'后端组件'}}};fs.writeFileSync(`${dir}/${id}.json`,JSON.stringify(d,null,2)+'\n')};
write('c1',{schema_version:1,diagram_type:'architecture',meta:M('c1','C1 系统上下文 · 谁使用，系统负责什么'),components:[
 N('researcher','external','研究人员 / 模型维护者','设置工况、导入数据、查看分析',60,80,[R('web/index.html',null,'参数与结果界面')],270),
 N('system','backend','SPAD 线扫 LiDAR 研究系统','A / 独立SPAD / B / C / 系统预算',550,80,[R('api','index'),R('runtime/jobs','worker'),R('system_budget','calculate_budget')],310)
],connections:[E('researcher','system','建模 / 采集 / 预算 / 导入导出','emphasis')],cards:[
 {dot:'cyan',title:'系统责任',items:['对照光子预算、器件/读出、空间光学和扫描，生成可审计的仿真或预算结果。','五种研究模式属于同一软件系统，评估/调试是观察视图。']},
 {dot:'amber',title:'外部边界',items:['光学JSON、曲线CSV与导出文件由使用者管理；文件去向在C2和数据页展开。','本次代码未证明已直连真实SPAD、激光器、Zemax宿主或云端存储；不把构造光学当实测。']}
]});
write('c2',{schema_version:1,diagram_type:'architecture',meta:M('c2','C2 应用与存储 · 前后端及参数归属'),components:[
 N('browser','frontend','浏览器前端应用','表单 / 预览 / 图形 / 导入导出',40,70,[R('web/app.js',null,'A 控制器'),R('web/system.js',null,'B 控制器'),R('web/columns.js',null,'C 控制器')]),
 N('backend','backend','本地 Python 后端应用','FastAPI + JobManager + 进程池',420,70,[R('api','index'),R('runtime/jobs','submit'),R('webapi/budget','calculate')]),
 N('db','database','任务元数据 SQLite','artifacts/runs/jobs.sqlite3',800,70,[R('runtime/jobs','connect'),R('runtime/jobs','submit')]),
 N('draft','database','浏览器草稿与任务引用','localStorage / sessionStorage',40,310,[R('web/system.js',null,'B 草稿键'),R('web/shared/labs.js',null,'SPAD 草稿键'),R('web/columns.js',null,'C 草稿键')]),
 N('defaults','database','项目初始默认与策略','config/defaults.yaml 等 YAML',420,310,[R('configuration','read_yaml'),R('experiments/system_config','domain_defaults'),R('config/defaults.yaml',null,'唯一工况默认值')]),
 N('runs','database','已提交工况与结果文件','runs/<id>/request · result.json',800,310,[R('runtime/jobs','submit'),R('runtime/jobs','worker'),R('runtime/jobs','result')])
],connections:[E('browser','backend','HTTP / JSON','emphasis'),E('browser','draft','保存 / 恢复'),E('backend','defaults','读取与冻结'),E('backend','db','任务状态'),E('backend','runs','快照 / 结果')],boundaries:[
 {kind:'region',label:'浏览器内；按页面来源隔离',wraps:['browser','draft'],pad:24},
 {kind:'region',label:'本机后端应用与项目数据；进程池属于同一应用',wraps:['backend','db','defaults','runs'],pad:24}
],cards:[
 {dot:'cyan',title:'用户输入沿什么路径走',items:['编辑值先在浏览器内；部分平台将草稿写浏览器存储。导入的文件解析后成为当前输入。','提交采集后由后端校验，写request.json和任务索引；完成后worker写result.json。']},
 {dot:'amber',title:'两个重要区别',items:['浏览器草稿不等于修改defaults.yaml；历史任务使用自己的冻结工况，不追随新的默认值。','预算calculate不创建采集作业；结果在浏览器显示/比较，需显式导出才成为用户文件。','A只保存最后任务id与临时切页配置，并没有和B/C相同的完整持久草稿机制。']}
]});
write('c3',{schema_version:1,diagram_type:'architecture',meta:M('c3','C3 后端组件 · 第一阶段提取后的职责协作'),components:[
 N('control','backend','HTTP 与任务控制','webapi/* + runtime/jobs.py',40,50,[R('webapi/labs','create_job'),R('runtime/jobs','worker')]),
 N('config','backend','配置入口与领域类型','configuration / models / domains',420,50,[R('models','for_experiment'),R('configuration','read_yaml'),R('domains/system','optical_fields')]),
 N('cases','backend','平台用例编排','experiments/* + scan/*',800,50,[R('experiments/spatial_analysis','run_system_analysis'),R('experiments/columns','run_columns'),R('experiments/a_acquisition','event_acquisition')]),
 N('budget','backend','系统预算用例','system_budget.py',40,280,[R('system_budget','calculate_budget')]),
 N('optics','backend','公共光学服务','optics/ + tx / scene / rx',420,280,[R('optics/service','project_illumination'),R('optics/service','optical_dataset')]),
 N('acq','backend','实验计划与记录适配','acquisition/ · TrialPlan / periodic',800,280,[R('acquisition/trials','TrialPlan'),R('acquisition/executor','execute_trials'),R('acquisition/adapters/periodic','acquire_candidates')]),
 N('output','backend','两种独立输出调度','scan/transport · budget_pipeline',40,510,[R('scan/transport','transport_plan'),R('budget_pipeline','schedule_link')]),
 N('processing','backend','公共处理与审计展示','processing/ + reporting/',420,510,[R('processing/ranging','_estimate_range'),R('processing/records','histogram_records'),R('experiments/lab','stamp_result')]),
 N('spad','backend','器件与数字读出状态','spad/acquisition · device/readout',800,510,[R('spad/acquisition','AcquisitionSession'),R('spad/readout/engine','ReadoutEngine')])
],connections:[E('control','config','校验输入'),E('config','cases','规范工况'),E('control','budget','预算请求'),E('cases','optics','B / C 投影'),E('cases','acq','组织采集'),E('budget','optics','光学参考'),E('optics','acq','照明输入'),E('acq','spad','推进状态','emphasis'),E('spad','processing','观测记录'),E('processing','output','C 记录数'),E('budget','output','预算计划')],cards:[
 {dot:'emerald',title:'已实现的第一阶段',items:['领域字段、光学组合、周期记录适配、A/B/C重复计划已提取；旧导入路径保留兼容。','acquisition/组织实验，spad/acquisition.py维护器件/读出状态，二者分层。']},
 {dot:'amber',title:'衔接与保留',items:['箭头展示职责间的数据衔接，规范工况和光学/记录交接由控制层与用例组织，不等同每条都直接import。','A解析分支不走事件核心；SPAD直接照明不走整机光学。','C/预算输出仍为两套策略；默认YAML领域化和三个工作台尚未实施。']}
]});
console.log(JSON.stringify({proofRoot:S.proofRoot,diagrams:['c1','c2','c3']}));
