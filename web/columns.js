/* Formal C UI: collect configuration and render Python-computed plans/results. */
(function(){
'use strict';
const $=id=>document.getElementById(id),clone=structuredClone;
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=3)=>n===null||n===undefined?'—':Number(n).toLocaleString('en-US',{maximumFractionDigits:d});
const get=(o,p)=>p.split('.').reduce((v,k)=>v[k],o);
const set=(o,p,v)=>{const keys=p.split('.'),key=keys.pop();keys.reduce((x,k)=>x[k],o)[key]=v;};
const opt=(v,label)=>`<option value="${esc(v)}">${esc(label)}</option>`;
const text=(x,y,t,extra='')=>`<text x="${x}" y="${y}" font-size="11" ${extra}>${esc(t)}</text>`;
const rect=(x,y,w,h,fill,extra='')=>`<rect x="${x}" y="${y}" width="${Math.max(0,w)}" height="${h}" rx="3" fill="${fill}" ${extra}/>`;
const line=(a,b,c,d,color,extra='')=>`<line x1="${a}" y1="${b}" x2="${c}" y2="${d}" stroke="${color}" ${extra}/>`;
const svg=(w,h,body,label)=>`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">${body}</svg>`;
const colors={cyan:'#58d9cf',amber:'#e9b879',blue:'#78a9f6',purple:'#bf9be2',green:'#61bea6'};
const enumLabels={frame:'完整帧',columns:'显式列区间',per_pulse:'逐发门并集',column:'整列连续门',serial:'逐列串行',pipeline:'列间流水',duration:'直接指定耗时',payload:'数据量 / 净速率',points:'点云结果',histogram:'时间直方图',events:'原始时间戳',drop_column:'标记输出丢列',error:'超限报错',sawtooth:'锯齿往返',triangle:'三角往返',sinusoidal:'正弦摆扫',static:'固定方向',gaussian:'高斯',rectangular:'矩形',super_gaussian:'超高斯角分布',super_gaussian_psf:'超高斯 PSF',gaussian_psf:'高斯 PSF',uniform_pixel:'像素均匀参考',uniform:'均匀角分布',dataset:'导入数据库',gated:'门控',free_running:'自由运行',inverted:'倒置成像',legacy_upright:'历史正向映射',optical_centroid:'光学角质心',explicit:'显式标定',rectangle:'矩形',circle:'圆形',ellipse:'椭圆'};
const KEY='spad-columns-v4';
let catalog,config,editors,plan,budget,result,hist,resultJob=null,activeJob=null,pollTimer,previewTimer,budgetTimer,requestSerial=0,budgetSerial=0,controller;
let histogramKey=null;
let selection={frame:0,column:0,cycle:null},timelineRange=null,histRange=null,activeTab='exposure',figure='pulse',loading=false,timelineDragging=false;
async function request(url,body,signal){const r=await fetch(url,{cache:'no-store',signal,...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});const v=await r.json();if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:JSON.stringify(v.detail||v));return v;}
function error(e,origin='general'){$('errorBox').textContent=e.message||String(e);$('errorBox').dataset.origin=origin;$('errorBox').classList.remove('hidden');}
function clearError(){$('errorBox').classList.add('hidden');}
function download(name,value){const content=typeof value==='string'?value:JSON.stringify(value,null,2);const url=URL.createObjectURL(new Blob([content],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function help(path){return catalog.help.experiments?.columns?.[path]||catalog.help.experiments?.[path]||catalog.help[path.split('.').at(-1)]||{};}
function resolveSchema(s){return s?.$ref?catalog.schema.$defs[s.$ref.split('/').at(-1)]:s;}
function fieldSchema(path){let s=catalog.schema;for(const key of path.split('.'))s=resolveSchema(s).properties?.[key];return resolveSchema(s);}
function makeField(path,value){
 const h=help(path),s=fieldSchema(path),label=h.label||path.split('.').at(-1),choices=s?.enum;
 let type=s?.type,nullable=false;if(s?.anyOf){nullable=s.anyOf.some(x=>x.type==='null');type=s.anyOf.find(x=>x.type!=='null')?.type;}
 const wide=Array.isArray(value)||type==='object'||path==='rx.dataset';let input;
 if(choices)input=`<select data-path="${path}">${choices.map(v=>opt(v,catalog.readout_modes[v]?.label||enumLabels[v]||v)).join('')}</select>`;
 else if(type==='boolean'||typeof value==='boolean')input=`<input type="checkbox" data-path="${path}">`;
 else if(wide)input=`<textarea rows="3" data-path="${path}" data-json="true" spellcheck="false"></textarea>`;
 else input=`<input type="number" step="${type==='integer'?'1':'any'}" data-path="${path}" data-nullable="${nullable}" ${nullable?'placeholder="未配置 / 继承"':''}>`;
 return `<label class="${wide?'wide':''}" title="${esc(h.description||label)}"><span>${esc(label)}${h.unit?' / '+esc(h.unit):''}</span>${input}</label>`;
}
function renderConfiguration(){
 const high=[['frame_rate_hz','目标帧率','Hz'],['hfov_deg','HFOV','deg'],['scan_time_utilization','扫描时间利用率','%'],['slot_count','每帧 slot 数','列']];
 $('highInputs').innerHTML=high.map(([key,label,unit])=>`<label><span>${label}</span><div><input type="number" step="${key==='slot_count'?'1':'any'}" data-high="${key}" aria-label="${label}"><b>${unit}</b></div></label>`).join('');
 for(const el of document.querySelectorAll('[data-high]')){el.value=config.system_targets[el.dataset.high]*(el.dataset.high==='scan_time_utilization'?100:1);el.oninput=()=>changed(true);}
 const groups=[['motion','转镜与角度归档'],['acquisition','采集、门与统计'],['exposure','曝光与拖尾'],['tx','Tx 发射光学'],['rx','Rx 接收光学'],['spad','SPAD 线阵'],['readout','电子读出'],['scene','场景与目标'],['scene_motion','场景运动'],['background','太阳与其他环境光'],['transport','DSP / MIPI'],['diagnostics','器件轨迹选择']];
 const curves={rx:['filter'],spad:['pde'],background:['solar','other']};
 $('parameters').innerHTML=groups.map(([group,title])=>`<details class="parameter-group" ${['acquisition','exposure'].includes(group)?'open':''}><summary>${title}</summary><div class="parameter-body"><div class="field-grid">${groupedFields(group)}</div>${(curves[group]||[]).map(kind=>`<details class="wave-detail"><summary>${esc(catalog.curves.groups[kind].label)}输入</summary><div id="curve-${kind}"></div></details>`).join('')}${group==='exposure'?'<p class="field-note">逐发列表在右侧编辑；尾迹为基底波形的指数延迟分量，光学仍按中心姿态求值。</p>':''}${group==='transport'?'<p class="field-note">启用后必须填写有效耗时或数据格式 / 净速率。默认保留未知值。</p>':''}</div></details>`).join('');
 for(const el of document.querySelectorAll('[data-path]')){const v=get(config,el.dataset.path);if(el.type==='checkbox')el.checked=v;else if(el.dataset.json)el.value=v===null?'':JSON.stringify(v,null,2);else el.value=v===null?'':v;el.setAttribute('aria-label',help(el.dataset.path).label||el.dataset.path);el.oninput=()=>changed(false);}
 editors=new CurveEditors(catalog.curves,()=>changed(false),(kind,spec)=>request('/api/curve/validate?kind='+kind,spec));editors.fill(config.spectral_inputs);
 renderPulses();$('arrayNote').innerHTML=`<strong>H × V = ${config.spad.channels_h} × ${config.spad.channels_v}</strong><span>V 表示线数 · 所有H路参与计算<br>整列并行 / 共用器件模型</span>`;
}
const axisGroups={tx:[['H/V 角中心',['tx_center_h_mrad','tx_center_v_mrad']],['H/V FWHM',['tx_fwhm_h_mrad','tx_fwhm_v_mrad']],['H/V 超高斯阶数',['tx_order_h','tx_order_v']],['Tx H 角域',['angle_h_min_mrad','angle_h_max_mrad']],['Tx V 角域',['angle_v_min_mrad','angle_v_max_mrad']]],rx:[['H/V 等效焦距',['focal_length_h_mm','focal_length_v_mm']],['H/V PSF 标准差',['psf_sigma_h_um','psf_sigma_v_um']],['H/V PSF 阶数',['psf_order_h','psf_order_v']],['H/V 像面偏移',['rx_offset_x_um','rx_offset_y_um']],['入瞳 H/V 全尺寸',['rx_aperture_width_mm','rx_aperture_height_mm']],['Rx H 覆盖',['rx_angle_h_min_mrad','rx_angle_h_max_mrad']],['Rx V 覆盖',['rx_angle_v_min_mrad','rx_angle_v_max_mrad']]],spad:[['H/V 通道数',['channels_h','channels_v']],['H/V 空间合并',['H_binning','V_binning']]]};
function groupedFields(group){const pairs=axisGroups[group]||[],paired=new Set(pairs.flatMap(([,keys])=>keys));const singles=Object.entries(config[group]).filter(([key])=>!paired.has(key)&&!(group==='exposure'&&key==='pulses')&&!(group==='acquisition'&&key==='period_ns')).map(([key,v])=>makeField(group+'.'+key,v)).join('');return singles+pairs.map(([title,keys])=>`<fieldset class="hv-pair wide"><legend>${title}</legend>${keys.map(key=>makeField(group+'.'+key,config[group][key])).join('')}</fieldset>`).join('');}
function collect(){
 const next=clone(config);
 for(const el of document.querySelectorAll('[data-path]')){let v;if(el.type==='checkbox')v=el.checked;else if(el.dataset.json)v=el.value.trim()===''?null:JSON.parse(el.value);else if(el.tagName==='SELECT')v=el.value;else{if(el.value.trim()===''){if(el.dataset.nullable==='true')v=null;else throw Error((help(el.dataset.path).label||el.dataset.path)+'需要数值');}else{v=Number(el.value);if(!Number.isFinite(v))throw Error('需要有限数值：'+el.dataset.path);}}set(next,el.dataset.path,v);}
 for(const el of document.querySelectorAll('[data-high]')){if(el.value.trim()===''||!Number.isFinite(Number(el.value)))throw Error('高层目标需要有限数值');next.system_targets[el.dataset.high]=Number(el.value)/(el.dataset.high==='scan_time_utilization'?100:1);}
 next.exposure.pulses=[...$('pulseRows').querySelectorAll('tr')].map(row=>{const t=row.querySelector('[data-time]').value,e=row.querySelector('[data-energy]').value;if(t.trim()===''||!Number.isFinite(Number(t)))throw Error('逐发时间必须填写有限数值');if(e.trim()!==''&&!Number.isFinite(Number(e)))throw Error('单发能量需要有限数值');return {time_offset_ns:Number(t),energy_nj:e.trim()===''?null:Number(e)};});
 next.spectral_inputs=editors.values();return next;
}
function collectTargets(){const v=clone(config.system_targets);for(const el of document.querySelectorAll('[data-high]')){if(el.value.trim()===''||!Number.isFinite(Number(el.value)))throw Error('高层目标需要有限数值');v[el.dataset.high]=Number(el.value)/(el.dataset.high==='scan_time_utilization'?100:1);}return v;}
function changed(high){
 if(loading)return;requestSerial++;controller?.abort();$('stalePlan').classList.remove('hidden');$('draftState').textContent='已修改 · 待校验';$('runAcquisition').disabled=true;
 if(plan)$('receivedTarget').textContent='上次有效计划 · '+fmt(plan.system_budget.derived.slot_target_ns/1000)+' μs；待更新';
 if(high){budgetSerial++;clearTimeout(budgetTimer);budgetTimer=setTimeout(refreshBudget,catalog.algorithms.parameter_preview_debounce_ms);}
 try{config=collect();localStorage.setItem(KEY,JSON.stringify({schema_version:4,kind:'columns',experiment:config}));history.replaceState(null,'','/system/scan');}catch(e){$('updatePlan').disabled=false;error(e);return;}
 if(result)$('resultState').textContent='历史采集 · 当前草稿可能不同';
 clearTimeout(previewTimer);previewTimer=setTimeout(()=>refreshPreview(false),catalog.algorithms.parameter_preview_debounce_ms);
}
function renderPulses(){
 $('pulseRows').innerHTML=config.exposure.pulses.map((p,i)=>`<tr><td>P${i}</td><td><input data-time type="number" step="any" aria-label="第${i+1}发时间"></td><td><input data-energy type="number" step="any" placeholder="继承Tx" aria-label="第${i+1}发能量"></td><td><button data-remove="${i}">删此行</button></td></tr>`).join('');
 [...$('pulseRows').rows].forEach((row,i)=>{row.querySelector('[data-time]').value=config.exposure.pulses[i].time_offset_ns??'';row.querySelector('[data-energy]').value=config.exposure.pulses[i].energy_nj??'';row.querySelectorAll('input').forEach(el=>el.oninput=()=>changed(false));row.querySelector('button').onclick=()=>{try{config=collect();}catch(e){/* allow removing an incomplete row */}config.exposure.pulses.splice(i,1);renderPulses();changed(false);};});
 $('pulseJson').value=JSON.stringify(config.exposure.pulses,null,2);
}
async function refreshBudget(){const serial=++budgetSerial;try{const next=await request('/api/columns/budget',collectTargets());if(serial!==budgetSerial)return;budget=next;renderBudget();}catch(e){if(serial===budgetSerial){$('slotTarget').textContent='—';error(e);}}}
function renderBudget(){
 const b=budget.derived,c=budget.configuration;
 $('budgetChain').innerHTML=[['帧周期',`${fmt(b.frame_period_ns/1e6)} ms`],['扫描可分配时间',`${fmt(b.scan_allocatable_ns/1e6)} ms`],['每列最大时间',`${fmt(b.slot_max_ns/1000)} μs`]].map(([k,v],i)=>`<div><span>0${i+1}</span><article><small>${k}</small><strong>${v}</strong></article></div>`).join('');
 $('slotTarget').textContent=fmt(b.slot_target_ns/1000)+' μs';$('slotMaximum').textContent=`${c.slot_count} 列 / 帧 · ${fmt(c.frame_rate_hz)} Hz`;
 $('highRelations').innerHTML=`<article><span>角采样参考</span><b>${fmt(b.angle_per_slot_deg,5)} deg / 列</b><small>均匀角格参考，实际轨迹可非匀速</small></article><article><span>所需平均光学速度</span><b>${fmt(b.required_average_optical_rad_s)} rad/s</b><small>高层目标，实际转镜导数见下方</small></article>`;
 const W=900,L=20,R=880,split=L+(R-L)*b.scan_allocatable_ns/b.frame_period_ns;
 $('frameAllocation').innerHTML=svg(W,93,rect(L,12,split-L,35,'#23635f')+rect(split,12,R-split,35,'#635139')+text((L+split)/2,34,`扫描 ${fmt(b.scan_allocatable_ns/1e6)} ms / ${c.slot_count} 列`,'text-anchor="middle"')+text((split+R)/2,34,`非扫描 ${fmt(b.non_scan_ns/1e6)} ms`,'text-anchor="middle"')+text(L,75,'0 ms')+text(R,75,`${fmt(b.frame_period_ns/1e6)} ms`,'text-anchor="end"'),'一帧系统预算');
 $('highFormulas').innerHTML=budget.formulas.map((f,i)=>`<article><div class="formula-box" id="formula${i}"></div><p>${esc(f.note)}</p></article>`).join('');
 budget.formulas.forEach((f,i)=>renderMath($('formula'+i),f.latex));
}
function renderMath(el,latex){try{katex.render(latex,el,{displayMode:true,throwOnError:true});}catch(e){el.textContent='公式渲染失败：'+e.message+' / '+latex;}}
async function refreshPreview(resetWindow){
 const serial=++requestSerial;controller?.abort();controller=new AbortController();$('updatePlan').disabled=true;
 try{config=collect();if(selection.frame>=config.acquisition.frame_count)selection.frame=0;if(selection.column>=config.system_targets.slot_count)selection.column=0;
  const id=selection.frame*config.system_targets.slot_count+selection.column;
  const next=await request('/api/columns/preview?column_id='+id,config,controller.signal);if(serial!==requestSerial)return;plan=next;config=clone(plan.configuration.experiment);budget=plan.system_budget;renderBudget();
  $('draftState').textContent='计划已校验';$('stalePlan').classList.add('hidden');clearError();$('runAcquisition').disabled=plan.resource_probe.blocked;
  $('pulseNote').textContent=`完整计划 ${plan.frame_budget.trigger_count} 次触发；本次事件实验覆盖 ${plan.resource_probe.measured_columns} 列。计划帧均输入功率 ${fmt(plan.frame_budget.tx_input_average_power_w,6)} W。`;
  if(plan.resource_probe.blocked){error(plan.resource_probe.histogram_blocked?'计划已计算；距离分析工作量超过限额，可显式选取列区间或设置更粗的分析分箱。':`计划已计算；背景候选下界 ${fmt(plan.resource_probe.expected_noise_candidates_lower_bound,0)} 超过事件限额 ${fmt(plan.resource_probe.event_limit,0)}。可显式选择两列局部实验、调整背景/算法限额，或载入具名快速示例。`);const button=document.createElement('button');button.textContent='设为选中两列实验（保留当前背景）';button.onclick=()=>$('scopeTwo').click();$('errorBox').append(document.createElement('br'),button);}
  fillSelections();renderConcepts();renderMotion();renderTransport();renderFigure();renderAudit();if(resetWindow||!timelineRange||timelineRange[1]>timelineLimit())setTimelinePreset('columns');else renderTimeline();
  localStorage.setItem(KEY,JSON.stringify({schema_version:4,kind:'columns',experiment:config}));
 }catch(e){if(e.name!=='AbortError'){error(e);$('draftState').textContent='配置未通过';$('runAcquisition').disabled=true;}}finally{if(serial===requestSerial)$('updatePlan').disabled=false;}
}
function viewConfig(){return plan?plan.configuration.experiment:config;}
function currentTransport(){return result&&plan&&result.provenance.configuration_sha256===plan.provenance.configuration_sha256?result.transport:plan.transport;}
function selectedColumn(){return plan.columns[selection.frame*viewConfig().system_targets.slot_count+selection.column];}
function fillSelections(){
 $('frameSelect').innerHTML=Array.from({length:config.acquisition.frame_count},(_,i)=>opt(i,'帧 '+i)).join('');$('frameSelect').value=selection.frame;$('columnSelect').value=selection.column;$('columnSelect').max=config.system_targets.slot_count-1;
 const rows=plan.motion.selected_rows.filter(r=>r.has_pulse);if(!rows.some(r=>r.cycle===selection.cycle))selection.cycle=rows[0]?.cycle??null;
 $('pulseSelect').innerHTML=rows.map(r=>opt(r.cycle,`F${r.frame} S${r.column} / P${r.pulse_index} · ${fmt(r.energy_nj)} nJ`)).join('');if(selection.cycle!==null)$('pulseSelect').value=selection.cycle;
 $('receivedTarget').textContent=`高层下发 T_slot ${fmt(plan.system_budget.derived.slot_target_ns/1000)} μs / 列`;
 const labels={pulse:'Tx 波形 / 拖尾',filter:'滤光片',solar:'太阳光谱',environment:'环境光合成',pde:'PDE / FF',combined:'综合光谱响应',tx_profile:'Tx 角分布',mapping:'Rx H/V 映射',psf:'PSF'};
 $('figureSelect').innerHTML=Object.keys(plan.parameter_figures).map(k=>opt(k,labels[k]||k)).join('');$('figureSelect').value=figure;
}
function renderConcepts(){
 const config=viewConfig(),b=plan.system_budget.derived,N=config.system_targets.slot_count,V=config.spad.channels_v;
 let s=rect(20,27,240,90,'#18434a')+text(140,57,`${N} 列 × ${V} 行 / H 路`,'text-anchor="middle"')+text(140,82,'每列各行并行采集','text-anchor="middle"')+text(140,103,'H 路选择不等于硬件禁用','text-anchor="middle" font-size="10"');
 s+=line(269,70,323,70,colors.cyan,'stroke-width="2"')+rect(333,27,250,90,'#183349')+text(458,57,`一列 slot · ${fmt(b.slot_target_ns/1000)} μs`,'text-anchor="middle"')+text(458,83,`${config.exposure.pulses.length} 个逐发列表项`,'text-anchor="middle"')+text(458,105,'触发编号与列编号独立','text-anchor="middle" font-size="10"');
 s+=line(592,70,639,70,colors.amber,'stroke-width="2"')+rect(649,27,230,90,'#433a30')+text(764,57,'SPAD → DSP → MIPI','text-anchor="middle"')+text(764,82,'器件状态连续 / 双缓冲','text-anchor="middle"')+text(764,105,'下层按目标节拍检查资源','text-anchor="middle" font-size="10"');
 $('conceptDiagram').innerHTML=svg(900,145,s,'系统帧、列slot、逐发列表、共同SPAD与输出流水线');
}
function focusRow(){return plan.motion.selected_rows.find(r=>r.cycle===selection.cycle)||plan.motion.selected_rows[0];}
function renderMotion(){
 if(!plan)return;const config=viewConfig(),r=focusRow();if(!r){$('motionMetrics').innerHTML='<p>此列没有触发参考。</p>';return;}
 const ret=r.returns.find(x=>x.range_m===config.scene.range_m);
 $('motionMetrics').innerHTML=[['机械角速度',`${fmt(r.mechanical_velocity_rad_s)} rad/s`],['Tx 世界主轴角',`${fmt(r.true_tx_optical_mrad/1000*180/Math.PI,4)} deg`],['相邻 Tx 角差',r.previous_pulse_shift_mrad!==null?`${fmt(r.previous_pulse_shift_mrad,6)} mrad`:'首发'],['Rx 相对入射角',ret?`${fmt(ret.relative_rx_h_mrad,6)} mrad`:'—']].map(([k,v])=>`<div class="metric"><small>${k}</small><strong>${v}</strong></div>`).join('');
 PhotonPlots.drawSeries($('speedPlot'),{x_label:'帧内时间 / μs',y_label:'rad/s',series:[{x:plan.motion.frame_time_ns.map(t=>t/1000),y:plan.motion.optical_velocity_rad_s,color:'cyan'},{x:plan.motion.frame_time_ns.map(t=>t/1000),y:plan.motion.mechanical_velocity_rad_s,color:'amber'}]});
 PhotonPlots.drawSeries($('distancePlot'),{x_label:'静止中心目标距离 / m',y_label:'Rx相对入射角 / mrad',series:[{x:r.returns.map(v=>v.range_m),y:r.returns.map(v=>v.relative_rx_h_mrad),color:'blue'}]});
 $('motionTable').innerHTML=table(['距离 / m','飞行 / ns','到达时 Rx角 / mrad','相对入射角 / mrad','像面 x / μm'],r.returns.map(v=>[fmt(v.range_m),fmt(v.flight_ns),fmt(v.rx_axis_mrad,5),fmt(v.relative_rx_h_mrad,6),fmt(v.image_x_um,5)]))+`<p class="note">${esc(plan.motion.image_position_kind)}。${esc(plan.motion.note)}</p>`;
}
function timelineLimit(){return Math.max(plan.frame_budget.duration_ns,currentTransport().summary?.last_output_ns||0);}
function setTimelinePreset(mode){
 if(!plan)return;const config=viewConfig(),c=selectedColumn(),n=plan.columns[c.column_id+1],r=focusRow();
 if(mode==='frame')timelineRange=[selection.frame*plan.frame_budget.frame_period_ns,Math.max((selection.frame+1)*plan.frame_budget.frame_period_ns,currentTransport().summary?.last_output_ns||0)];
 else if(mode==='echo'&&r){const ret=r.returns.find(x=>x.range_m===config.scene.range_m),focus=plan.parameter_figures.pulse.series[0].x;const center=r.emission_time_ns+ret.flight_ns;timelineRange=[center+focus[0],center+focus.at(-1)];}
 else timelineRange=[c.start_ns,n?n.end_ns:c.end_ns];
 $('timeStart').value=Number(((timelineRange[0]-c.start_ns)/1000).toFixed(9));$('timeEnd').value=Number(((timelineRange[1]-c.start_ns)/1000).toFixed(9));renderTimeline();
}
function renderTimeline(){
 if(!plan||!timelineRange)return;const config=viewConfig(),transport=currentTransport(),[a,b]=timelineRange,L=150,R=910,W=940,lane=[48,91,134,177,220,263,306,349],sx=t=>L+(t-a)/(b-a)*(R-L),base=selectedColumn().start_ns;
 let body='<defs><clipPath id="c-time-clip"><rect x="150" y="24" width="760" height="350"/></clipPath></defs>';
 ['列 slot','实际 Tx 发射','中心回波参考','SPAD 器件门','TDC 记录门','DSP','MIPI → 主机','所存TDC触发'].forEach((label,i)=>{body+=text(12,lane[i]+4,label)+line(L,lane[i]+18,R,lane[i]+18,'#233c4e');});
 for(let i=0;i<=5;i++){const t=a+(b-a)*i/5;body+=line(sx(t),25,sx(t),370,'#203849')+text(sx(t),393,fmt((t-base)/1000,(b-a)<1000?6:3),'text-anchor="middle" font-size="10"');}
 let inside='';for(const c of plan.columns){if(c.end_ns<a||c.start_ns>b)continue;const x=sx(Math.max(a,c.start_ns)),right=sx(Math.min(b,c.end_ns));inside+=rect(x,lane[0]-12,right-x-1,24,c.column_id===selectedColumn().column_id?'#23645f':'#614d32');if(right-x>35)inside+=text((x+right)/2,lane[0]+4,`S${c.column}`,'text-anchor="middle"');}
 for(const r of plan.schedule){if(r.emitted&&r.emission_time_ns>=a&&r.emission_time_ns<=b){inside+=`<g><title>F${r.frame} S${r.column} P${r.pulse_index} / ${fmt(r.energy_nj)} nJ</title>`+line(sx(r.emission_time_ns),lane[1]-12,sx(r.emission_time_ns),lane[1]+12,colors.cyan,`stroke-width="${r.cycle===selection.cycle?3:1.5}"`)+'</g>';}
  for(const [lo,hi] of r.gate_segments_ns){if(hi<=a||lo>=b)continue;const x=sx(Math.max(a,lo)),width=sx(Math.min(b,hi))-x;inside+=rect(x,lane[4]-7,width,14,'#41618b');if(config.spad.detector_operation==='gated')inside+=rect(x,lane[3]-7,width,14,'#316172');}
 }
 if(config.spad.detector_operation==='free_running')inside+=rect(L,lane[3]-7,R-L,14,'#316172')+text(L+10,lane[3]+3,'free_running · 全程工作','font-size="10"');
 for(const r of plan.motion.selected_rows){if(!r.emitted)continue;const ret=r.returns.find(x=>x.range_m===config.scene.range_m),time=r.emission_time_ns+ret.flight_ns;if(time>=a&&time<=b)inside+=`<circle cx="${sx(time)}" cy="${lane[2]}" r="4" fill="${colors.amber}"/>`;}
 for(const [name,index,color] of [['dsp',5,colors.purple],['mipi',6,colors.green]]){if(!transport.rows.length){inside+=text(L+12,lane[index]+4,transport.note||'未配置资源时序','font-size="10"');continue;}for(const r of transport.rows){if(r.status!=='scheduled')continue;const lo=r[name+'_start_ns'],hi=r[name+'_end_ns'];if(hi<a||lo>b)continue;const x=sx(Math.max(a,lo)),right=sx(Math.min(b,hi));inside+=rect(x,lane[index]-11,Math.max(1,right-x),22,color,'opacity=".65"');if(right-x>50)inside+=text((x+right)/2,lane[index]+4,`S${r.column} / B${r.buffer_id}`,'text-anchor="middle" font-size="10"');}}
 if(result&&result.provenance.configuration_sha256===plan.provenance.configuration_sha256){for(const r of result.audit.trace){if(r.absolute_time_ns>=a&&r.absolute_time_ns<=b)inside+=`<circle cx="${sx(r.absolute_time_ns)}" cy="${lane[7]}" r="3" fill="${r.outcome==='recorded'?colors.green:'#e09287'}"><title>${esc(r.outcome)} · CH${r.group} · TDC${r.tdc}</title></circle>`;}}
 else inside+=text(L+12,lane[7]+4,'需要同一工况的采集轨迹','font-size="10"');
 body+=`<g clip-path="url(#c-time-clip)">${inside}</g>`+text(R,415,'μs · 相对所选列开始','text-anchor="end" font-size="10"');
 const extent=timelineLimit(),nx=t=>L+t/extent*(R-L);body+=rect(L,440,R-L,19,'#173340')+rect(nx(a),440,Math.max(3,nx(b)-nx(a)),19,'#ae804966','stroke="#edbc75"')+text(L,479,'全程导航 · 拖动定位','font-size="10"')+text(R,479,`${fmt(extent/1000)} μs`,'text-anchor="end" font-size="10"')+`<rect id="timelineNav" x="${L}" y="440" width="${R-L}" height="19" fill="transparent" style="cursor:ew-resize"/>`;
 $('timeline').innerHTML=svg(W,500,body,'列时序、实际发射、门并集与DSP/MIPI资源');
 $('timelineNote').textContent='竖线是事件标记，不代表实际脉宽。中心回波按所选列的静止参考距离绘制；梯度/运动的完整到达分布在逐发审计。DSP/MIPI块标注被处理的数据列，观测结束后可继续输出。';
 const move=e=>{const bounds=$('timeline').querySelector('svg').getBoundingClientRect();const t=((e.clientX-bounds.left)/bounds.width*W-L)/(R-L)*extent,span=timelineRange[1]-timelineRange[0];const start=Math.max(0,Math.min(extent-span,t-span/2));timelineRange=[start,start+span];$('timeStart').value=(start-base)/1000;$('timeEnd').value=(start+span-base)/1000;renderTimeline();};
 $('timelineNav').onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();timelineDragging=true;$('timeline').setPointerCapture(e.pointerId);move(e);};$('timeline').onpointermove=e=>{if(timelineDragging)move(e);};$('timeline').onpointerup=$('timeline').onpointercancel=()=>{timelineDragging=false;};
}
function renderTransport(){
 if(!plan)return;const config=viewConfig(),t=currentTransport();$('transportState').textContent={not_configured:'尚未配置',needs_acquisition:'等待完整事件数据量',scheduled:'排程完成',overloaded:'发生缓冲丢列'}[t.status]||t.status;
 if(!t.summary){$('transportMetrics').innerHTML='';$('transportSummary').textContent=t.note;$('transportRows').innerHTML='';return;}
 const s=t.summary;$('transportMetrics').innerHTML=[['输入列',s.input_columns],['计划输出列',s.delivered_columns],['丢列',s.dropped_columns],['缓冲占用峰值',s.peak_occupied_buffers]].map(([k,v])=>`<div class="metric"><small>${k}</small><strong>${fmt(v)}</strong></div>`).join('');
 $('transportSummary').innerHTML=`<p class="note">最大完成延迟 ${fmt(s.max_latency_ns/1000)} μs；末次输出 ${fmt(s.last_output_ns/1e6)} ms；平均载荷 ${fmt(s.average_payload_mbps)} Mbit/s。${esc(t.note)}</p>`;
 const id=selection.frame*config.system_targets.slot_count+selection.column;
 $('transportRows').innerHTML=t.rows.filter(r=>Math.abs(r.column_id-id)<=5).map(r=>`<tr><td>F${r.frame} S${r.column}</td><td>${r.buffer_id??'—'}</td><td>${fmt(r.data_ready_ns/1000)}</td><td>${r.dsp_start_ns===undefined?'—':fmt(r.dsp_start_ns/1000)+' → '+fmt(r.dsp_end_ns/1000)}</td><td>${r.mipi_start_ns===undefined?'—':fmt(r.mipi_start_ns/1000)+' → '+fmt(r.mipi_end_ns/1000)}</td><td class="${r.status==='scheduled'?'transport-ok':'transport-bad'}">${r.status==='scheduled'?'已排程':'无空闲缓冲丢列'}</td></tr>`).join('');
}
function renderFigure(){
 if(!plan||!$('parameterVisuals').open)return;const f=plan.parameter_figures[figure];$('figureTitle').textContent=f.title;PhotonPlots.drawSeries($('parameterPlot'),f);$('figureNote').textContent=f.note;
 $('figureFacts').innerHTML=(f.facts||[]).map(([k,v,u])=>`<span>${esc(k)} <b>${fmt(v,6)} ${esc(u)}</b></span>`).join('');$('parameterMap').classList.toggle('hidden',!f.heatmap);
 if(f.heatmap==='tx')heatmap($('parameterMap'),plan.optics.tx_energy_fraction,plan.optics.tx_h_edges_mrad,plan.optics.tx_v_edges_mrad,'H / mrad','V / mrad','能量份额');
 if(f.heatmap==='psf'){const m=f.psf_map;heatmap($('parameterMap'),m.values,m.x_edges_um,m.y_edges_um,'x / μm','y / μm',m.color_label);}
}
function heatmap(canvas,values,xEdges,yEdges,xlabel,ylabel,unit){
 const [ctx,w,h]=PhotonPlots.canvasSetup(canvas),L=58,R=w-55,T=27,B=h-42,rows=values.length,cols=values[0]?.length||0;
 const finite=values.flat().filter(v=>v!==null&&Number.isFinite(v));let lo=finite.length?finite.reduce((a,b)=>Math.min(a,b)):0,hi=finite.length?finite.reduce((a,b)=>Math.max(a,b)):0;
 ctx.clearRect(0,0,w,h);for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){const value=values[row][col];let color='#182d3b';if(value!==null&&Number.isFinite(value)){const q=hi===lo?.5:(value-lo)/(hi-lo);color=`rgb(${Math.round(18+222*q)},${Math.round(71+166*q)},${Math.round(95+51*q)})`;}ctx.fillStyle=(globalThis.LidarTheme?.color(color) ?? (color));ctx.fillRect(L+col/cols*(R-L),T+(rows-1-row)/rows*(B-T),(R-L)/cols+.3,(B-T)/rows+.3);}
 ctx.font='10px Consolas';ctx.fillStyle=(globalThis.LidarTheme?.color('#92b1c4') ?? ('#92b1c4'));ctx.textAlign='right';ctx.fillText(ylabel,L-7,16);ctx.textAlign='center';for(let i=0;i<=4;i++){ctx.textAlign=i===4?'right':i===0?'left':'center';ctx.fillText(fmt(xEdges[0]+(xEdges.at(-1)-xEdges[0])*i/4,2),L+(R-L)*i/4,B+17);ctx.textAlign='right';ctx.fillText(fmt(yEdges[0]+(yEdges.at(-1)-yEdges[0])*i/4,2),L-8,B-(B-T)*i/4+3);ctx.textAlign='center';}ctx.textAlign='right';ctx.fillText(xlabel,R,h-5);
 for(let i=0;i<100;i++){const q=i/99;ctx.fillStyle=(globalThis.LidarTheme?.color(`rgb(${Math.round(18+222*q)},${Math.round(71+166*q)},${Math.round(95+51*q)})`) ?? (`rgb(${Math.round(18+222*q)},${Math.round(71+166*q)},${Math.round(95+51*q)})`));ctx.fillRect(R+15,B-(B-T)*(i+1)/100,10,(B-T)/100+.5);}ctx.fillStyle=(globalThis.LidarTheme?.color('#aac3c8') ?? ('#aac3c8'));ctx.textAlign='left';ctx.fillText(hi!==0&&Math.abs(hi)<.001?hi.toExponential(2):fmt(hi,3),R+12,T-8);ctx.fillText(lo!==0&&Math.abs(lo)<.001?lo.toExponential(2):fmt(lo,3),R+12,B+16);ctx.fillText(unit,L,16);
}
function table(heads,rows){return `<table class="design-table"><thead><tr>${heads.map(v=>`<th>${esc(v)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(v=>`<td>${esc(v??'—')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
function renderAudit(){
 const source=activeTab==='results'&&result?result:plan;if(!source)return;
 $('auditContent').innerHTML=`<p>来源：${esc(source.provenance.scope)} · ${esc(source.provenance.model_version)} · ${esc(source.provenance.utc)}</p><p>配置指纹：${esc(source.provenance.configuration_sha256)}</p><pre>${esc(JSON.stringify(source.configuration,null,2))}</pre>${(source.limitations||[]).map(v=>`<p>${esc(v)}</p>`).join('')}`;
 const flow=activeTab==='results'?result?.photon_flow:null;$('photonFlow').innerHTML=flow?`<p>背景原始光子积分波段：${esc(flow.background_integration_band_nm.join(' — '))} nm</p>`+flow.steps.map((s,i)=>`<article class="flow-step"><h3>${esc(s.title)}</h3><p>${esc(s.logic)}</p><div class="math" id="flowMath${i}"></div><p>${esc(s.symbols)}</p><dl>${s.values.map(v=>`<dt>${esc(v.label)}</dt><dd>${fmt(v.value,8)} ${esc(v.unit)}</dd>`).join('')}</dl></article>`).join(''):'';
 if(flow)flow.steps.forEach((s,i)=>renderMath($('flowMath'+i),s.latex));
}
function switchTab(name){activeTab=name;for(const n of ['exposure','resources','results'])$(n+'Tab').classList.toggle('hidden',n!==name);document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===name)));if(name==='exposure'){renderMotion();renderFigure();}if(name==='resources')renderTransport();if(name==='results'){renderResultMaps();drawHistograms();}renderAudit();}
async function refreshJobs(){const jobs=await request('/api/jobs');$('jobSelect').innerHTML=jobs.filter(j=>j.kind==='columns').map(j=>opt(j.id,`${j.status} · ${j.created.slice(5,16)} · ${j.id.slice(0,6)}`)).join('');if(resultJob)$('jobSelect').value=resultJob;}
async function run(){try{clearError();await refreshPreview(false);if($('runAcquisition').disabled)return;const job=await request('/api/jobs',{kind:'columns',config:collect()});activeJob=job.id;$('cancelJob').disabled=false;await refreshJobs();poll();}catch(e){error(e);}}
async function poll(){clearTimeout(pollTimer);if(!activeJob)return;try{const job=await request('/api/jobs/'+activeJob);$('jobStatus').textContent=job.status+' · '+job.message;$('jobProgress').value=job.total?job.completed/job.total:0;
 if(job.status==='completed'){$('cancelJob').disabled=true;const id=activeJob;activeJob=null;await loadResult(id,true);await refreshJobs();}
 else if(['failed','cancelled','interrupted'].includes(job.status)){$('cancelJob').disabled=true;activeJob=null;error(job.message);await refreshJobs();}
 else pollTimer=setTimeout(poll,catalog.algorithms.job_poll_ms);
 }catch(e){error(e);pollTimer=setTimeout(poll,catalog.algorithms.job_poll_ms);}}
async function loadResult(id,restore){
 try{result=await request('/api/columns/jobs/'+id+'/view');resultJob=id;const saved=result.configuration.experiment;
  if(restore){loading=true;config=clone(result.form_configuration||saved);if(saved.acquisition.scope_mode==='columns'){selection.frame=Math.floor(saved.acquisition.scope_first_column/saved.system_targets.slot_count);selection.column=saved.acquisition.scope_first_column%saved.system_targets.slot_count;}renderConfiguration();loading=false;await refreshPreview(true);}
  $('resultFrame').innerHTML=Array.from({length:saved.acquisition.frame_count},(_,i)=>opt(i,'帧 '+i)).join('');$('resultFrame').value=result.frame;$('resultColumn').value=result.first_column??0;$('resultColumn').max=saved.system_targets.slot_count-1;
  $('hRoute').innerHTML=Array.from({length:saved.spad.channels_h},(_,i)=>opt(i,'H'+i)).join('');
  const totals=result.counts.map(r=>r.reduce((a,b)=>a+b,0));const strongest=totals.indexOf(Math.max(...totals));$('channelInput').value=String(strongest);$('histBin').value=saved.acquisition.analysis_bin_ps??saved.readout.tdc_bin_ps;
  $('downloadResult').href='/api/jobs/'+id+'/result';$('downloadRecords').href='/api/columns/jobs/'+id+'/records.csv';$('downloadPoints').href='/api/columns/jobs/'+id+'/point-cloud.csv';
  $('downloadResult').setAttribute('download',id+'-result.json');$('showIdeal').checked=true;$('showNoise').checked=result.statistics.noise_trial_count>0;$('showErrors').checked=result.statistics.trial_count>1;
  if(['scheduled','overloaded'].includes(result.transport.status))$('downloadDelivered').href='/api/columns/jobs/'+id+'/point-cloud.csv?delivered=true';else $('downloadDelivered').removeAttribute('href');
  renderResult();await loadHistogram();switchTab('results');history.replaceState(null,'','/system/scan?job='+encodeURIComponent(id));
 }catch(e){loading=false;error(e);}}
function renderResult(){if(!result)return;const s=result.summary;$('resultState').textContent=`${resultJob.slice(0,10)} · ${result.provenance.utc.slice(0,19)}`;$('resultMetrics').innerHTML=[['混合记录',result.audit.final_records],['点云列',s.column_count],['有原始估计的点',s.points_with_raw_estimate],['候选雪崩',result.audit.potential_events]].map(([k,v])=>`<div class="metric"><small>${k}</small><strong>${fmt(v,0)}</strong></div>`).join('');
 $('resultNote').textContent=`本次实际仿真 ${s.column_count} 列；系统规划仍为每帧 ${result.configuration.experiment.system_targets.slot_count} 列。未仿真的格点保持未知。条件RMSE ${fmt(s.conditional_rmse_m)} m 包含噪声峰，不代表已标定精度或检出率。重复采集 ${result.statistics.trial_count} 次，纯噪声 ${result.statistics.noise_trial_count} 次。`;
 $('deviceTrace').innerHTML=table(['t / ns','参考','物理像素','结果','记录门内','原恢复时刻 / ns','新恢复时刻 / ns'],result.audit.device_trace.map(r=>[fmt(r.time_ns,4),r.cycle,r.pixel_id,r.outcome==='avalanche'?'雪崩':'死时间丢弃',r.inside_recording_gate?'是':'否',fmt(r.ready_before_ns,4),fmt(r.ready_after_ns,4)]))+`<p class="note">所选轨迹事件 ${result.audit.device_trace_selected_events}，已存 ${result.audit.device_trace.length}；${result.audit.device_trace_truncated?'输出受限，完整统计仍保留。':'未截断。'}</p>`;renderResultMaps();renderAudit();renderTimeline();renderTransport();}
function parseChannels(value,limit){const out=new Set();for(const item of value.split(/[,，]/)){const match=item.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);if(!match)throw Error('通道格式示例：0, 2, 4-5');const lo=Number(match[1]),hi=match[2]===undefined?lo:Number(match[2]);if(lo>hi||hi>=limit)throw Error('通道超出范围');for(let i=lo;i<=hi;i++)out.add(i);}if(!out.size||out.size>catalog.algorithms.max_visible_channels)throw Error('显示通道数须为1到'+catalog.algorithms.max_visible_channels);return [...out].sort((a,b)=>a-b);}
async function loadHistogram(){if(!resultJob)return;try{const saved=result.configuration.experiment,f=Number($('resultFrame').value),col=Number($('resultColumn').value);if(!Number.isInteger(col)||col<0||col>=saved.system_targets.slot_count)throw Error('结果列编号超出范围');const key=resultJob+':'+f+':'+col;if(histogramKey!==key){histRange=null;histogramKey=key;}const channels=parseChannels($('channelInput').value,saved.spad.channels_h*saved.spad.channels_v),bin=Number($('histBin').value);hist=await request('/api/columns/jobs/'+resultJob+'/histogram',{column_id:f*saved.system_targets.slot_count+col,channels,bin_ps:bin,include_reference:true});
 const gate=[hist.histogram.edges_ns[0],hist.histogram.edges_ns.at(-1)];if(!histRange||histRange[0]<gate[0]||histRange[1]>gate[1])histRange=[...hist.focus_window_ns];
 $('histScope').textContent=`帧 ${f} · 列 S${col}`;$('showIdeal').disabled=!hist.references;$('showNoise').disabled=!hist.statistics.noise_mean;$('showErrors').disabled=!hist.statistics.upper;
 if(!hist.references)$('showIdeal').checked=false;if(!hist.statistics.noise_mean)$('showNoise').checked=false;if(!hist.statistics.upper)$('showErrors').checked=false;
 $('histNote').textContent=`${hist.reference_note} · 范围棒是${hist.statistics.trial_count}次独立采集的最小/最大值；纯噪声均值来自${hist.statistics.noise_trial_count}次激光关闭采集，未保存的统计不补造。`;
 $('rangeStats').innerHTML=hist.range_statistics.map(r=>`<span>CH${r.channel}：均值 <b>${fmt(r.mean_raw_distance_m)} m</b>，样本标准差 <b>${fmt(r.sample_std_m)} m</b>，有原始估计 ${r.valid_raw_estimates} 次</span>`).join('');renderHistograms();if($('errorBox').dataset.origin==='hist')clearError();
 }catch(e){error(e,'hist');}}
function renderHistograms(){if(!hist)return;const saved=result.configuration.experiment;$('histogramPlots').innerHTML=hist.channels.map((ch,i)=>`<article class="hist-card"><header><strong>CH ${ch} / H${ch%saved.spad.channels_h} V${Math.floor(ch/saved.spad.channels_h)}</strong><span>${fmt(hist.histogram.counts[i].reduce((a,b)=>a+b,0),0)} 记录</span></header><canvas class="hist-main" data-hist="${i}"></canvas><div class="hist-window-label"><span>全门概览 · 拖动窗口</span><span>橙色：当前窗口</span></div><canvas class="hist-overview" data-overview="${i}"></canvas><div class="hist-inputs"><label>起点 / ns<input type="number" step="any" data-hstart="${i}"></label><label>终点 / ns<input type="number" step="any" data-hend="${i}"></label><button data-happly="${i}">精确窗口</button></div></article>`).join('');
 const gate=[hist.histogram.edges_ns[0],hist.histogram.edges_ns.at(-1)];hist.channels.forEach((_,i)=>{PhotonHistogram.bindOverview(document.querySelector(`[data-overview="${i}"]`),gate,()=>histRange,range=>{histRange=range;drawHistograms();});document.querySelector(`[data-happly="${i}"]`).onclick=()=>{const lo=Number(document.querySelector(`[data-hstart="${i}"]`).value),hi=Number(document.querySelector(`[data-hend="${i}"]`).value);if(!Number.isFinite(lo)||!Number.isFinite(hi)||lo>=hi||lo<gate[0]||hi>gate[1]){error('窗口必须在分析门内，且终点大于起点');return;}histRange=[lo,hi];drawHistograms();};});drawHistograms();}
function drawHistograms(){if(!hist||activeTab!=='results')return;const layers={observed:$('showObserved').checked,ideal:$('showIdeal').checked,noise:$('showNoise').checked,error:$('showErrors').checked};const gate=[hist.histogram.edges_ns[0],hist.histogram.edges_ns.at(-1)];hist.channels.forEach((_,i)=>{const main=document.querySelector(`[data-hist="${i}"]`),overview=document.querySelector(`[data-overview="${i}"]`);if(!main)return;PhotonHistogram.draw(main,hist,i,histRange,PhotonHistogram.maximum(hist,i,histRange,layers),layers);PhotonHistogram.draw(overview,hist,i,gate,PhotonHistogram.maximum(hist,i,gate,{observed:true}),{observed:true},true,histRange);document.querySelector(`[data-hstart="${i}"]`).value=histRange[0];document.querySelector(`[data-hend="${i}"]`).value=histRange[1];});}
function renderResultMaps(){if(!result||activeTab!=='results')return;const c=result.configuration.experiment,h=Number($('hRoute').value),known=result.measured_column_ids.filter(id=>Math.floor(id/c.system_targets.slot_count)===result.frame).map(id=>id%c.system_targets.slot_count);const lower=$('mapExtent').value==='measured'&&known.length?known[0]:0,upper=$('mapExtent').value==='measured'&&known.length?known.at(-1)+1:c.system_targets.slot_count;const values=Array.from({length:c.spad.channels_v},(_,v)=>result.ranges[v*c.spad.channels_h+h].slice(lower,upper));heatmap($('rangeMap'),values,[lower,upper],[0,c.spad.channels_v],'列编号','V行','原始距离 / m');
 const [ctx,w,height]=PhotonPlots.canvasSetup($('pointPlot')),L=48,R=w-20,T=26,B=height-40,points=result.point_cloud.filter(p=>p.h_route===h);ctx.clearRect(0,0,w,height);if(!points.length){ctx.fillStyle=(globalThis.LidarTheme?.color('#9bb5c5') ?? ('#9bb5c5'));ctx.fillText('没有可显示的前向原始估计点',20,30);return;}
 const pair={xz:['x_m','z_m'],xy:['x_m','y_m'],yz:['y_m','z_m']}[$('pointProjection').value];
 const xs=points.map(p=>p[pair[0]]),zs=points.map(p=>p[pair[1]]),xmin=xs.reduce((a,b)=>Math.min(a,b)),xmax=xs.reduce((a,b)=>Math.max(a,b)),zmin=zs.reduce((a,b)=>Math.min(a,b)),zmax=zs.reduce((a,b)=>Math.max(a,b)),scale=Math.min((R-L)/Math.max(1,xmax-xmin),(B-T)/Math.max(1,zmax-zmin)),cx=(xmin+xmax)/2,cz=(zmin+zmax)/2,sx=x=>(L+R)/2+(x-cx)*scale,sy=z=>(T+B)/2-(z-cz)*scale;
 ctx.font='10px Consolas';ctx.strokeStyle=(globalThis.LidarTheme?.color('#203849') ?? ('#203849'));ctx.fillStyle=(globalThis.LidarTheme?.color('#91aec2') ?? ('#91aec2'));
 for(let i=0;i<=4;i++){const x=cx+(i/4-.5)*(R-L)/scale,z=cz+(i/4-.5)*(B-T)/scale;ctx.beginPath();ctx.moveTo(sx(x),T);ctx.lineTo(sx(x),B);ctx.moveTo(L,sy(z));ctx.lineTo(R,sy(z));ctx.stroke();ctx.textAlign='center';ctx.fillText(fmt(x,1),sx(x),B+17);ctx.textAlign='right';ctx.fillText(fmt(z,1),L-7,sy(z)+3);}
 ctx.fillStyle=(globalThis.LidarTheme?.color('#58d9cf') ?? ('#58d9cf'));for(const p of points)ctx.fillRect(sx(p[pair[0]]),sy(p[pair[1]]),2,2);ctx.fillStyle=(globalThis.LidarTheme?.color('#91aec2') ?? ('#91aec2'));ctx.textAlign='left';ctx.fillText(pair[1][0].toUpperCase()+' / m ↑（等比例）',L,15);ctx.textAlign='right';ctx.fillText(pair[0][0].toUpperCase()+' / m →',R,height-4);

}
function bind(){
 $('updatePlan').onclick=() =>refreshPreview(true);$('pushTarget').onclick=()=>refreshPreview(true);$('runAcquisition').onclick=run;
 $('collapse').onclick=()=>document.querySelectorAll('.parameter-group').forEach(d=>d.open=false);$('expand').onclick=()=>document.querySelectorAll('.parameter-group').forEach(d=>d.open=true);
 $('reset').onclick=async()=>{try{catalog=await request('/api/columns');loading=true;config=clone(catalog.defaults);localStorage.setItem(KEY,JSON.stringify({schema_version:4,kind:'columns',experiment:config}));renderConfiguration();loading=false;history.replaceState(null,'','/system/scan');if(result)$('resultState').textContent='历史采集 · 当前已恢复默认';await refreshPreview(true);}catch(e){loading=false;error(e);}};
 $('loadDemo').onclick=async()=>{try{config=await request('/api/columns/demo');localStorage.setItem(KEY,JSON.stringify({schema_version:4,kind:'columns',experiment:config}));renderConfiguration();history.replaceState(null,'','/system/scan');if(result)$('resultState').textContent='历史采集 · 当前为快速示例';await refreshPreview(true);$('draftState').textContent='具名快速示例 · DCR保留';}catch(e){error(e);}};
 $('scopeTwo').onclick=async()=>{try{config=collect();const start=selection.frame*config.system_targets.slot_count+selection.column,total=config.acquisition.frame_count*config.system_targets.slot_count;if(start+2>total)throw Error('所选位置不足连续两列，请选择前一列或手动设置单列实验。');config.acquisition.scope_mode='columns';config.acquisition.scope_first_column=start;config.acquisition.scope_column_count=2;renderConfiguration();await refreshPreview(true);$('draftState').textContent='两列局部实验 · 系统目标不变';}catch(e){error(e);}};
 $('addPulse').onclick=()=>{try{config=collect();}catch(e){error(e);return;}config.exposure.pulses.push({time_offset_ns:null,energy_nj:null});renderPulses();$('stalePlan').classList.remove('hidden');};
 $('applyPulseJson').onclick=()=>{try{const value=JSON.parse($('pulseJson').value);if(!Array.isArray(value))throw Error('必须是列表');value.forEach((p,i)=>{if(!p||typeof p!=='object'||Array.isArray(p)||Object.keys(p).sort().join(',')!=='energy_nj,time_offset_ns')throw Error(`第${i+1}行必须且只能包含time_offset_ns和energy_nj`);if(typeof p.time_offset_ns!=='number'||!Number.isFinite(p.time_offset_ns)||p.energy_nj!==null&&(typeof p.energy_nj!=='number'||!Number.isFinite(p.energy_nj)))throw Error('时间、能量须为数值；能量可用null显式继承');});config.exposure.pulses=value;renderPulses();changed(false);}catch(e){error(e);}};
 $('selectColumn').onclick=async()=>{try{const n=Number($('columnSelect').value);if(!Number.isInteger(n)||n<0||n>=config.system_targets.slot_count)throw Error('计划列编号超出范围');selection.frame=Number($('frameSelect').value);selection.column=n;await refreshPreview(true);}catch(e){error(e);}};
 $('pulseSelect').onchange=()=>{selection.cycle=Number($('pulseSelect').value);renderMotion();renderTimeline();};
 $('frameZoom').onclick=()=>setTimelinePreset('frame');$('columnZoom').onclick=()=>setTimelinePreset('columns');$('echoZoom').onclick=()=>setTimelinePreset('echo');
 $('applyTime').onclick=()=>{const a=Number($('timeStart').value)*1000+selectedColumn().start_ns,b=Number($('timeEnd').value)*1000+selectedColumn().start_ns;if(!Number.isFinite(a)||!Number.isFinite(b)||a<0||b<=a||b>timelineLimit()){error('时序窗口须位于计划 / 输出时域内，且终点大于起点');return;}timelineRange=[a,b];renderTimeline();};
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));$('parameterVisuals').ontoggle=renderFigure;$('figureSelect').onchange=()=>{figure=$('figureSelect').value;renderFigure();};$('exportFigure').onclick=()=>{if(plan)download('c-parameter-figure.json',plan.parameter_figures[figure]);};
 $('exportConfig').onclick=()=>{try{download('c-column-config.json',{schema_version:4,kind:'columns',experiment:collect()});}catch(e){error(e);}};
 $('importConfig').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const r=await fetch('/api/columns/import',{method:'POST',headers:{'Content-Type':'text/plain'},body:await file.text()});const value=await r.json();if(!r.ok)throw Error(value.detail);config=value;renderConfiguration();await refreshPreview(true);}catch(e){error(e);}};
 $('cancelJob').onclick=async()=>{if(activeJob)await request('/api/jobs/'+activeJob+'/cancel',{});};$('loadJob').onclick=()=>{if($('jobSelect').value)loadResult($('jobSelect').value,true);};
 $('updateHistogram').onclick=loadHistogram;$('histPeak').onclick=()=>{if(hist){histRange=[...hist.focus_window_ns];drawHistograms();}};$('histFull').onclick=()=>{if(hist){histRange=[hist.histogram.edges_ns[0],hist.histogram.edges_ns.at(-1)];drawHistograms();}};for(const id of ['showObserved','showIdeal','showNoise','showErrors'])$(id).onchange=drawHistograms;
 $('exportHistogram').onclick=()=>{if(hist)download('c-selected-histogram.json',hist);};$('hRoute').onchange=renderResultMaps;$('pointProjection').onchange=renderResultMaps;$('mapExtent').onchange=renderResultMaps;
 $('resultFrame').onchange=async()=>{try{result=await request('/api/columns/jobs/'+resultJob+'/view?frame='+$('resultFrame').value);if(result.first_column!==null)$('resultColumn').value=result.first_column;renderResult();if(result.first_column!==null)await loadHistogram();else error('此任务没有仿真所选帧；空白不表示零回波。');}catch(e){error(e);}};
 let resize;window.addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(()=>{renderMotion();renderFigure();drawHistograms();renderResultMaps();},100);});
}
async function init(){
 catalog=await request('/api/columns');config=clone(catalog.defaults);const stored=localStorage.getItem(KEY);
 if(stored){try{const doc=JSON.parse(stored);if(doc.schema_version!==4||doc.kind!=='columns')throw Error('旧草稿版本不兼容');config=await request('/api/experiments/columns/validate',doc.experiment);}catch(e){error('旧草稿未载入，已显示YAML默认值：'+e.message);}}
 const transfer=sessionStorage.getItem('lidar-system-to-columns');if(transfer){const doc=JSON.parse(transfer);config=await request('/api/experiments/columns/validate',doc.experiment);sessionStorage.removeItem('lidar-system-to-columns');}
 renderConfiguration();bind();await refreshPreview(true);await refreshJobs();const job=new URLSearchParams(location.search).get('job');if(job)await loadResult(job,true);document.body.dataset.ready='true';
}
init().catch(e=>{$('loadError').textContent='平台加载失败：'+e.message;$('loadError').classList.remove('hidden');console.error(e);});
})();
