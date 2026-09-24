/* Design-review UI only. All numeric model data is exported by Python.
 * Inputs collect a separate design draft; they never submit a simulation.
 */
'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (v, digits = 3) => Number(v).toLocaleString('en-US', {maximumFractionDigits:digits});
const svg = (w,h,body,label) => `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">${body}</svg>`;
const txt = (x,y,t,attr='') => `<text x="${x}" y="${y}" font-size="12" ${attr}>${esc(t)}</text>`;
const rect = (x,y,w,h,fill,attr='') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4" fill="${fill}" ${attr}/>`;
const line = (x1,y1,x2,y2,color,attr='') => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" ${attr}/>`;
const arrow = (x1,y1,x2,y2,color='#58d9cf') => `${line(x1,y1,x2,y2,color,'stroke-width="2"')}<path d="M${x2-6},${y2-4} L${x2},${y2} L${x2-6},${y2+4}" fill="none" stroke="${color}" stroke-width="2"/>`;
const palette = {cyan:'#58d9cf', amber:'#e9b879', blue:'#78a9f6', muted:'#839dad'};
let data, columnIndex, focusCycle, windowNs, draft = {}, strategy='uniform', outputFormat='points', navDragging=false;
const selectedColumn = () => data.columns[columnIndex];
const nextColumn = () => data.columns[columnIndex+1];
const focusPulse = () => data.frame_rows.find(r=>r.cycle===focusCycle);
const setActive = (attribute, value) => document.querySelectorAll(`[${attribute}]`).forEach(b=>b.classList.toggle('active',b.getAttribute(attribute)===value));
function option(value,label){return `<option value="${esc(value)}">${esc(label)}</option>`;}
function setDraft(key,value){draft[key]=value; $('draftStatus').textContent='已修改 · 未计算';$('draftBanner').classList.remove('hidden');}
function field(path,label,value,kind='number',choices=null){
  const control=choices?`<select data-draft="${path}">${choices.map(([v,t])=>option(v,t)).join('')}</select>`:
    `<input data-draft="${path}" type="${kind}" ${kind==='number'?'step="any"':''}>`;
  return `<label>${esc(label)}${control}</label>`;
}
function renderParameters(){
  const c=data.configuration, definitions=[
    ['scan','扫描与列规划',true,[['scan.frame_rate_hz','帧率 / Hz',c.scan.frame_rate_hz],['scan.frame_count','帧数',c.scan.frame_count],['scan.angle_bin_min_mrad','角格 H 下界 / mrad',c.scan.angle_bin_min_mrad],['scan.angle_bin_max_mrad','角格 H 上界 / mrad',c.scan.angle_bin_max_mrad],['scan.angle_bin_width_mrad','角格宽度 / mrad',c.scan.angle_bin_width_mrad],['scan.active_fraction','前扫时间占比',c.scan.active_fraction]],'列 slot 由列级计划分配。参考工况恰好每角格一列；非均匀规划时二者可以不同。'],
    ['mirror','转镜与角度耦合',false,[['scan.mechanical_start_mrad','机械起始角 / mrad',c.scan.mechanical_start_mrad],['scan.mechanical_end_mrad','机械终止角 / mrad',c.scan.mechanical_end_mrad],['scan.optical_multiplier','机械 → 光学角倍率',c.scan.optical_multiplier],['scan.rx_scan_scale','Rx / Tx 扫描比例',c.scan.rx_scan_scale],['scan.rx_angle_offset_mrad','Rx 静态角偏移 / mrad',c.scan.rx_angle_offset_mrad],['scan.trajectory','运动轨迹',c.scan.trajectory,'select',[['sawtooth','锯齿往返'],['triangle','三角往返'],['sinusoidal','正弦摆扫'],['static','静止']]]],'机械角速度由角范围、帧率与轨迹确定，光学扫描速度另乘角倍率。连续转镜的 RPM / 棱面周期模型另行定义，不把帧率直接叫机械转速。'],
    ['acquisition','曝光与接收门',true,[['acquisition.period_ns','触发周期 / ns',c.acquisition.period_ns],['acquisition.gate_start_ns','门起点 / ns',c.acquisition.gate_start_ns],['acquisition.gate_width_ns','门宽 / ns',c.acquisition.gate_width_ns],['acquisition.rng_seed','随机种子',c.acquisition.rng_seed]],'门起点相对触发。右侧逐发列表定义列内时间和单发能量；本栏周期值保留为均匀参考。'],
    ['tx','Tx 发射',false,[['tx.total_pulse_energy_nj','单发能量 / nJ',c.tx.total_pulse_energy_nj],['tx.pulse_fwhm_ps','脉宽 FWHM / ps',c.tx.pulse_fwhm_ps],['tx.wavelength_nm','波长 / nm',c.tx.wavelength_nm],['tx.pulse_shape','脉冲形状',c.tx.pulse_shape,'select',[['gaussian','Gaussian'],['rectangular','矩形']]]],'复用 B 的光斑与光谱输入。新的长尾参数尚未定义，不自动添加经验尾迹。'],
    ['rx','Rx 接收光学',false,[['rx.focal_length_h_mm','f_H / mm',c.rx.focal_length_h_mm],['rx.focal_length_v_mm','f_V / mm',c.rx.focal_length_v_mm],['rx.rx_offset_x_um','像面 x 偏移 / μm',c.rx.rx_offset_x_um],['rx.rx_offset_y_um','像面 y 偏移 / μm',c.rx.rx_offset_y_um]],'沿用 B 的倒置映射、PSF 和角域结构。Rx 在回波时刻的姿态与发射角标签分别处理。'],
    ['spad','SPAD 线阵',true,[['spad.channels_h','H 兼容维度',c.spad.channels_h],['spad.channels_v','V 线数',c.spad.channels_v],['spad.H_binning','每通道 H 合并数',c.spad.H_binning],['spad.V_binning','每通道 V 合并数',c.spad.V_binning]],'16 条线按列并行。H 选择仅切换显示，当前计算仍包含两路；是否启用/合并另行定义。'],
    ['readout','读出与时间量化',false,[['readout.tdc_bin_ps','时间分箱 / ps',c.readout.tdc_bin_ps],['readout.tdc_count','共享 TDC 个数',c.readout.tdc_count],['readout.tdc_dead_time_ns','TDC 死时间 / ns',c.readout.tdc_dead_time_ns],['spad.spad_dead_time_ns','SPAD 死时间 / ns',c.spad.spad_dead_time_ns]],'参数是否生效取决于读出模式。器件内部吞吐与外部数据链路带宽分开统计。'],
    ['scene','场景与目标',false,[['scene.range_m','参考距离 / m',c.scene.range_m],['scene.target_reflectivity','目标反射率',c.scene.target_reflectivity],['scene_motion.radial_velocity_m_s','径向速度 / m·s⁻¹',c.scene_motion.radial_velocity_m_s],['scene_motion.range_gradient_m_per_rad','距离角梯度 / m·rad⁻¹',c.scene_motion.range_gradient_m_per_rad]],'行距离表、单行多个目标、运动和多径将分层呈现；当前数值图使用单距离参考。'],
    ['background','太阳与其他环境光',false,[['background.solar_enabled','太阳光',String(c.background.solar_enabled),'select',[['true','启用'],['false','关闭']]],['background.other_light_enabled','其他环境光',String(c.background.other_light_enabled),'select',[['true','启用'],['false','关闭']]],['background.solar_illuminance_lux','太阳照度 / lux',c.background.solar_illuminance_lux],['background.other_light_scale','其他光缩放',c.background.other_light_scale]],'默认值继承公共工况。完整光谱编辑与可折叠曲线面板复用 B；此预览仅展现 C 的新增交互。']
  ];
  $('parameters').innerHTML=definitions.map(([id,title,open,fields,note])=>`<details class="parameter-group" ${open?'open':''}><summary>${esc(title)}</summary><div class="parameter-body"><div class="form-grid">${fields.map(f=>field(...f)).join('')}</div><p class="field-note">${esc(note)}</p>${id==='spad'?`<div class="readonly-fact">当前参考：<b>${data.h_routes} × ${data.line_rows}</b> 读出通道<br>物理 SPAD 网格：${data.physical_shape[1]} × ${data.physical_shape[0]}。不会自动扩张光学覆盖。</div>`:''}</div></details>`).join('');
  definitions.forEach(d=>d[3].forEach(([path,,value])=>{document.querySelector(`[data-draft="${path}"]`).value=value;}));
  $('parameters').oninput=e=>{if(e.target.dataset.draft)setDraft(e.target.dataset.draft,e.target.value);};markUpstreamFields();
}
const terms={
  column:['列 slot Sₖ','<strong>列采集时隙 slot</strong>：对应一列点云。全部线阵行并行工作，列内可安排多次发射。列编号是采集计划的 ID，不由某次编码器读数直接决定。'],
  angle:['扫描角格 Aⱼ',()=>{const c=selectedColumn();return `<strong>扫描角格</strong>：用于方向归档与重建的角区间。所选 A${c.index} 中心 ${fmt(c.angle_center_mrad)} mrad，范围 [${fmt(c.angle_min_mrad)}, ${fmt(c.angle_max_mrad)}) mrad；编号从 0 开始。它与列 slot 仅在当前均匀参考中对齐。`;}],
  trigger:['触发 Pᵢ','<strong>触发周期</strong>：一轮激光触发的时间安排。旧代码的 slot 指这一层；新页面改称“触发周期”。回扫阶段可以继续计时但不发射。'],
  time:['时间分箱 Tᵦ',()=>`<strong>TCSPC 时间分箱</strong>：直方图中的一个到达时间区间，当前宽 ${fmt(data.timing.tdc_bin_ns)} ns。相邻距离格对应约 ${fmt(data.timing.range_bin_m)} m；这是量化格宽，不是测距精度。时间原点、门起点和分箱宽度分别标明。`],
  spad:['SPAD 空间合并',()=>`<strong>SPAD 空间合并</strong>：当前每个读出组由 H×V＝${data.configuration.spad.H_binning}×${data.configuration.spad.V_binning} 颗 SPAD 组成。它不同于 ${data.h_routes}×${data.line_rows} 个读出通道，也不同于扫描角格。`],
  optics:['光学积分单元','<strong>光学积分角单元</strong>：B 平台对光斑和 PSF 做数值积分的二维角网格。积分网格密度不是点云分辨率；保留 H/V 二维标签。']
};
function selectTerm(key){setActive('data-term',key);const body=terms[key][1];$('termExplanation').innerHTML=typeof body==='function'?body():body;}
function renderConcepts(){
  const w=470,h=205,x0=53,y0=33,cw=18,rh=7.5;
  let b=txt(13,19,`H${$('hRoute').value} · V 行`,'font-size="10"')+txt(245,19,'点云列 →','font-size="10"');
  for(let v=0;v<data.line_rows;v++){
    const yy=y0+(data.line_rows-1-v)*rh;
    if(v===0||v===data.line_rows-1||v===Math.floor(data.line_rows/2))b+=txt(14,yy+6,`V${v}`,'font-size="9"');
    data.columns.forEach((c,i)=>{const on=i===columnIndex||i===columnIndex+1;b+=rect(x0+i*cw,yy,cw-3,rh-1,on?(i===columnIndex?'#399b99':'#ab8757'):'#1e394a');});
  }
  data.columns.forEach((c,i)=>{b+=`<rect class="col-hit" data-column="${i}" x="${x0+i*cw}" y="${y0-2}" width="${cw-1}" height="${data.line_rows*rh+4}" fill="transparent" role="button" tabindex="0" aria-label="查看列 S${i}"><title>列 S${i} · 参考角格 A${i}</title></rect>`;if(i===0||i===columnIndex||i===columnIndex+1||i===data.columns.length-1)b+=txt(x0+i*cw+7,y0+data.line_rows*rh+19,`S${i}`,'font-size="9" text-anchor="middle"');});
  b+=txt(53,192,'网格表达采样位置；未绘制探测结果或有效回波。','font-size="10"');
  $('frameDiagram').innerHTML=svg(w,h,b,'16行点云帧，两个相邻列高亮');
  const c=selectedColumn(), pulses=c.pulses;
  let tree=rect(28,29,350,31,'#174248')+txt(203,49,`列 slot S${c.index} · ${fmt((c.end_ns-c.start_ns)/1000)} μs`,'text-anchor="middle" class="hot"');
  pulses.forEach((p,i)=>{let x=34+i*85;tree+=line(x+36,60,x+36,88,'#396a77')+rect(x,88,72,40,'#173047')+txt(x+36,105,`P${p.cycle}`,'text-anchor="middle" class="mono"')+txt(x+36,120,`${fmt(data.timing.trigger_period_ns/1000)} μs`,'text-anchor="middle" font-size="10"');});
  tree+=line(35,150,371,150,'#4c8290')+txt(203,175,`V0…V${data.line_rows-1} 同时工作，不逐行轮流曝光`,'text-anchor="middle" font-size="11"');
  $('hierarchyDiagram').innerHTML=svg(406,205,tree,'列采集时隙包含多次触发，16行并行');
  $('frameDiagram').querySelectorAll('[data-column]').forEach(el=>{
    const choose=()=>{let ix=Number(el.dataset.column);if(ix===data.columns.length-1)ix--;selectColumn(ix);};
    el.onclick=choose;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};
  });
}
function renderAssignment(mode){
  setActive('data-assignment',mode);const c=selectedColumn(), wrong=mode==='mismatch';
  let b=txt(24,25,wrong?'角标签偏差示意 · 不代表误差仿真':'当前零误差参考','font-size="11"');
  b+=rect(22,43,115,87,'#183c43')+txt(79,73,`采集列 S${c.index}`,'text-anchor="middle" class="hot"')+txt(79,99,'列 ID 不改变','text-anchor="middle" font-size="10"');
  b+=arrow(137,67,197,67)+arrow(137,111,197,111,'#e9b879');
  b+=txt(212,65,`编码器归属：A${wrong?(c.index>0?c.index-1:c.index+1):c.index}`,'class="hot"')+txt(212,83,'用于记录归档 / 重建','font-size="10"');
  b+=txt(212,111,`实际发射方向：A${c.index}`,'class="warm"')+txt(212,129,'仅仿真审计，不能替代观测标签','font-size="10"');
  $('assignmentDiagram').innerHTML=svg(448,151,b,'编码器归属角格与实际发射方向角格的区别');
}
function selectColumn(ix){
  columnIndex=ix;const pulses=selectedColumn().pulses.concat(nextColumn().pulses);
  $('columnSelect').value=ix;$('pulseSelect').innerHTML=pulses.map(p=>option(p.cycle,`P${p.cycle} · ${fmt(p.emission_time_ns/1000)} μs`)).join('');
  focusCycle=selectedColumn().pulses.at(-1).cycle;$('pulseSelect').value=focusCycle;
  renderConcepts();renderAssignment(document.querySelector('[data-assignment].active').dataset.assignment);setWindowPreset('columns');renderPlanning();
  selectTerm(document.querySelector('[data-term].active').dataset.term);
  if(reviewReady)syncReviewSelection();
}
function setWindow(a,b){windowNs=[a,b];$('windowStart').value=Number(((a-selectedColumn().start_ns)/1000).toFixed(9));$('windowEnd').value=Number(((b-selectedColumn().start_ns)/1000).toFixed(9));$('windowError').textContent='';renderTimeline();}
function setWindowPreset(mode){
  document.querySelectorAll('.zoom-buttons button').forEach(b=>b.classList.toggle('active',b.id===({frame:'viewFrame',columns:'viewColumns',trigger:'viewTrigger',echo:'viewEcho'})[mode]));
  const p=focusPulse();
  if(mode==='frame')setWindow(0,data.frame_budget.frame_period_ns);
  if(mode==='columns')setWindow(selectedColumn().start_ns,nextColumn().end_ns);
  if(mode==='trigger'){const next=data.frame_rows.find(r=>r.cycle===p.cycle+1);setWindow(p.nominal_time_ns,next?next.gate_close_ns:p.slot_end_ns);}
  if(mode==='echo'){const ret=referenceReturn(p.cycle);const center=ret.arrival_ns;setWindow(center+data.waveforms.echo_phase_ns[0]-data.timing.tof_ns,center+data.waveforms.echo_phase_ns.at(-1)-data.timing.tof_ns);}
}
function renderTimeline(){
  const [a,b]=windowNs,W=930,H=604,L=152,R=900,x=t=>L+(t-a)/(b-a)*(R-L),base=selectedColumn().start_ns;
  const lane=[51,97,143,189,235,281,327,373,419,465];
  const names=['列采集 slot','触发周期 · 基准','Tx 发射 · 基准','回波中心 · 基准','SPAD 门 · 基准','TDC 门 · 基准','内部器件状态','Tx 列表 · 草案','DSP · 草案','MIPI → 主机 · 草案'];
  let body='<defs><clipPath id="timelineClip"><rect x="152" y="27" width="748" height="468"/></clipPath></defs>';
  names.forEach((n,i)=>{body+=txt(15,lane[i]+4,n,'font-size="11"')+line(L,lane[i]+21,R,lane[i]+21,'#213a4c');});
  for(let i=0;i<=5;i++){const t=a+(b-a)*i/5;body+=line(x(t),28,x(t),488,'#1d3445')+txt(x(t),513,fmt((t-base)/1000,(b-a)<1000?6:3),'text-anchor="middle" class="mono" font-size="10"');}
  body+=txt(R,533,`μs · 相对 S${columnIndex} 开始；绝对 ${fmt(a/1000,6)} — ${fmt(b/1000,6)} μs`,'text-anchor="end" font-size="10"');
  let clipped='';
  data.columns.forEach(c=>{if(c.end_ns<a||c.start_ns>b)return;const xa=x(Math.max(c.start_ns,a)),xb=x(Math.min(c.end_ns,b));const on=c.index===columnIndex;clipped+=rect(xa,lane[0]-13,Math.max(0,xb-xa-1),26,on?'#215b59':c.index===columnIndex+1?'#655237':'#1b3543');if(xb-xa>32)clipped+=txt((xa+xb)/2,lane[0]+4,`S${c.index}`,'text-anchor="middle" font-size="11"');});
  data.frame_rows.forEach(p=>{
    const t=p.nominal_time_ns,em=p.emission_time_ns,echo=p.emitted?referenceReturn(p.cycle).arrival_ns:null;
    if(t>=a&&t<=b){clipped+=line(x(t),lane[1]-11,x(t),lane[1]+10,'#7999ab');if((b-a)/data.timing.trigger_period_ns<14)clipped+=txt(x(t)+4,lane[1]+3,`P${p.cycle}`,'font-size="9"');}
    if(p.emitted&&em>=a&&em<=b)clipped+=line(x(em),lane[2]-13,x(em),lane[2]+13,palette.cyan,`stroke-width="${p.cycle===focusCycle?3:1.5}"`);
    if(p.emitted&&echo>=a&&echo<=b)clipped+=`<path d="M${x(echo)},${lane[3]-8} l5,8 l-5,8 l-5,-8 Z" fill="${palette.amber}"/>`;
    if(p.gate_close_ns>a&&p.gate_open_ns<b){const xa=x(Math.max(a,p.gate_open_ns)),xb=x(Math.min(b,p.gate_close_ns));[4,5].forEach(j=>{clipped+=rect(xa,lane[j]-8,Math.max(1,xb-xa),16,j===4?'#36657a':'#365785');});}
  });
  clipped+=line(L,lane[6],R,lane[6],'#776c8c','stroke-dasharray="5 5"')+rect(L+8,lane[6]-11,440,22,'#0b1722')+txt(L+15,lane[6]+4,'暂无逐器件轨迹；不从量化 TDC 记录倒造雪崩时刻','font-size="11"');
  clipped+=reviewTimelineLanes(x,a,b,lane);
  body+=`<g clip-path="url(#timelineClip)">${clipped}</g>`;
  const navX=t=>L+t/data.frame_budget.frame_period_ns*(R-L),ny=557,ww=navX(b)-navX(a);
  body+=txt(15,ny+13,'全帧导航','font-size="11"')+rect(L,ny,R-L,19,'#162c3b')+rect(L,ny,data.planning_reference.active_ns/data.frame_budget.frame_period_ns*(R-L),19,'#224853');
  body+=rect(navX(a),ny,Math.max(3,ww),19,'#bb895050','stroke="#e9b879" stroke-width="1.5"')+txt(L,593,'0 μs','font-size="9"')+txt(R,593,`${fmt(data.frame_budget.frame_period_ns/1000)} μs · 拖动定位 / 上方精确输入`,'text-anchor="end" font-size="9"');
  body+=`<rect id="navigatorHit" x="${L}" y="${ny}" width="${R-L}" height="19" fill="transparent" style="cursor:ew-resize" aria-label="拖动全帧观测窗口"/>`;
  $('timeline').innerHTML=svg(W,H,body,'两个列采集时隙的触发、发射、回波与门控时序');
  $('timelineScope').textContent=`S${columnIndex} + S${columnIndex+1} · 参考时序`;
  $('timingHint').innerHTML=`基准触发间隔 <strong>${fmt(data.timing.trigger_period_ns/1000)} μs</strong>；脉宽 <strong>${fmt(data.timing.pulse_fwhm_ns)} ns</strong>；选中距离 ${fmt(referenceReturn(focusCycle).reflection_range_m)} m 的光学飞行时间约 <strong>${fmt(referenceReturn(focusCycle).flight_ns)} ns</strong>。上方参考门与回波未按 Tx 草案重算；下方三条草案泳道仅按输入定位。DSP / MIPI 的标签 Sₖ 表示被处理的数据列，可延续到下一 slot。`;
  const hit=$('navigatorHit'), diagram=hit.ownerSVGElement;
  const move=e=>{const r=diagram.getBoundingClientRect(),sx=(e.clientX-r.left)/r.width*W;const centre=(sx-L)/(R-L)*data.frame_budget.frame_period_ns,span=b-a;const start=Math.max(0,Math.min(data.frame_budget.frame_period_ns-span,centre-span/2));setWindow(start,start+span);};
  // Capture on the persistent container, since SVG nodes are replaced on redraw.
  $('timeline').onpointermove=e=>{if(navDragging)move(e);};$('timeline').onpointerup=()=>{navDragging=false;};$('timeline').onpointercancel=()=>{navDragging=false;};
  hit.onpointerdown=e=>{navDragging=true;$('timeline').setPointerCapture(e.pointerId);move(e);};
}
function plotCurve(id,xs,ys,color,xLabel,yLabel){
  const canvas=$(id), dpr=window.devicePixelRatio||1,w=canvas.clientWidth,h=185;
  if(!w)return;canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const l=48,r=w-17,t=19,b=h-36,xmin=xs[0],xmax=xs.at(-1),ymax=Math.max(...ys),xp=x=>l+(x-xmin)/(xmax-xmin)*(r-l),yp=y=>b-y/ymax*(b-t);
  ctx.font='10px Consolas';ctx.lineWidth=1;ctx.textAlign='right';ctx.fillStyle='#829fb3';
  for(let i=0;i<=4;i++){const y=ymax*i/4;ctx.strokeStyle='#233e51';ctx.beginPath();ctx.moveTo(l,yp(y));ctx.lineTo(r,yp(y));ctx.stroke();ctx.fillText(fmt(y,2),l-7,yp(y)+3);}
  ctx.textAlign='center';for(let i=0;i<=4;i++){const x=xmin+(xmax-xmin)*i/4;ctx.fillText(fmt(x,2),xp(x),b+16);}
  ctx.textAlign='left';ctx.fillText(yLabel,l,t-7);ctx.textAlign='right';ctx.fillText(xLabel,r,h-5);ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.beginPath();xs.forEach((v,i)=>i?ctx.lineTo(xp(v),yp(ys[i])):ctx.moveTo(xp(v),yp(ys[i])));ctx.stroke();
}
function drawWaves(){const ret=referenceReturn(focusCycle),phase=data.waveforms.echo_phase_ns.map(t=>t-data.timing.tof_ns+ret.flight_ns+data.configuration.acquisition.calibration_delay_ns);plotCurve('txWave',data.waveforms.tx_time_ns,data.waveforms.tx_power_w,palette.cyan,'相对脉冲中心 / ns','W');plotCurve('echoWave',phase,data.waveforms.echo_relative,palette.amber,'相对发射 / ns（含标定延迟）','归一化');}
function renderStrategy(value){strategy=value;setActive('data-strategy',value);$('strategyNote').textContent={uniform:'当前数值时序：列内均匀周期发射。对比策略应固定发数和单发能量，分别观察门控、器件忙碌与归档结果。',burst:'设计候选：脉冲集中到列内一段时间，可设置组间隔和组内间隔。卡片仅示意排列；下方数值时序仍是均匀参考，尚未执行突发仿真。',gates:'设计候选：保持发射不变，比较延迟开门、宽门与多窄门。需要区分 SPAD 器件门和 TDC 记录门；下方数值时序仍是当前 gated 参考。'}[value];}
function renderCause(value){
  setActive('data-cause',value);let b=rect(125,19,298,32,'#194349')+rect(425,19,324,32,'#413d33')+txt(275,40,'列 slot Sₖ','text-anchor="middle" class="hot"')+txt(590,40,'列 slot Sₖ₊₁','text-anchor="middle" class="warm"')+line(424,19,424,192,'#8d7859','stroke-dasharray="4 4"');
  if(value==='tail'){
    b+=txt(18,93,'光源 / 场景')+rect(170,72,210,37,'#204550')+txt(275,95,'前次发射及其响应','text-anchor="middle"')+arrow(380,91,680,91,palette.amber)+txt(527,79,'尾迹延伸（示意）','text-anchor="middle" class="warm"');
    b+=txt(18,158,'后次接收')+rect(470,133,235,38,'#314664')+txt(588,157,'后次门内可能混入前次来源','text-anchor="middle"');
    $('causeNote').textContent='先区分 Tx 光源尾迹、场景多径/距离分布、接收电子响应尾迹，再判断是否跨触发或跨列。追踪“来自哪一发”和“记录归到哪一列”两个 ID。图中箭头没有数值时间比例。';
  }else if(value==='range'){
    b+=txt(18,91,'近目标')+arrow(174,86,327,86)+rect(280,112,95,28,'#234d50')+txt(327,131,'较早返回','text-anchor="middle" font-size="11"');
    b+=txt(18,166,'远目标')+arrow(174,161,669,161,palette.amber)+rect(563,113,150,28,'#4e4336')+txt(638,132,'可能越过列边界','text-anchor="middle" font-size="11"');
    $('causeNote').textContent='同一行可有多个回波，各行也可对应不同距离。远处回波可能进入下一触发或下一列的门，需要保留发射来源及绝对到达时间；当前预览仅有单距离参考，没有构造新的多目标结果。';
  }else{
    b+=txt(17,90,'一颗 SPAD')+rect(251,68,313,36,'#4b3c42')+txt(405,91,'雪崩 → 恢复中 → 恢复完成','text-anchor="middle"')+txt(245,130,'其他 SPAD 可具有不同状态','font-size="11"');
    b+=txt(17,170,'TDC 资源')+rect(307,149,353,31,'#344361')+txt(484,170,'忙碌 / 容量 / 复用状态延续','text-anchor="middle"');
    $('causeNote').textContent='观察所选行内的一颗 SPAD 及相应 TDC 资源。列边界不自动重置器件状态；不要把单颗死时间画成整条线阵一起失效。需要核心真实事件轨迹，不能从量化后的记录倒推。';
  }
  $('causeDiagram').innerHTML=svg(785,210,b,'跨列影响机制，无时间比例示意');
}
function renderPlanning(){
  const p=data.planning_reference,c=selectedColumn();
  $('resourceMetrics').innerHTML=[['帧周期',`${fmt(p.frame_period_ns/1000)} μs`,`${fmt(data.configuration.scan.frame_rate_hz)} Hz`],['前扫时间',`${fmt(p.active_ns/1000)} μs`,'其余为回扫参考'],['每帧点云列',fmt(p.column_count),'参考角格与列对齐'],['每列 slot',`${fmt((c.end_ns-c.start_ns)/1000)} μs`,'当前均匀时间规划']].map(([a,b,c])=>`<div class="metric"><small>${a}</small><strong>${b}</strong><span>${c}</span></div>`).join('');
  const width=780,L=25,R=750,xx=t=>L+t/p.frame_period_ns*(R-L);let body=rect(L,34,xx(p.active_ns)-L,39,'#1e595b')+rect(xx(p.active_ns),34,R-xx(p.active_ns),39,'#564736')+txt((L+xx(p.active_ns))/2,59,`前扫 · ${p.column_count} 列`,'text-anchor="middle" class="hot"')+txt((R+xx(p.active_ns))/2,59,'回扫 · 不发射','text-anchor="middle" class="warm"');
  [0,p.active_ns,p.frame_period_ns].forEach(t=>{body+=txt(xx(t),96,`${fmt(t/1000)} μs`,'text-anchor="middle" font-size="11"');});
  $('frameBudget').innerHTML=svg(width,115,body,'单帧前扫和回扫时间预算');
  $('columnBudget').innerHTML=`<div>${c.pulses.length} 次发射 / 列<small>触发周期 ${fmt(data.timing.trigger_period_ns/1000)} μs；每次门宽 ${fmt(data.timing.gate_width_ns/1000)} μs</small></div><div>${data.line_rows} 行并行 / H 路<small>${p.points_per_frame_one_H} 个点位置 / 帧 / H 路，非有效点数</small></div><div>${fmt(p.h_fov_mrad)} mrad 水平扫描 FOV<small>角格宽 ${fmt(p.angle_step_mrad)} mrad；V 角覆盖另由光学校准给出</small></div>`;
}
function renderPipeline(value){
  setActive('data-buffer',value);let b=txt(20,24,'依赖关系示意 · 未定义延迟，横向长度不代表耗时','font-size="11"');
  const boxes=[['整列采集',20],['整列锁存',181],['DSP 并行处理',342],[value==='single'?'单缓冲':'双缓冲 A / B',503],['MIPI → 主机',664]];
  boxes.forEach(([title,x],i)=>{b+=rect(x,48,129,44,i===3?'#574630':'#19424b')+txt(x+64,74,title,'text-anchor="middle"');if(i<4)b+=arrow(x+129,70,x+156,70);});
  if(value==='single'){b+=txt(30,125,'Sₖ 缓冲仍占用时，Sₖ₊₁ 是否等待 / 丢弃？必须定义资源释放条件。','font-size="12"')+line(570,95,570,141,'#bc9c6b','stroke-dasharray="4 4"')+txt(30,164,'单缓冲 ≠ 所有操作串行；读取与写入能否并行仍由硬件决定。','font-size="11"');}
  else{b+=rect(503,115,129,34,'#223d5a')+txt(567,136,'缓冲 B / 下一列','text-anchor="middle" font-size="11"')+line(469,95,469,132,'#7099b2')+arrow(469,132,499,132,'#7099b2')+txt(20,133,'采集 Sₖ₊₁ 与输出 Sₖ 可重叠','class="hot"')+txt(20,167,'双缓冲不能解决持续平均输入大于链路输出；仍要检查积压与期限。','font-size="11"');}
  $('pipelineDiagram').innerHTML=svg(815,191,b,'整列并行处理到读出链路的依赖关系');
  $('pipelineNote').textContent=value==='single'?'先明确锁存、处理、读出各占用哪个资源，再分配时隙。不要直接把所有阶段时间相加，也不要把接收关门段全部当作空闲。':'本次选定双缓冲，允许不同列在不同资源上重叠。真实时间流水线要等处理延迟、链路净速率、缓存容量和仲裁规则齐全后才能计算。';
}
const formatFields={points:[['pointBytes','每回波结果 / byte'],['returnsPerRow','每行最多回波数']],histograms:[['countBits','每计数位宽 / bit'],['exportedBins','导出时间分箱数']],events:[['eventBytes','每条事件记录 / byte'],['eventBound','每列事件上限']]};
function renderFormat(value){
  outputFormat=value;setActive('data-format',value);
  $('formatDefinition').textContent={points:'每列以线阵行组织结果，距离、强度、置信度与状态字段分别定义位宽；若有多回波需明确上限。H0/H1 是分开发送还是合并也要明确。',histograms:'按行 / H 路输出各时间分箱计数。采集分箱与导出分箱不一定相同；需明确截窗、合并和计数位宽。',events:'输出接受的时间戳、行 / H 路与标志。数据量随信号、环境光和记录容量变化，要同时评估平均负载与最坏情况。'}[value];
  const fields=[...formatFields[value],['columnHeaderBytes','列头 / byte'],['frameHeaderBytes','帧头 / byte'],['netLinkMbps','接口净速率 / Mbit·s⁻¹'],['bufferBytes','可用缓存 / byte']];
  $('bandwidthInputs').innerHTML=fields.map(([key,label])=>`<label>${label}<input type="number" step="any" min="0" data-budget="${key}" placeholder="待定义"></label>`).join('');
  fields.forEach(([key])=>{if(Object.hasOwn(draft,`planning.${key}`))document.querySelector(`[data-budget="${key}"]`).value=draft[`planning.${key}`];});
  $('bandwidthInputs').oninput=e=>{if(e.target.dataset.budget)setDraft(`planning.${e.target.dataset.budget}`,e.target.value);};
}
async function init(){
  const response=await fetch(document.body.dataset.reference,{cache:'no-store'});if(!response.ok)throw Error(`参考工况加载失败：HTTP ${response.status}`);data=await response.json();
  if(data.purpose!=='design_review_only'||data.columns.length<2)throw Error('预览参考数据结构不兼容，请重新生成 reference.json');
  renderParameters();
  $('hRoute').innerHTML=Array.from({length:data.h_routes},(_,i)=>option(i,`H${i}`)).join('');
  $('rowSelect').innerHTML=Array.from({length:data.line_rows},(_,i)=>option(i,`V${i}`)).join('');
  $('columnSelect').innerHTML=data.columns.slice(0,-1).map(c=>option(c.index,`S${c.index} → S${c.index+1}`)).join('');
  $('termButtons').innerHTML=Object.entries(terms).map(([key,[title]])=>`<button data-term="${key}">${title}</button>`).join('');selectTerm('column');
  document.querySelectorAll('[data-term]').forEach(b=>b.onclick=()=>selectTerm(b.dataset.term));
  document.querySelectorAll('[data-assignment]').forEach(b=>b.onclick=()=>renderAssignment(b.dataset.assignment));
  $('hRoute').onchange=renderConcepts;$('columnSelect').onchange=e=>{selectColumn(Number(e.target.value));renderPlanning();};
  $('pulseSelect').onchange=e=>{focusCycle=Number(e.target.value);syncReviewSelection();renderTimeline();drawWaves();};
  $('rowSelect').onchange=e=>{document.querySelector('.state-inspector .pending').textContent=`V${e.target.value} · 待核心事件轨迹接入`;};
  selectColumn(Math.min(7,data.columns.length-2));
  initReviewV2();
  initHighLevel();
  ['frame','columns','trigger','echo'].forEach((mode,i)=>$(['viewFrame','viewColumns','viewTrigger','viewEcho'][i]).onclick=()=>setWindowPreset(mode));
  $('applyWindow').onclick=()=>{
    const start=$('windowStart').value,end=$('windowEnd').value,a=Number(start)*1000+selectedColumn().start_ns,b=Number(end)*1000+selectedColumn().start_ns;
    if(start===''||end===''||!Number.isFinite(a)||!Number.isFinite(b)||b<=a||a<0||b>data.frame_budget.frame_period_ns){$('windowError').textContent='请输入帧范围内的有效起止时间，且终点大于起点。';return;}
    document.querySelectorAll('.zoom-buttons button').forEach(el=>el.classList.remove('active'));setWindow(a,b);
  };
  document.querySelectorAll('[data-workspace]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-workspace]').forEach(el=>el.setAttribute('aria-selected',String(el===b)));$('exposureWorkspace').classList.toggle('hidden',b.dataset.workspace!=='exposure');$('planningWorkspace').classList.toggle('hidden',b.dataset.workspace!=='planning');drawWaves();});
  document.querySelectorAll('[data-strategy]').forEach(b=>b.onclick=()=>renderStrategy(b.dataset.strategy));renderStrategy('uniform');
  $('fixedEnergy').textContent=`${selectedColumn().pulses.length} 发 / 列 · 每发 ${fmt(data.configuration.tx.total_pulse_energy_nj)} nJ`;
  document.querySelectorAll('[data-cause]').forEach(b=>b.onclick=()=>renderCause(b.dataset.cause));renderCause('tail');
  renderPlanning();document.querySelectorAll('[data-buffer]').forEach(b=>b.onclick=()=>renderPipeline(b.dataset.buffer));renderPipeline('double');
  document.querySelectorAll('[data-format]').forEach(b=>b.onclick=()=>renderFormat(b.dataset.format));renderFormat('points');
  $('collapse').onclick=()=>document.querySelectorAll('.parameter-group').forEach(d=>d.open=false);
  $('expand').onclick=()=>document.querySelectorAll('.parameter-group').forEach(d=>d.open=true);
  $('reset').onclick=()=>{draft={};renderParameters();renderFormat('points');renderStrategy('uniform');$('draftStatus').textContent='参考工况';$('draftBanner').classList.add('hidden');};
  $('workflow').onclick=()=>{$('dialogTitle').textContent='审核后的运行流程';$('dialogBody').innerHTML='<ol><li>选择研究问题，校验 Tx / Rx / 场景 / SPAD 公共参数。</li><li>生成列级曝光计划：分配列 slot、发射时刻、器件门和记录门。</li><li>执行连续时间仿真；保留跨脉冲、跨列、跨帧的器件状态。</li><li>按观测角标签重建，同仿真真值分开审计。</li><li>对照测距、损失原因与重复统计；检查列输出数据量和缓冲峰值。</li></ol><p>此按钮仅解释设计，当前没有提交计算任务。</p>';$('dialog').showModal();};
  $('closeDialog').onclick=()=>$('dialog').close();
  $('exportDraft').onclick=()=>{const payload={kind:'c_workspace_design_draft',not_simulation_config:true,reference_provenance:data.provenance,reference_configuration:data.configuration,draft_inputs:draft,review:exportReviewDraft(),high_level:exportHighLevelDraft(),strategy,output_format:outputFormat,note:'待审核设计草案；未校验或执行新模型。'};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='c-workspace-design-draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  $('audit').innerHTML=`<p>参考生成时间：${esc(data.provenance.utc)}。来源：${esc(data.provenance.source)}。</p><p>参考配置已是 H×V=${data.h_routes}×${data.line_rows}，并非旧 3×2 探测结果重贴标签。此页未运行探测器随机仿真。默认太阳与环境光沿用公共工况；正式运行需单独核对资源限额。</p><p>待审核：列级 slot、两种研究入口、时序与门控层级、H 兼容路处理、输出格式与硬件约束。完整曲线、直方图通道筛选、彩色窗口和精确时间输入将沿用 B 的公共组件。</p><p>编辑左侧只改变设计草案，不更新图中参考数值，不回写配置，不提交任务。新尾迹 / 非均匀调度 / 内部事件 / 带宽队列未实现。</p><pre>${esc(JSON.stringify(data.configuration,null,2))}</pre>`;
  drawWaves();new ResizeObserver(drawWaves).observe($('txWave'));document.body.dataset.ready='true';
}
init().catch(error=>{$('loadError').textContent=`预览无法加载：${error.message}`;$('loadError').classList.remove('hidden');console.error(error);});
