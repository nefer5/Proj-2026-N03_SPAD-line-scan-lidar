import fs from 'node:fs';
const dir='artifacts/architecture-review/20261014-213640';
const repo={url:'https://github.com/nefer5/Proj-2026-N03_SPAD-line-scan-lidar.git',revision:'354cb2e3aeac4d093d8291b1601f5f40587d8e14',link_mode:'local-only'};
const s=(path,line,end_line,label)=>({path,line,end_line:Math.min(end_line,fs.readFileSync(path,'utf8').trimEnd().split('\n').length),label});
const n=(id,type,label,sublabel,x,y,sources)=>({id,type,label,sublabel,pos:[x,y],size:[220,74],sources});
const e=(from,to,label,variant='default')=>({id:`${from}-${to}`,from,to,label,variant});
function save(slug,title,components,connections,cards){fs.writeFileSync(`${dir}/${slug}.json`,JSON.stringify({schema_version:1,diagram_type:'architecture',meta:{title,locale:'zh-CN',output:`${dir}/${slug}.html`,quality_profile:'showcase',repository:repo},components,connections,cards},null,2)+'\n');}
save('runtime','SPAD 项目 · 运行与代码架构',[
 n('web','frontend','网页与共享组件','A / SPAD / B / C / 系统预算',40,50,[s('web/app.js',287,290,'A 请求'),s('web/shared/labs.js',9,9,'实验请求'),s('web/columns.js',20,20,'C 请求')]),
 n('api','backend','FastAPI 入口与路由','api.py + webapi/*',420,50,[s('src/spad_lidar/api.py',25,40,'路由注册与缓存'),s('src/spad_lidar/webapi/labs.py',118,153,'任务 API')]),
 n('config','database','YAML 配置与校验','SimulationConfig / Algorithms',800,50,[s('src/spad_lidar/configuration.py',31,75,'安全加载与唯一源'),s('src/spad_lidar/models.py',29,63,'类型与解析')]),
 n('a','backend','A 单角同步入口','simulate / 性能扫参',40,260,[s('src/spad_lidar/api.py',107,134,'同步调用'),s('src/spad_lidar/experiments/single_channel.py',22,48,'解析或事件模式')]),
 n('jobs','backend','JobManager 任务编排','快照 / 取消 / 进程池',420,260,[s('src/spad_lidar/runtime/jobs.py',123,155,'提交与 spawn'),s('src/spad_lidar/runtime/jobs.py',60,101,'执行与写结果')]),
 n('budget','backend','独立系统预算路径','光学 / 电热 / DSP / MIPI',800,260,[s('src/spad_lidar/webapi/budget.py',65,73,'无状态计算 API'),s('src/spad_lidar/system_budget.py',125,177,'预算组合'),s('src/spad_lidar/electrical_budget.py',1,75,'输出资源调度')]),
 n('store','database','本地任务与结果','SQLite + artifacts/runs/<id>',40,480,[s('src/spad_lidar/runtime/jobs.py',15,20,'任务根目录'),s('src/spad_lidar/runtime/jobs.py',94,121,'结果与中断状态'),s('src/spad_lidar/runtime/jobs.py',140,146,'请求快照')]),
 n('experiments','backend','实验编排 experiments/*','A / SPAD / B / 历史C / 列级C',420,480,[s('src/spad_lidar/runtime/jobs.py',73,91,'按 kind 分派'),s('src/spad_lidar/experiments/spatial_analysis.py',41,63,'B 重复分析'),s('src/spad_lidar/experiments/columns.py',52,83,'C 编排')]),
 n('views','backend','结果视图与重放 API','reporting/* / 重分箱 / CSV',40,700,[s('src/spad_lidar/webapi/labs.py',155,192,'B 结果视图'),s('src/spad_lidar/webapi/columns.py',100,170,'C 结果与导出')]),
 n('core','backend','公共模型与数值核心','tx / scene / rx / spad / processing',420,700,[s('src/spad_lidar/experiments/lab.py',28,47,'共用采集核心'),s('src/spad_lidar/experiments/a_router.py',9,21,'A 器件适配'),s('src/spad_lidar/experiments/columns.py',52,82,'列级核心组合')])
],[e('web','api','HTTP / JSON','emphasis'),e('api','config','解析与校验'),e('api','a','同步计算'),e('api','jobs','提交 / 轮询'),e('api','budget','预算计算'),e('jobs','store','读写'),e('jobs','experiments','子进程执行','emphasis'),e('store','views','读取已完成结果'),e('experiments','core','组合调用','emphasis')],[
 {dot:'cyan',title:'从入口读代码',items:['start-dev.cmd → run.py → Uvicorn → api:app；服务绑定本机。','网页共用曲线、直方图和扫描工作台组件；参数预览也调用 Python。','A 支持同步 API，也支持 kind=a 后台任务；图中两种入口分开标示。']},
 {dot:'emerald',title:'任务与审计的实际边界',items:['JobManager 保存 YAML、实际配置、算法快照；worker 写 result.json，元数据存 SQLite。','服务发现已停止的任务所有者后标 interrupted；不是自动崩溃续算。','图中的箭头是调用或数据方向；响应沿 HTTP 原路返回。结果视图由 API 提供。']},
 {dot:'violet',title:'模块复用与预算分支',items:['experiments 是编排层，公共核心的内部关系见另一张核心链路图。','simulator.py、readout.py、curves.py 等保留兼容导出；并非另外一套主模型。','预算路径调用同一个 B 光学投影，并独立计算电热/输出容量；不运行完整事件采集。']},
 {dot:'amber',title:'审查范围与未完成项',items:['依据干净工作树 HEAD 354cb2e；节点附本地源码路径和行号。','此图核对代码结构和调用关系，不替代数值验证或器件实测。','roadmap：C 人工精细验收、C 列间完全复位、命名与参数跨平台审计仍待完成。']}
]);
save('core','SPAD 项目 · 光学与共享采集核心',[
 n('optics','backend','B 空间光学投影','tx → scene → rx / 光谱 / PSF',40,50,[s('src/spad_lidar/experiments/spatial.py',158,180,'光学投影入口'),s('src/spad_lidar/experiments/spatial.py',11,23,'模块组合')]),
 n('light','backend','探测面照明契约','SensorIllumination / 像素 × 波长',410,50,[s('src/spad_lidar/contracts/illumination.py',7,35,'照明定义'),s('src/spad_lidar/experiments/lab.py',17,25,'独立SPAD直接照明')]),
 n('source','backend','候选雪崩采样','spad/source.py · PDE / FF / seed',780,50,[s('src/spad_lidar/spad/source.py',36,72,'固定照明采样'),s('src/spad_lidar/spad/source.py',73,100,'逐发变化采样')]),
 n('scan','backend','C 扫描编排与逐发投影','scan/* / ColumnPulseProjection',780,270,[s('src/spad_lidar/experiments/columns.py',52,70,'计划、投影与采样')]),
 n('session','backend','AcquisitionSession','时间水位 / 门控 / 跨块状态',410,270,[s('src/spad_lidar/spad/acquisition.py',31,105,'状态推进'),s('src/spad_lidar/experiments/columns.py',69,70,'C 注入专用适配器')]),
 n('aadapter','backend','A 兼容事件入口','保留历史 RNG 与单角预算',40,270,[s('src/spad_lidar/experiments/a_acquisition.py',12,43,'A 候选采样'),s('src/spad_lidar/experiments/a_router.py',9,21,'A 接入 Session')]),
 n('device','backend','器件状态与响应','spad/device/* · 死时间 / 恢复',40,490,[s('src/spad_lidar/spad/acquisition.py',65,98,'器件门与雪崩'),s('src/spad_lidar/spad/device/state.py',1,24,'恢复状态')]),
 n('readout','backend','数字读出引擎','OR / 符合 / TDC / 容量',410,490,[s('src/spad_lidar/spad/acquisition.py',61,64,'读出工厂'),s('src/spad_lidar/spad/readout/engine.py',1,45,'读出引擎')]),
 n('quantize','backend','时间抖动与量化记录','普通周期 / 列级记录适配',780,490,[s('src/spad_lidar/experiments/lab.py',40,72,'周期记录'),s('src/spad_lidar/experiments/columns.py',32,49,'列级量化')]),
 n('process','backend','直方图与测距重建','processing/* · 统计 / 点云',780,710,[s('src/spad_lidar/experiments/columns.py',79,95,'重建与交付点云'),s('src/spad_lidar/experiments/lab.py',61,64,'直方图')]),
 n('transport','backend','C 输出资源计划','scan/transport.py · DSP / MIPI',410,710,[s('src/spad_lidar/experiments/columns.py',81,95,'传输计划与筛选')]),
 n('report','backend','Python 审计与展示数据','reporting/* / photon_flow / provenance',780,930,[s('src/spad_lidar/experiments/columns.py',101,103,'光子流程展示'),s('src/spad_lidar/experiments/lab.py',83,94,'版本与指纹'),s('src/spad_lidar/reporting/column_view.py',1,21,'视图共享计算')])
],[e('optics','light','投影光子','emphasis'),e('light','source','光谱积分输入','emphasis'),e('scan','source','逐发信号'),e('scan','session','采集程序'),e('source','session','CandidateEvents','emphasis'),e('aadapter','session','事件模式'),e('session','device','雪崩判定'),e('session','readout','推进状态','emphasis'),e('readout','quantize','已记录时间','emphasis'),e('quantize','process','量化记录','emphasis'),e('process','transport','记录数'),e('process','report','结果 / 真值 / 审计')],[
 {dot:'cyan',title:'共享核心的输入边界',items:['B 先完成 Tx/场景/Rx 投影；独立 SPAD 直接构造探测面照明。','照明在 PDE/FF 之前，以完整像素为参考面；候选雪崩与最终混合记录分开。','C 复用 B 背景/光学数据，再按逐发角度和时序形成变化信号。']},
 {dot:'emerald',title:'状态与硬件信息边界',items:['Session 在同一事件时间线上维护器件恢复、读出窗口、TDC 容量和时间水位。','C 注入 TraceDevice 与 FragmentAwareReadout；仍使用公共 Session。','读出记录只暴露读出/TDC 身份；光学真值和器件诊断独立保存。']},
 {dot:'violet',title:'A 的分支与兼容层',items:['A 的事件模式通过 a_router 接入同一器件/读出核心；保留旧采样顺序。','A 的 analytic_reference 分支直接计算和采样解析直方图，绕过事件 Session。','A 的单角 Rx 预算与 B 的空间光学不同；共同函数共享不等于模型范围相同。']},
 {dot:'amber',title:'检查时需要保留的限制',items:['核心检查点恢复不等于 JobManager 能在进程崩溃后自动续算。','C 当前仍跨列连续；完全复位为已确认待实施意图。','B/C 原始测距不等于已标定 Pd/PFA；afterpulse、雪崩串扰和完整直方图硬件资源仍有限制。']}
]);
