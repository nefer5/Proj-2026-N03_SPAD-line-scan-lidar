/* Explanation-only view: timing examples and resource measurements come from Python. */
'use strict';
const $=id=>document.getElementById(id),fmt=(v,d=3)=>Number(v).toLocaleString('en-US',{maximumFractionDigits:d});
let snapshot,selectedCase=0;
const concepts={
 slot:['slot 与累计发数','一个 slot 对应点云的一列。列开始分配工作缓冲；累计发数 N 是这一列参与同一直方图累积的曝光次数。规则时序用次数和间隔生成，自定义列表模式的 N 应由列表派生。'],
 gate:['发射周期与接收门','发射周期决定相邻 Tx 触发间隔；门宽决定每次允许记录的 ToF 范围。两者不是 slot 时长。此示例按相邻、不重叠的门展示；超出列末的门需要报错或明确单独的跨列策略。'],
 device:['SPAD 与 TDC','一次门内按所选读出模式处理。曝光之间只重新开放首事件/命中额度，SPAD 恢复和 TDC 忙状态延续；列间复位完成后，前端恢复到下一列的初始状态。'],
 accumulate:['跨曝光保留的，是同一份列直方图','每次用相对本次 Tx 的飞行时间查找时间分箱，再给同一通道的计数器累加。不是将多个曝光的绝对时刻摊成一条长直方图，也不是把单发随机结果直接乘 N。'],
 output:['先锁存上一列，再准备下一列','slot 结束保留完整一列的输出数据并交给 DSP。已确认 MIPI 位于 DSP 之后，用于输出处理结果。双缓冲允许上一列处理与下一列采集重叠，仍要检查真实吞吐和缓冲占用。'],
 reset:['列间完全复位，是明确的硬件边界','复位放在两个 slot 之间，另计入帧时间；耗时尚待提供。复位清理采集前端与下一列工作状态，不丢弃已锁存的上一列输出，也不会消除尚在飞行的旧回波。'],
 stats:['统计重复次数不等于累计发数','完整统计会按设定次数独立重复含噪采集与纯噪声采集；每次内部再累计 N 发。它用于误差棒和噪声均值。快速模式若未执行统计，应明确不展示对应统计曲线。']};
function showConcept(key){const [title,text]=concepts[key];$('conceptDetail').innerHTML=`<strong>${title}</strong><br>${text}`;document.querySelectorAll('[data-concept]').forEach(b=>b.classList.toggle('active',b.dataset.concept===key));}
function renderCase(index){selectedCase=index;const d=snapshot,c=d.cases[index],slot=d.slot_ns,domain=Math.max(slot,c.last_gate_close_ns)*1.06,left=145,pw=905,sx=t=>left+t/domain*pw;
 $('timingStatus').className='status'+(c.overrun_ns?'':' good');$('timingStatus').textContent=c.overrun_ns?`${c.shots} 发的最后接收门到 ${fmt(c.last_gate_close_ns/1000)} μs，超出本 slot ${fmt(c.overrun_ns/1000)} μs。当前示例未计任何额外复位时间。`:`${c.shots} 次完整曝光在 ${fmt(c.last_gate_close_ns/1000)} μs 结束，本 slot 剩余 ${fmt(c.remaining_ns/1000)} μs。列间复位在 slot 之外，耗时仍待定。`;
 document.querySelectorAll('[data-case]').forEach(b=>{b.classList.toggle('active',+b.dataset.case===index);b.setAttribute('aria-pressed',String(+b.dataset.case===index));});
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1110 355"><defs><pattern id="beyond" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#44292b"/><path d="M0 0V8" stroke="#895052"/></pattern></defs><rect x="${sx(0)}" y="47" width="${sx(slot)-sx(0)}" height="247" fill="#10313b" opacity=".45"/><rect x="${sx(slot)}" y="47" width="${sx(domain)-sx(slot)}" height="247" fill="url(#beyond)" opacity=".65"/><text x="${left}" y="25" fill="#94b6c8" font-size="11">本 slot 的局部时间 / μs</text>`;
 for(let i=0;i<=5;i++){const t=slot*i/5;svg+=`<path d="M${sx(t)} 42V305" stroke="#244151"/><text x="${sx(t)}" y="326" fill="#7f9eb2" text-anchor="middle" font-size="11">${fmt(t/1000)}</text>`;}
 const labels=[['Tx 触发',86],['接收门',153],['TDC 计时',220],['本列直方图',276]];for(const [label,y] of labels)svg+=`<text x="123" y="${y}" fill="#bcd7e6" text-anchor="end" font-size="12">${label}</text>`;
 for(const w of c.windows){const x=sx(w.trigger_ns),lo=sx(w.open_ns),hi=sx(w.close_ns),outside=w.close_ns>slot;svg+=`<g><title>曝光 ${w.index}：Tx ${fmt(w.trigger_ns/1000)} μs，门 ${fmt(w.open_ns/1000)}–${fmt(w.close_ns/1000)} μs</title><path d="M${x} 65V101" stroke="#5cddd0" stroke-width="2"/><text x="${x+5}" y="76" fill="#91d9d3" font-size="10">${w.index}</text><rect data-gate="${w.index}" x="${lo+1}" y="131" width="${hi-lo-2}" height="31" rx="3" fill="${outside?'#753e3d':'#22596a'}" stroke="${outside?'#ef9b7e':'#4c9bad'}"/><text x="${(lo+hi)/2}" y="152" fill="#d0e7ed" text-anchor="middle" font-size="10">G${w.index}</text><path d="M${x} 198V223" stroke="#d6b079"/><text x="${x+4}" y="215" fill="#d6b079" font-size="10">t=0</text></g>`;}
 svg+=`<rect x="${sx(0)}" y="254" width="${sx(slot)-sx(0)}" height="35" rx="4" fill="#214940" stroke="#5cb393"/><text x="${(sx(slot)+sx(0))/2}" y="277" fill="#b8ecce" text-anchor="middle" font-size="12">同一份列直方图 · 所有曝光累加到对应的 ToF 时间分箱</text><path d="M${sx(slot)} 39V300" stroke="#efbd76" stroke-dasharray="5 4"/><text x="${sx(slot)-7}" y="39" fill="#efbd76" text-anchor="end" font-size="11">slot 结束：锁存整列</text></svg>`;
 $('timingPlot').innerHTML=svg;
}
async function init(){const response=await fetch(document.body.dataset.snapshot,{cache:'no-store'});if(!response.ok)throw Error('说明快照载入失败');snapshot=await response.json();const d=snapshot;$('slotDurationNote').textContent='slot 有效采集时间：'+fmt(d.slot_ns/1000)+' μs 示例';$('repeatCostNote').textContent='保存的失败任务原设置为 '+d.trial_count+' 次含噪 + '+d.noise_trials+' 次纯噪声';concepts.device[1]+=' 当前工况：SPAD 死时间 '+fmt(d.spad_dead_time_ns)+' ns，TDC 死时间 '+fmt(d.tdc_dead_time_ns)+' ns，每 TDC 每曝光命中上限 '+d.hit_capacity_per_exposure+'。';
 $('parameterCards').innerHTML=[['slot 有效采集时长',fmt(d.slot_ns/1000)+' μs','一列的曝光预算','slot'],['累计发数 · 当前设置',d.cases[0].shots+' 发','同一列的曝光累积次数','accumulate'],['单次接收门宽',fmt(d.gate_width_ns)+' ns','每次曝光的 ToF 记录窗口','gate'],['相邻 Tx 间隔',fmt(d.period_ns)+' ns','当前规则发射周期','gate']].map(([name,value,note,key])=>`<button class="param-card" data-concept="${key}">${name}<strong>${value}</strong><small>${note}</small></button>`).join('');
 $('caseButtons').innerHTML=d.cases.map((c,i)=>`<button data-case="${i}">${c.label} · ${c.shots} 发</button>`).join('');for(const b of document.querySelectorAll('[data-case]'))b.onclick=()=>renderCase(+b.dataset.case);
 for(const b of document.querySelectorAll('[data-concept]'))b.onclick=()=>showConcept(b.dataset.concept);
 $('expandAll').onclick=()=>document.querySelectorAll('details').forEach(e=>e.open=true);$('collapseAll').onclick=()=>document.querySelectorAll('details').forEach(e=>e.open=false);
 $('resourceCards').innerHTML=[['候选事件 · 实际抽样',fmt(d.probe.sampled_candidates,0),'已取消本次诊断的预热'],['正式探测记录',fmt(d.probe.records,0),'与直方图累计值一致'],['单次采集耗时',fmt(d.probe.elapsed_s,2)+' s','含性能分析开销；不含光学预计算'],['列间复位时间','待提供','帧率可行性暂不能据此判定']].map(([name,value,note])=>`<article>${name}<strong class="${value==='待提供'?'pending':''}">${value}</strong><small>${note}</small></article>`).join('');
 showConcept('slot');renderCase(0);document.body.dataset.ready='true';
}
init().catch(e=>{$('error').hidden=false;$('error').textContent=e.message;});
