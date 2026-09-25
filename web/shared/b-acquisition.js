/* B acquisition explanation and immutable-record views. No detector simulation here. */
(function(){
'use strict';
const fmt=(n,d=3)=>Number(n).toLocaleString('en-US',{maximumFractionDigits:d});
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
class BAcquisitionMechanism{
 constructor(root){this.root=root;}
 setModel(view,isResult){
  const c=view.acquisition_context;if(!c)throw Error('缺少 B 采集口径元数据，请刷新页面。');
  const initial=c.initialization.mode==='fully_recovered'?'本次采集开始时已完全恢复':`历史周期初态 · ${c.initialization.warmup_cycles} 次预热`;
  this.root.innerHTML=`<div class="ba-context">${isResult?'当前显示的采集工况':'当前参数预览'} · 配置 ${esc(view.provenance.configuration_sha256.slice(0,12))}</div><div class="ba-facts"><div><span>累计发数 N · 一份 slot 数据</span><strong>${c.shots} 发</strong><small>同一次采集内累加 N 次曝光</small></div><div class="ba-stat"><span>统计重复 M · 多份独立样本</span><strong>${c.trial_count===null?'未保存':c.trial_count+' 次'}</strong><small>${c.trial_count===null?'历史任务未保存重复统计':c.trial_count===0?'重复统计关闭；仍有一次完整采集':'蓝柱取首次；误差棒比较各轮，不再累加'}</small></div><div><span>本次 B 曝光序列长度</span><strong>${fmt(c.sequence_duration_ns/1000)} μs</strong><small>N 个发射周期；独立硬件 slot 上限尚未配置</small></div><div><span>单 gate 记录门宽</span><strong>${fmt(c.gate_width_ns)} ns</strong><small>Tx 间隔 ${fmt(c.period_ns)} ns · 门间空隙 ${fmt(c.gate_gap_ns)} ns</small></div></div>
  <div class="b-gate-example"><strong>区分示例：N＝3，M＝5。</strong>每轮累积3发得到一份slot直方图，共独立重复5轮；蓝柱取第1份，误差棒比较5份。不是把15发合成蓝柱。此示例不修改当前工况。</div><div class="ba-flow"><button data-step="start"><b>开始本列</b><small>${initial}</small></button><i>→</i><button data-step="expose"><b>重复 N 次曝光</b><small>Tx → 接收门 → SPAD/TDC</small></button><i>→</i><button data-step="sum"><b>同一列直方图</b><small>相对 Tx 的 ToF 分箱持续累加</small></button><i>→</i><button data-step="finish"><b>列末锁存 / 输出</b><small>结果交给 DSP → MIPI</small></button><i>→</i><button data-step="reset"><b>列间复位</b><small>工作机制示意 · 耗时另计帧预算</small></button></div><p class="ba-step-note" data-note></p>
  <div class="ba-timing" data-timing role="img" aria-label="当前工况的曝光触发、接收门与slot累积"></div><p class="field-note">Tx 竖线只标示触发时刻，不表示脉宽。${c.gate_preview_truncated?`仅画前 ${c.gate_preview_count} 个 gate，实际共 ${c.shots} 个；结果区累积过程图覆盖全部曝光。`:'本图覆盖本次全部曝光。'} </p>
  <div class="ba-equations"><span data-phase></span><span data-sum></span></div>
  <details class="explanation"><summary>曝光、slot 与统计重复的状态边界</summary><div class="matrix-scroll"><table><thead><tr><th>状态</th><th>下一次曝光</th><th>下一列 / 独立实验</th></tr></thead><tbody><tr><td>ToF 计时参考</td><td>改为本次 Tx</td><td>从新触发开始</td></tr><tr><td>首事件 / 命中次数额度</td><td>重新开放本次额度</td><td>复位</td></tr><tr><td>SPAD / TDC 恢复状态</td><td>按真实时间延续</td><td>B 的本次初态：${initial}</td></tr><tr><td>本列直方图</td><td>保留并继续累积</td><td>先锁存输出，再清空下一列工作缓冲</td></tr><tr><td>统计样本</td><td>N 发形成一份 slot 样本</td><td>M 次独立实验形成 M 份样本；不合成 M×N 发蓝柱</td></tr></tbody></table></div></details>
  <p class="ba-boundary">B 的“slot 累积”指本次 N 发曝光序列。当前模拟长度为 N 个发射周期；并未额外设置硬件 T_slot 上限。列间复位、DSP/MIPI 是整机工作机制说明，复位耗时和完整帧预算仍需在 C 接入；已锁存的上一列结果不能被复位清除。</p>`;
  const notes={start:`${initial}。初始化方式来自该任务的算法快照。`,expose:`每个 gate 内按读出模式处理；SPAD 死时间 ${fmt(c.spad_dead_time_ns)} ns，TDC 死时间 ${fmt(c.tdc_dead_time_ns)} ns。同一 slot 内重新开门不等于清空器件恢复状态。`,sum:`${c.shots} 次曝光在同一个 ToF 横轴上叠加。因此横轴只覆盖 ${fmt(c.gate_width_ns)} ns，蓝柱仍是整个 slot 的累计计数。`,finish:'每个读出通道输出一份本列直方图。采用双缓冲时，上一列处理可与下一列采集重叠；图中未虚构 DSP 或 MIPI 耗时。',reset:'按已确认架构，完全复位位于两个 slot 之间，耗时额外计入帧时间。它不删除已经锁存的数据，也不会使飞行中的旧回波消失。'};
  for(const b of this.root.querySelectorAll('[data-step]'))b.onclick=()=>{this.root.querySelector('[data-note]').textContent=notes[b.dataset.step];this.root.querySelectorAll('[data-step]').forEach(el=>el.classList.toggle('active',el===b));};
  this.root.querySelector('[data-step="sum"]').click();
  for(const [selector,key] of [['[data-phase]','b_gate_phase'],['[data-sum]','b_slot_accumulation']]){const el=this.root.querySelector(selector);try{katex.render(c.formulas[key],el,{throwOnError:true});el.title=c.formula_notes[key];}catch(e){el.textContent='公式渲染失败：'+c.formulas[key]+' / '+e.message;}}
  this.drawTiming(c);
 }
 drawTiming(c){
  const end=c.gate_preview_end_ns,left=115,width=780,sx=t=>left+t/end*width;
  let svg=`<svg viewBox="0 0 950 235" xmlns="http://www.w3.org/2000/svg"><text x="${left}" y="22" fill="#97b6c8" font-size="10">本次 B 序列时间 / μs</text>`;
  for(let i=0;i<=4;i++){const t=end*i/4;svg+=`<path d="M${sx(t)} 32V197" stroke="#294252"/><text x="${sx(t)}" y="222" text-anchor="middle" fill="#809caf" font-size="10">${fmt(t/1000)}</text>`;}
  for(const [label,y] of [['Tx 触发',57],['接收门',108],['slot 直方图',175]])svg+=`<text x="100" y="${y}" text-anchor="end" fill="#b5d0df" font-size="11">${label}</text>`;
  for(const w of c.gate_preview){const x=sx(w.trigger_ns),lo=sx(w.open_ns),hi=sx(w.close_ns);svg+=`<g><title>G${w.index}：${fmt(w.open_ns)}–${fmt(w.close_ns)} ns</title><path d="M${x} 38V68" stroke="#5bdbcf" stroke-width="2"/><rect x="${lo}" y="83" width="${hi-lo}" height="35" fill="#24556a" stroke="#68aab7"/>${hi-lo>28?`<text x="${(lo+hi)/2}" y="105" text-anchor="middle" fill="#c3e3ef" font-size="10">G${w.index}</text>`:''}</g>`;}
  svg+=`<rect x="${left}" y="148" width="${width}" height="43" rx="4" fill="#20493f" stroke="#55b392"/><text x="${left+width/2}" y="174" text-anchor="middle" fill="#b6e6c9" font-size="12">同一份 slot 直方图持续累积 · 不是 M 次统计结果叠加</text></svg>`;
  this.root.querySelector('[data-timing]').innerHTML=svg;
 }
}

class BHistogramViews{
 constructor(root,{request,onChange,onError,onExport}){
  this.root=root;this.request=request;this.onChange=onChange;this.onError=onError;this.serial=0;this.view=null;this.busy=false;
  root.innerHTML=`<div class="bh-controls"><label>探测结果范围<select data-scope aria-label="直方图采集范围"><option value="slot">slot 累积 · 全部 gate</option><option value="gate">单 gate · 实际记录</option></select></label><label data-gate-controls hidden>gate 索引<input type="number" step="1" min="0" data-gate aria-label="单gate索引"><button class="quiet small" data-apply>查看该 gate</button></label><span class="sample-label" data-badge></span><button class="quiet small" data-export-view disabled>导出当前视图 JSON</button></div><p class="bh-scope-note" data-note aria-live="polite"></p>`;
  this.q('export-view').onclick=()=>{if(this.view&&!this.busy)onExport(this.view);};
  this.q('scope').onchange=()=>{this.scope=this.q('scope').value;this.q('gate').value=String(this.gate);this.q('gate-controls').hidden=this.scope!=='gate';this.reload();};
  this.q('apply').onclick=()=>{const n=this.q('gate').valueAsNumber;if(!Number.isInteger(n)||n<0||n>=this.shots){this.onError(Error(`gate 索引须为 0–${this.shots-1} 的整数`));return;}this.gate=n;this.reload();};
  this.q('gate').onkeydown=e=>{if(e.key==='Enter')this.q('apply').click();};
 }
 q(key){return this.root.querySelector(`[data-${key}]`);}
 cancel(){this.serial++;this.controller?.abort();this.view=null;this.busy=false;}
 setModel(data,job,channels){this.cancel();this.job=job;this.shots=data.form_configuration.timing.laser_shots;this.scope='slot';this.gate=0;this.bin=data.record_schema.tdc_bin_ps;this.channels=[...channels];this.q('scope').value='slot';this.q('gate').value='0';this.q('gate').max=this.shots-1;this.q('gate-controls').hidden=true;this.root.classList.remove('hidden');return this.reload();}
 setChannels(channels){this.channels=[...channels];return this.reload();}
 setBin(bin){if(!Number.isFinite(bin)||bin<=0){this.onError(Error('分箱宽度需要正有限数值'));return false;}this.bin=bin;return this.reload();}
 async reload(){
  const serial=++this.serial;this.controller?.abort();this.controller=new AbortController();this.busy=true;this.view=null;this.q('export-view').disabled=true;
  this.q('badge').textContent=this.scope==='slot'?`slot · 累计发数 N=${this.shots}`:`单 gate · G${this.gate}`;
  this.q('note').textContent='正在读取所选范围的已保存记录…';this.onChange();
  try{const view=await this.request('/api/jobs/'+this.job+'/system-histogram',{scope:this.scope,gate_index:this.gate,bin_ps:this.bin,channels:this.channels},false,this.controller.signal);if(serial!==this.serial)return;this.view=view;this.busy=false;this.q('export-view').disabled=false;this.q('badge').textContent=view.scope_label;this.q('note').textContent=view.scope==='slot'?`横轴是相对每次 Tx 的 ToF；纵轴已经累计 ${view.shots_in_view} 个 gate。下方另画整个 slot 的逐门计数与累计过程。`:`只显示 G${view.gate_index} 的真实记录，不是把 slot 结果除以 N。${view.statistics_note}`;this.onChange();return true;}
  catch(e){if(e.name==='AbortError'||serial!==this.serial)return;this.busy=false;this.q('note').textContent='视图未更新：'+e.message;this.onError(e);this.onChange();return false;}
 }
}

function drawExposureTimeline(canvas,timeline,channel,selectedGate){
 const index=timeline.channels.indexOf(channel);if(index<0)return;
 const[c,w,h]=PhotonPlots.canvasSetup(canvas),left=46,right=49,top=25,bottom=28,pw=w-left-right,ph=h-top-bottom;
 const bars=timeline.counts[index],cum=timeline.cumulative_counts[index],last=timeline.sequence_duration_ns;
 const maxBar=Math.max(1,...bars),maxCum=Math.max(1,...cum),sx=t=>left+t/last*pw;
 c.clearRect(0,0,w,h);c.font='9px Consolas,monospace';c.fillStyle='#88a6bc';c.textAlign='left';c.fillText(timeline.grouped?'每组记录':'每门记录',left,12);c.fillStyle='#5bdbcf';c.textAlign='right';c.fillText('slot 累计',w-right,12);
 for(let i=0;i<=2;i++){const y=top+ph*(1-i/2);c.strokeStyle='#28404f';c.beginPath();c.moveTo(left,y);c.lineTo(w-right,y);c.stroke();c.fillStyle='#88a6bc';c.textAlign='right';c.fillText(fmt(maxBar*i/2,0),left-6,y+3);c.fillStyle='#5bdbcf';c.textAlign='left';c.fillText(fmt(maxCum*i/2,0),w-right+6,y+3);}
 for(let i=0;i<bars.length;i++){const x=left+i/bars.length*pw,bw=pw/bars.length;const active=selectedGate!==null&&selectedGate>=timeline.start_gate[i]&&selectedGate<=timeline.end_gate[i];c.fillStyle=active?'#dfb172':'#507fae';c.fillRect(x+1,top+ph*(1-bars[i]/maxBar),Math.max(.5,bw-2),ph*bars[i]/maxBar);}
 c.strokeStyle='#62decb';c.lineWidth=1.7;c.beginPath();c.moveTo(left,top+ph);let previous=0;
 timeline.gate_end_time_ns.forEach((t,i)=>{c.lineTo(sx(t),top+ph*(1-previous/maxCum));c.lineTo(sx(t),top+ph*(1-cum[i]/maxCum));previous=cum[i];});c.lineTo(sx(last),top+ph*(1-previous/maxCum));c.stroke();
 c.fillStyle='#85a4ba';for(let i=0;i<=4;i++){c.textAlign='center';c.fillText(fmt(last/1000*i/4,2),left+pw*i/4,h-12);}c.textAlign='right';c.fillText('slot 内时间 · μs',w-right,h-1);
}
globalThis.BAcquisitionMechanism=BAcquisitionMechanism;globalThis.BHistogramViews=BHistogramViews;globalThis.drawExposureTimeline=drawExposureTimeline;
})();
