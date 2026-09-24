/* C review extension: render Python geometry and explicit user-authored intervals.
 * No optical physics, detector model, queue solver or MIPI rate calculation in JS.
 */
'use strict';
let reviewReady=false, selectedMotionRange=null, pulsePlan=[], pulsePlanError='', transportPlan=null;
function motionPulseRow(cycle){return data.motion.columns.flatMap(c=>c.pulse_rows).find(p=>p.cycle===cycle);}
function referenceReturn(cycle){const p=motionPulseRow(cycle),r=selectedMotionRange===null?data.configuration.scene.range_m:selectedMotionRange;return p.returns.find(x=>x.base_range_m===r);}
function miniSeriesPlot(items,xLabel,yLabel){
  const W=470,H=230,L=68,R=449,T=28,B=181,xx=items.flatMap(s=>s.x),yy=items.flatMap(s=>s.y);
  let lo=Math.min(...yy),hi=Math.max(...yy),xmin=Math.min(...xx),xmax=Math.max(...xx);
  if(lo===hi){lo-=1;hi+=1;}const pad=(hi-lo)*.12;lo-=pad;hi+=pad;if(xmin===xmax)xmax=xmin+1;
  const sx=x=>L+(x-xmin)/(xmax-xmin)*(R-L),sy=y=>B-(y-lo)/(hi-lo)*(B-T);
  let b=txt(L,15,yLabel,'font-size="10"')+txt(R,224,xLabel,'font-size="10" text-anchor="end"');
  for(let i=0;i<=4;i++){const y=lo+(hi-lo)*i/4,x=xmin+(xmax-xmin)*i/4;b+=line(L,sy(y),R,sy(y),'#243e50')+txt(L-9,sy(y)+3,fmt(y,4),'text-anchor="end" font-size="10" class="mono"')+txt(sx(x),202,fmt(x,2),'text-anchor="middle" font-size="10" class="mono"');}
  for(const s of items){b+=`<polyline fill="none" stroke="${s.color}" stroke-width="1.6" points="${s.x.map((x,i)=>`${sx(x)},${sy(s.y[i])}`).join(' ')}"/>`;s.x.forEach((x,i)=>b+=`<circle cx="${sx(x)}" cy="${sy(s.y[i])}" r="3" fill="${s.color}"><title>${esc(s.label)} · ${fmt(x,6)}, ${fmt(s.y[i],6)}</title></circle>`);}
  return svg(W,H,b,`${yLabel} 随 ${xLabel} 变化，正值向上`);
}
function renderMotion(){
  const m=data.motion.columns.find(c=>c.pulse_rows.some(p=>p.cycle===focusCycle)),p=motionPulseRow(focusCycle),ret=referenceReturn(focusCycle),xs=m.pulse_rows.map(p=>p.offset_ns/1000);
  $('motionMetrics').innerHTML=[['机械角速度',`${fmt(p.mechanical_rad_s)} rad/s`,'所选发射时刻，不把摆扫频率叫 RPM'],['Tx 光学角速度',`${fmt(p.optical_rad_s)} rad/s`,`机械到光学角倍率 ${fmt(data.configuration.scan.optical_multiplier)}`],['相邻发射角偏移',p.dtx_previous_mrad===null?'首发':`${fmt(p.dtx_previous_mrad,5)} mrad`,p.dt_previous_ns===null?'列内无上一发':`前一发间隔 ${fmt(p.dt_previous_ns/1000)} μs`],['飞行中 Rx 转动',`${fmt(ret.rx_motion_mrad,5)} mrad`,`${fmt(ret.reflection_range_m)} m · ${fmt(ret.flight_ns)} ns`]].map(([a,b,c])=>`<div class="metric"><small>${a}</small><strong>${b}</strong><span>${c}</span></div>`).join('');
  $('angleWalkPlot').innerHTML=miniSeriesPlot([{x:xs,y:m.pulse_rows.map(p=>p.tx_mrad),color:palette.cyan,label:'Tx 发射方向'},{x:xs,y:m.pulse_rows.map(p=>referenceReturn(p.cycle).rx_axis_at_return_mrad),color:palette.amber,label:'回波到达时 Rx 主轴'}],'slot 内时间 / μs','世界角 H / mrad');
  $('returnAnglePlot').innerHTML=miniSeriesPlot([{x:p.returns.map(r=>r.reflection_range_m),y:p.returns.map(r=>r.relative_rx_h_mrad),color:palette.blue,label:'相对 Rx 入射角'}],'反射距离 / m','相对 Rx 入射角 / mrad');
  $('speedPlot').innerHTML=miniSeriesPlot([{x:data.motion.time_ns.map(t=>t/1000),y:data.motion.optical_rad_s,color:palette.cyan,label:'Tx 光学角速度'},{x:data.motion.time_ns.map(t=>t/1000),y:data.motion.mechanical_rad_s,color:palette.amber,label:'转镜机械角速度'}],'全帧时间 / μs','角速度 / rad·s⁻¹');
  $('motionExplanation').innerHTML=`当前 slot 镜面带动光学轴扫过 <strong>${fmt(m.slot_travel_mrad)} mrad</strong>，首发到末发扫过 <strong>${fmt(m.first_to_last_mrad)} mrad</strong>，两者不同。所选回波相对 Rx 入射角为 <strong>${fmt(ret.relative_rx_h_mrad,6)} mrad</strong>，由“发射时世界方向减去到达时 Rx 主轴方向”定义；当前倒置成像下，扫描运动带来的像面 x 位移为 <strong>${fmt(ret.motion_image_shift_um,4)} μm</strong>。<br>这是光斑中心参考；PSF 不变也不代表各通道截获能量不变。跨转向点按真实轨迹求角差，不套用恒速近似。光学飞行时间不包含电子标定延迟。`;
  const table=(heads,rows)=>`<table class="design-table"><thead><tr>${heads.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  $('motionTable').innerHTML=table(['发射','slot 内 / μs','机械角 / mrad','Tx 世界角 / mrad','上次间隔 / μs','Tx 角偏移 / mrad'],m.pulse_rows.map(p=>[`P${p.cycle}`,fmt(p.offset_ns/1000),fmt(p.mechanical_mrad),fmt(p.tx_mrad),p.dt_previous_ns===null?'—':fmt(p.dt_previous_ns/1000),p.dtx_previous_mrad===null?'—':fmt(p.dtx_previous_mrad,6)]));
  $('rangeTable').innerHTML=table(['反射距离 / m','光学飞行 / ns','Rx 世界角 / mrad','Rx 飞行中转角 / mrad','相对入射角 / mrad','像面运动位移 / μm'],p.returns.map(r=>[fmt(r.reflection_range_m),fmt(r.flight_ns),fmt(r.rx_axis_at_return_mrad,6),fmt(r.rx_motion_mrad,6),fmt(r.relative_rx_h_mrad,6),fmt(r.motion_image_shift_um,4)]));
}
function syncReviewSelection(){
  $('motionPulse').innerHTML=selectedColumn().pulses.concat(nextColumn().pulses).map(p=>option(p.cycle,`P${p.cycle} · ${fmt(p.emission_time_ns/1000)} μs`)).join('');$('motionPulse').value=focusCycle;renderMotion();
  if(pulsePlan.length){try{validatePulsePlan(pulsePlan);}catch(e){setPlanStatus(e.message);}}
}
function referencePulsePlan(){return selectedColumn().pulses.map(p=>({time_offset_ns:p.emission_time_ns-selectedColumn().start_ns,energy_nj:data.configuration.tx.total_pulse_energy_nj}));}
function validatePulsePlan(rows){
  const span=selectedColumn().end_ns-selectedColumn().start_ns;
  if(!Array.isArray(rows))throw Error('计划必须是 JSON list');
  if(rows.length>data.algorithm_configuration.scan_preview_table_rows)throw Error(`设计预览最多显示 ${data.algorithm_configuration.scan_preview_table_rows} 行，请缩小列表`);
  rows.forEach((r,i)=>{
    if(!r||typeof r!=='object'||Array.isArray(r)||Object.keys(r).sort().join(',')!=='energy_nj,time_offset_ns')throw Error(`第 ${i+1} 行只接受 time_offset_ns、energy_nj`);
    if(typeof r.time_offset_ns!=='number'||!Number.isFinite(r.time_offset_ns)||r.time_offset_ns<0||r.time_offset_ns>=span)throw Error(`第 ${i+1} 行时间需在 [0, ${fmt(span)}) ns 内`);
    if(typeof r.energy_nj!=='number'||!Number.isFinite(r.energy_nj)||r.energy_nj<0)throw Error(`第 ${i+1} 行能量必须是非负有限数`);
    if(i&&r.time_offset_ns<=rows[i-1].time_offset_ns)throw Error('时间必须严格递增；不自动排序或合并重复时刻');
  });
  return rows;
}
function setPlanStatus(error=''){
  pulsePlanError=error;$('pulsePlanStatus').classList.toggle('validation-error',!!error);
  $('pulsePlanStatus').textContent=error?`未应用：${error}。草案事件暂不绘制。`:`${pulsePlan.length} 发 / slot · ${pulsePlan.length?'时间与能量逐项配置':'空列表表示此 slot 不打光'}。紫色泳道展示该列表；回波、角度与探测结果仍为基准。`;
  renderTimeline();
}
function renderPulsePlan(){
  $('pulsePlanRows').innerHTML=pulsePlan.map((p,i)=>`<tr><td>D${i}</td><td><input type="number" step="any" data-pulse="${i}" data-part="time_offset_ns" aria-label="第${i+1}发时间 ns"></td><td><input type="number" step="any" data-pulse="${i}" data-part="energy_nj" aria-label="第${i+1}发能量 nJ"></td><td><button data-remove-pulse="${i}">删此行</button></td></tr>`).join('');
  $('pulsePlanRows').querySelectorAll('[data-pulse]').forEach(input=>{input.value=pulsePlan[Number(input.dataset.pulse)][input.dataset.part]??'';input.oninput=()=>{
    const value=input.value===''?null:Number(input.value);pulsePlan[Number(input.dataset.pulse)][input.dataset.part]=value;$('pulsePlanJson').value=JSON.stringify(pulsePlan,null,2);setDraft('tx.pulse_plan',pulsePlan);
    try{validatePulsePlan(pulsePlan);setPlanStatus();}catch(e){setPlanStatus(e.message);}
  };});
  $('pulsePlanRows').querySelectorAll('[data-remove-pulse]').forEach(b=>b.onclick=()=>{pulsePlan.splice(Number(b.dataset.removePulse),1);setDraft('tx.pulse_plan',pulsePlan);renderPulsePlan();});
  $('pulsePlanJson').value=JSON.stringify(pulsePlan,null,2);
  try{validatePulsePlan(pulsePlan);setPlanStatus();}catch(e){setPlanStatus(e.message);}
}
function applyTransport(){
  const ids=['dspStart','dspDuration','mipiStart','mipiDuration'],values=ids.map(id=>$(id).value);
  try{
    if(values.some(v=>v===''))throw Error('请填写 DSP 与 MIPI 的起点和耗时；空白不按零处理');
    const [ds,dd,ms,md]=values.map(Number),span=(selectedColumn().end_ns-selectedColumn().start_ns)/1000;
    if(![ds,dd,ms,md].every(Number.isFinite)||ds<span||dd<0||ms<0||md<0)throw Error(`DSP 从整列锁存后开始，起点至少 ${fmt(span)} μs；耗时须非负且有限`);
    if(ms<ds+dd)throw Error('已选 DSP 后输出：MIPI 起点不能早于本列 DSP 结束');
    transportPlan={dsp_start_us:ds,dsp_duration_us:dd,mipi_start_us:ms,mipi_duration_us:md};
    setDraft('transport.explicit_intervals',transportPlan);$('transportStatus').classList.remove('validation-error');$('transportStatus').textContent='已绘制输入区间 · 双缓冲 / DSP后输出 · 未求解排队与资源冲突';
  }catch(e){transportPlan=null;$('transportStatus').classList.add('validation-error');$('transportStatus').textContent=e.message;}
  renderTimeline();
}
function clearTransport(){transportPlan=null;['dspStart','dspDuration','mipiStart','mipiDuration'].forEach(id=>$(id).value='');$('transportStatus').textContent='耗时待定义 · 不等于零';$('transportStatus').classList.remove('validation-error');renderTimeline();}
function reviewTimelineLanes(sx,a,b,lane){
  let out='';
  if(!reviewReady||pulsePlanError)out+=txt(167,lane[7]+4,pulsePlanError?'逐发列表无效，请修正输入':'逐发计划加载中','font-size="11"');
  else if(!pulsePlan.length)out+=txt(167,lane[7]+4,'空列表 · 此列模板不发射','font-size="11"');
  else data.columns.forEach(c=>pulsePlan.forEach((p,i)=>{const t=c.start_ns+p.time_offset_ns;if(t>=a&&t<b){const color=p.energy_nj===0?'#839dad':'#c39ce4';out+=`<g><title>${esc(`S${c.index} / D${i} · ${fmt(p.time_offset_ns)} ns · ${fmt(p.energy_nj)} nJ${p.energy_nj===0?' · 暗触发':''}`)}</title>`+line(sx(t),lane[7]-12,sx(t),lane[7]+12,color,'stroke-width="2"')+'</g>';const next=pulsePlan[i+1],prev=pulsePlan[i-1],room=(!next||sx(c.start_ns+next.time_offset_ns)-sx(t)>70)&&(!prev||sx(t)-sx(c.start_ns+prev.time_offset_ns)>70);if(room&&(b-a)/(c.end_ns-c.start_ns)<4)out+=txt(sx(t)+5,lane[7]-3,`D${i} · ${fmt(p.energy_nj)} nJ`,'font-size="9"');}}));
  for(const [name,index,color] of [['dsp',8,'#8563aa'],['mipi',9,'#31867a']]){
    if(!transportPlan){out+=line(152,lane[index],900,lane[index],'#62727e','stroke-dasharray="5 5"')+rect(161,lane[index]-12,460,25,'#0b1722')+txt(167,lane[index]+4,`${name==='dsp'?'DSP':'MIPI → 主机'}：耗时待定义，可处理上一列；不填造数值块`,'font-size="11"');continue;}
    data.columns.forEach(c=>{const start=c.start_ns+transportPlan[`${name}_start_us`]*1000,end=start+transportPlan[`${name}_duration_us`]*1000;if(end<a||start>=b)return;const x=sx(Math.max(a,start)),right=sx(Math.min(b,end));out+=rect(x,lane[index]-12,Math.max(1,right-x),24,color,'opacity=".85"');if(right-x>48)out+=txt((x+right)/2,lane[index]+4,`S${c.index} · ${name==='dsp'?'DSP':'MIPI'}`,'font-size="10" text-anchor="middle"');});
  }
  return out;
}
function exportReviewDraft(){return {architecture:{buffering:'double',mipi_path:'dsp_to_host'},tx_pulse_list:pulsePlan,pulse_list_error:pulsePlanError||null,transport_intervals:transportPlan,transport_raw_inputs:Object.fromEntries(['dspStart','dspDuration','mipiStart','mipiDuration'].map(id=>[id,$(id).value])),calculated:false};}
function initReviewV2(){
  selectedMotionRange=data.configuration.scene.range_m;
  $('motionRange').innerHTML=data.motion.range_values_m.map(r=>option(r,`${fmt(r)} m`)).join('');$('motionRange').value=selectedMotionRange;
  $('motionRange').onchange=e=>{selectedMotionRange=Number(e.target.value);renderMotion();renderTimeline();drawWaves();};
  $('motionPulse').onchange=e=>{focusCycle=Number(e.target.value);$('pulseSelect').value=focusCycle;renderMotion();renderTimeline();drawWaves();};
  reviewReady=true;pulsePlan=referencePulsePlan();renderPulsePlan();syncReviewSelection();
  $('addPulse').onclick=()=>{pulsePlan.push({time_offset_ns:null,energy_nj:null});setDraft('tx.pulse_plan',pulsePlan);renderPulsePlan();};
  $('restorePulsePlan').onclick=()=>{pulsePlan=referencePulsePlan();setDraft('tx.pulse_plan',pulsePlan);renderPulsePlan();};
  $('applyPulseJson').onclick=()=>{try{const parsed=JSON.parse($('pulsePlanJson').value);validatePulsePlan(parsed);pulsePlan=parsed;setDraft('tx.pulse_plan',pulsePlan);renderPulsePlan();}catch(e){setPlanStatus(e.message);}};
  $('pulsePlanJson').oninput=()=>{setPlanStatus('JSON 有待载入的修改');};
  $('applyTransport').onclick=applyTransport;$('clearTransport').onclick=()=>{clearTransport();setDraft('transport.explicit_intervals',null);};
  ['dspStart','dspDuration','mipiStart','mipiDuration'].forEach(id=>$(id).oninput=()=>{transportPlan=null;$('transportStatus').textContent='输入已变更，请点击“显示时间草案”';setDraft(`transport.${id}`,$(id).value);renderTimeline();});
  $('reset').addEventListener('click',()=>{pulsePlan=referencePulsePlan();renderPulsePlan();clearTransport();});
}
