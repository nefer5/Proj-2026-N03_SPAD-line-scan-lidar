/* High-level design contract. Derived quantities come from Python reference data.
 * Edited requirements remain pending; no duplicated budget formulas in JavaScript.
 */
'use strict';
let highLevelReady=false, highTargetIssued=false, highInputsState='reference';
const highInputMap={hlFrameRate:'frame_rate_hz',hlHfov:'hfov_mrad',hlUtilization:'scan_time_utilization',hlSlotCount:'slot_count'};
function collectHighInputs(){
  const values={};for(const [id,key] of Object.entries(highInputMap)){const raw=$(id).value;values[key]=raw===''?null:Number(raw);}
  if(values.scan_time_utilization!==null)values.scan_time_utilization/=100;
  if(values.hfov_mrad!==null){
    const degrees=values.hfov_mrad;
    // Preserve the exact canonical reference on a deg -> mrad round trip.
    values.hfov_mrad=degrees===data.high_level.derived.hfov_deg?data.high_level.inputs.hfov_mrad:degrees*Math.PI/180*1000;
  }
  return values;
}
function highInputError(v){
  if(Object.values(v).some(x=>x===null||!Number.isFinite(x)))return '四项系统目标都必须填写有限数值。';
  if(v.frame_rate_hz<=0||v.hfov_mrad<=0)return '帧率与 HFOV 必须大于零。';
  if(v.scan_time_utilization<=0||v.scan_time_utilization>1)return '扫描时间利用率需大于 0 且不超过 100%。';
  if(!Number.isSafeInteger(v.slot_count)||v.slot_count<1)return 'slot 数量必须为可精确表示的正整数列数。';return '';
}
function highIsReference(v){return Object.entries(data.high_level.inputs).every(([k,n])=>v[k]===n);}
function markUpstreamFields(){
  if(!highLevelReady)return;
  for(const key of ['scan.frame_rate_hz','scan.active_fraction','scan.angle_bin_width_mrad']){
    const el=document.querySelector(`[data-draft="${key}"]`);if(el){el.readOnly=true;el.title='此处保留基准参数；系统目标统一在 High Level 板块填写，重算计划后更新。';}
  }
}
function renderHighLevel(){
  const h=data.high_level,d=h.derived,input=collectHighInputs(),error=highInputError(input),same=!error&&highIsReference(input);
  highInputsState=error?'invalid':same?'reference':'pending';
  const shown=value=>same?value:'—';
  $('hlDegree').textContent='水平全视场角 · 输入单位 deg';
  $('highBudgetChain').innerHTML=[['01','帧周期',shown(`${fmt(d.frame_period_ns/1000)} μs`),'帧率 → 每帧时间'],['02','有效扫描可分配时间',shown(`${fmt(d.scan_allocatable_ns/1000)} μs`),'帧周期 × 扫描时间利用率'],['03','每列可用最大时间',shown(`${fmt(d.slot_max_ns/1000)} μs`),'可分配时间 → 均分到各列']].map(([n,title,value,note])=>`<div><span>${n}</span><article><small>${title}</small><strong>${value}</strong><p>${note}</p></article></div>`).join('');
  $('hlSlotTarget').textContent=shown(`${fmt(d.slot_target_ns/1000)} μs`);
  $('hlSlotMax').textContent=same?`等分上限 ${fmt(d.slot_max_ns/1000)} μs / 列`:'高层草案待计算，不能沿用旧目标';
  $('hlAngleStep').textContent=shown(`${fmt(d.angle_per_slot_mrad)} mrad / 列`);
  $('hlScanSpeed').textContent=shown(`${fmt(d.required_average_optical_rad_s)} rad/s`);
  $('pushHighTarget').disabled=!same;
  $('pushHighTarget').textContent=highTargetIssued?'重新下发参考目标':'下发参考目标到时序设计';
  $('highTargetState').classList.toggle('validation-error',!!error);
  $('highTargetState').textContent=error||(!same?'系统目标已改 · 预算待 Python 计算 · 前次下发已失效':highTargetIssued?'参考目标已下发 · 下层完成时间与资源可行性待验证':'参考预算就绪 · 尚未下发 · 编辑后的预算计算待正式接入');
  $('highAllocation').innerHTML=same?highAllocationDiagram(h):'<p class="high-pending">新的帧时间分配图与 T_slot 等待计算；下方已有数值图仍属于参考工况。</p>';
  $('receivedSlotTarget').textContent=highTargetIssued&&same?`${fmt(d.slot_target_ns/1000)} μs / 列`:'T_slot 待高层下发';
  $('receivedTargetState').textContent=highTargetIssued&&same?'High Level / 参考目标 · 未判定满足':'上方已有时序为基准，不自动充当新目标';
  markUpstreamFields();
}
function highAllocationDiagram(h){
  const d=h.derived,W=930,L=24,R=906,scale=t=>L+t/d.frame_period_ns*(R-L),split=scale(d.scan_allocatable_ns);
  let b=rect(L,26,split-L,37,'#235857')+rect(split,26,R-split,37,'#554535');
  b+=txt((L+split)/2,49,`扫描可分配 ${fmt(d.scan_allocatable_ns/1000)} μs · ${h.inputs.slot_count} 个列 slot`,'text-anchor="middle" class="hot"')+txt((split+R)/2,49,`非扫描 ${fmt(d.non_scan_ns/1000)} μs`,'text-anchor="middle" class="warm"');
  for(let i=1;i<h.inputs.slot_count;i++){const x=L+(split-L)*i/h.inputs.slot_count;b+=line(x,68,x,88,'#387879');}
  b+=line(L,78,split,78,'#387879')+txt(L,108,'0 μs','font-size="10"')+txt(split,108,`${fmt(d.scan_allocatable_ns/1000)} μs`,'text-anchor="middle" font-size="10"')+txt(R,108,`${fmt(d.frame_period_ns/1000)} μs`,'text-anchor="end" font-size="10"');
  return svg(W,123,b,'帧时间分成有效扫描列时间与非扫描时间，每列等分');
}
function renderHighCoupling(policy){
  setActive('data-hfov-policy',policy);
  $('hfovCoupling').textContent=policy==='columns'?'固定 slot 数：HFOV 增大 → 每列角宽增大、所需光学扫描速度增大；帧率与时间利用率不变时，T_slot 不变。':'固定角步距：HFOV 增大 → 需要更多整数列 → 每列时间预算缩短。应由高层选择列数与边缘覆盖策略，不能在下层偷偷增加 slot。';
}
function resetHighInputs(){
  for(const [id,key] of Object.entries(highInputMap))$(id).value=id==='hlHfov'?data.high_level.derived.hfov_deg:data.high_level.inputs[key]*(id==='hlUtilization'?100:1);
  highTargetIssued=false;renderHighLevel();
}
function exportHighLevelDraft(){return {inputs:collectHighInputs(),display_inputs:{hfov_deg:$('hlHfov').value===''?null:Number($('hlHfov').value)},state:highInputsState,source:'high_level_system_budget',allocation:'uniform_equal_share',issued_reference_target:highTargetIssued?{slot_target_ns:data.high_level.derived.slot_target_ns,input_sha256:data.high_level.input_sha256,review_only:true}:null};}
function initHighLevel(){
  highLevelReady=true;resetHighInputs();
  for(const id of Object.keys(highInputMap))$(id).oninput=()=>{highTargetIssued=false;setDraft('system_targets',collectHighInputs());renderHighLevel();};
  $('pushHighTarget').onclick=()=>{if(highInputsState!=='reference')return;highTargetIssued=true;renderHighLevel();$('jumpLowLevel').click();};
  $('resetHighTargets').onclick=()=>{resetHighInputs();setDraft('system_targets',collectHighInputs());};
  $('jumpLowLevel').onclick=()=>{$('exposureWorkspace').classList.remove('hidden');$('planningWorkspace').classList.add('hidden');document.querySelectorAll('[data-workspace]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.workspace==='exposure')));$('receivedSlotTarget').scrollIntoView({behavior:'smooth',block:'center'});};
  $('backToHighLevel').onclick=()=>$('highLevelPanel').scrollIntoView({behavior:'smooth',block:'start'});
  $('reset').addEventListener('click',resetHighInputs);
  document.querySelectorAll('[data-hfov-policy]').forEach(b=>b.onclick=()=>renderHighCoupling(b.dataset.hfovPolicy));renderHighCoupling('columns');
  $('highFormulas').innerHTML=data.high_level.formulas.map(f=>`<article><div id="formula-${f.id}" class="formula-box"></div><p>${esc(f.note)}</p></article>`).join('');
  for(const f of data.high_level.formulas){const el=$('formula-'+f.id);try{katex.render(f.latex,el,{displayMode:true,throwOnError:true});}catch(error){el.textContent=`公式渲染失败：${error.message} / ${f.latex}`;el.classList.add('validation-error');}}
}
