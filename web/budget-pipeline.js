/* Resource schedules are Python results. This module only lays out SVG. */
(function(){
 const f=v=>BudgetNumbers.format(v),esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const label=(x,y,s,cls='',anchor='start')=>`<text x="${x}" y="${y}" class="pipeline-label ${cls}" text-anchor="${anchor}">${esc(s)}</text>`;
 class TimelineViewport{
  constructor(){this.key=null;this.full=0;this.lo=0;this.hi=0;}
  ensure(key,full){if(!Number.isFinite(full)||full<=0)throw Error('时序图时间范围无效');if(key!==this.key||full!==this.full){this.key=key;this.full=full;this.lo=0;this.hi=full;}}
  set(lo,hi){const span=Math.min(this.full,Math.max(this.full/128,hi-lo));this.lo=Math.max(0,Math.min(this.full-span,lo));this.hi=this.lo+span;}
  zoom(factor,anchor){const span=this.hi-this.lo,point=this.lo+span*anchor,newSpan=Math.min(this.full,Math.max(this.full/128,span*factor));this.set(point-newSpan*anchor,point+newSpan*(1-anchor));}
  pan(delta){this.set(this.lo+delta,this.hi+delta);}
 }
 const viewport=new TimelineViewport();let currentResult=null,drag=null;
 function renderContent(result){
  const s=result.electrical.selected,p=s.pipeline;
  if(!s.complete||!p?.feasible)return `<div class="pipeline-unavailable">${esc(p?.note||s.note||'时序输入未完整。')}<p>数据量预算仍可在电学板块查看；没有假定无限缓存或自动裁剪。</p></div>`;
  const rows=p.rows,t=result.timing,single=p.architecture==='single',bypass=p.dsp_bypassed;
  const lanes=[['采集 '+(single?'SRAM':'A'),'capture_start_ns','capture_end_ns','capture'],['采集块清零','clear_start_ns','clear_end_ns','clear'],[single?'搬移 · 旁路':'A → B 搬移','copy_start_ns','copy_end_ns','copy'],['DSP 输入延时','input_start_ns','input_end_ns','input'],[bypass?'DSP · Hist旁路':(single?'片内 DSP':'B · 片内 DSP'),'dsp_start_ns','dsp_end_ns','dsp'],['等待 FIFO 空位','dsp_end_ns','commit_ns','wait'],['输出 FIFO 占用','fifo_start_ns','fifo_end_ns','fifo'],['MIPI 应用打包','pack_start_ns','pack_end_ns','pack'],['D-PHY 发送','start_ns','end_ns','send']];
  const end=Math.max(...rows.map(r=>r.end_ns),(rows.length)*t.slot_max_ns),left=156,right=906,top=42,stride=30,half=7,bottom=top+stride*(lanes.length-1)+18;
  viewport.ensure(result.provenance.configuration_sha256,end);
  const lo=viewport.lo,hi=viewport.hi,span=hi-lo;
  const x=v=>left+(v-lo)/span*(right-left),y=i=>top+i*stride;
  let body='',connections='',axisLabels='',rowLabels='';
  for(let i=0;i<=6;i++){const time=lo+span*i/6;body+=`<path d="M${x(time)} 27V${bottom}" class="pipeline-grid"/>`;axisLabels+=label(x(time),bottom+24,f(time/1000),'pipeline-muted','middle');}
  lanes.forEach(([name],i)=>{rowLabels+=label(12,y(i)+4,name);body+=`<path d="M${left} ${y(i)+half+3}H${right}" class="pipeline-baseline"/>`;});
  for(const [index,row] of rows.entries()){
   body+=`<path d="M${x(row.planned_ns)} 26V${bottom}" class="pipeline-slot-boundary"/>`+label(x(row.planned_ns)+4,18,'目标 S'+row.column,'pipeline-muted');
   if(row.delay_ns>0)body+=label(x(row.capture_start_ns)+4,31,'采集 S'+row.column,'pipeline-muted');
   lanes.forEach(([name,a,b,kind],i)=>{const duration=row[b]-row[a];
    if(duration<=0){if(['copy','input','dsp'].includes(kind))body+=`<path d="M${x(row[a])} ${y(i)-half}V${y(i)+half}" class="pipeline-zero-event"><title>S${row.column} · ${name}：0 μs，交接时刻 ${f(row[a]/1000)} μs</title></path>`;return;}
    const px=x(row[a]),width=Math.max(1,x(row[b])-px),yy=y(i)-half;
    body+=`<rect x="${px}" y="${yy}" width="${width}" height="${half*2}" class="pipeline-block pipeline-${kind} slot-tone-${index}"><title>S${row.column} · ${name}：${f(row[a]/1000)}–${f(row[b]/1000)} μs；时长 ${f(duration/1000)} μs</title></rect>`;
    if(kind==='send'&&width>58)body+=label(px+width/2,yy+10,(width>90?'S'+row.column+' · ':'')+f(duration/1000)+' μs','pipeline-in-block','middle');else if(width>30)body+=label(px+width/2,yy+10,'S'+row.column,'pipeline-in-block','middle');
   });
   // Orthogonal handoffs: a vertical line for shared time, a horizontal segment
   // when the downstream resource is still occupied. Do not align false events.
   const dependencies=single?[[row.capture_end_ns,row.input_start_ns,0,3],[row.dsp_end_ns,row.commit_ns,4,6],[row.commit_ns,row.clear_start_ns,6,1]]:
    [[row.capture_end_ns,row.copy_start_ns,0,2],[row.copy_end_ns,row.clear_start_ns,2,1],[row.copy_end_ns,row.input_start_ns,2,3],[row.dsp_end_ns,row.commit_ns,4,6]];
   dependencies.push([row.input_end_ns,row.dsp_start_ns,3,4],[row.commit_ns,row.pack_start_ns,6,7],[row.pack_end_ns,row.start_ns,7,8]);
   const previous=rows[index-1];
   if(previous&&row.capture_start_ns===previous.clear_end_ns)dependencies.push([previous.clear_end_ns,row.capture_start_ns,1,0,'采集块释放']);
   if(previous&&!single&&row.copy_start_ns>row.hist_ready_ns)dependencies.push([previous.commit_ns,row.copy_start_ns,6,2,'B释放']);
   for(const [a,b,from,to,resource] of dependencies){
    const direction=to>from?1:-1,ya=y(from)+direction*half,yb=y(to)-direction*half,mid=from===4&&to===6?y(5)+half+3:(ya+yb)/2,kind=resource?' pipeline-resource-dependency':'';
    connections+=`<g class="pipeline-connector${kind}"><title>S${row.column} ${resource||'数据交接'}：${f(a/1000)} → ${f(b/1000)} μs</title><path d="M${x(a)} ${ya}V${mid}H${x(b)}V${yb}" class="pipeline-dependency"/><path d="M${x(a)} ${ya}v${direction*3}M${x(b)} ${yb}v${-direction*3}" class="pipeline-dependency-cap"/><circle cx="${x(a)}" cy="${ya}" r="1.35" class="pipeline-junction"/><circle cx="${x(b)}" cy="${yb}" r="1.35" class="pipeline-junction"/></g>`;
   }
   for(const shot of t.rows){const time=row.capture_start_ns+shot.emission_ns;if(time<=row.capture_end_ns)body+=`<path d="M${x(time)} ${y(0)-half-1}V${y(0)+half}" class="pipeline-emission"><title>S${row.column} 第${shot.pulse}发，${f(time/1000)} μs</title></path>`;}
  }
  body+=connections;axisLabels+=label(right,bottom+45,'时间 / μs →','pipeline-muted','end');
  const name=single?'单缓冲 · 串行复用':'双缓冲 · 固定 A采集 / B处理';
  return `<div class="pipeline-heading"><strong>${name}</strong><span>首 ${rows.length} 个 slot · ${bypass?'全Hist旁路DSP':result.electrical.format==='echo'?'Echo最坏上限':'Range完整点'}</span></div>${toolbar(lo,hi,end)}<svg class="pipeline-svg" data-view-start-ns="${lo}" data-view-end-ns="${hi}" viewBox="0 0 944 ${bottom+58}" role="img" aria-label="三个slot的采集、搬移、DSP、FIFO背压与MIPI传输依赖"><defs><clipPath id="budgetTimingClip"><rect x="154" y="0" width="754" height="${bottom+2}"/></clipPath></defs>${rowLabels}<g clip-path="url(#budgetTimingClip)">${body}</g>${axisLabels}</svg><div class="pipeline-legend">${[['capture','采集 / 多发'],['copy','Hist搬移'],['dsp','片内DSP'],['wait','FIFO背压'],['pack','应用打包'],['send','D-PHY发送']].map(([key,text])=>`<span><i class="pipeline-${key}"></i>${text}</span>`).join('')}</div><p class="note">竖线衔接色块边缘；正交虚线表示等待，蓝线表示前slot释放资源。FIFO保留整列块至发送完成；零耗时用细交接线。时间来自后端，极短段最少1px，真实耗时见悬停。</p><div class="pipeline-facts"><span>Hist搬移 <b>${f(p.copy_ns/1000)} μs</b></span><span>DSP <b>${f(p.dsp_ns/1000)} μs</b></span><span>D-PHY单slot <b>${f(s.wire_ns/1000)} μs</b></span><span>FIFO自动预算 <b>${f(p.fifo_capacity_bytes)} B</b></span><span>可容纳 <b>${p.fifo_slots} 列块</b></span><span>连续帧最大背压 <b>${f(p.fifo_wait_max_ns/1000)} μs</b></span><span>连续帧最大slot延后 <b>${f(p.max_slot_delay_ns/1000)} μs</b></span></div>${phyDetails(result)}`;
 }
 function toolbar(lo,hi,end){const span=hi-lo;
  return `<div class="timing-navigation" aria-label="时序横轴视窗"><div class="timing-nav-buttons"><button type="button" data-timing-action="out" aria-label="时序横轴缩小" ${span>=end?'disabled':''}>−</button><button type="button" data-timing-action="in" aria-label="时序横轴放大" ${span<=end/128?'disabled':''}>＋</button><button type="button" data-timing-action="left" aria-label="时序向左平移" ${lo<=0?'disabled':''}>←</button><button type="button" data-timing-action="right" aria-label="时序向右平移" ${hi>=end?'disabled':''}>→</button><button type="button" data-timing-action="fit">显示全程</button><button type="button" data-timing-action="send">定位发送段</button></div><span>${f(lo/1000)}–${f(hi/1000)} μs · ${f(end/span)}×</span><small>Ctrl＋滚轮缩放 · 横向拖动平移</small></div>`;
 }
 function phyDetails(result){const t=result.electrical.selected.transmission;if(!t)return '';
  const fact=(name,value,unit)=>`<span>${name} <b>${f(value)} ${unit}</b></span>`;
  return `<div class="phy-send-summary"><strong>D-PHY发送 · ${f(t.base_time_ns==null?null:t.base_time_ns/1000)} μs/slot</strong><span>含CSI-2包开销及配置间隔，排队与应用打包另计</span></div><details class="phy-details"><summary>D-PHY耗时计算 · 字节、线速与帧边界</summary><div class="pipeline-facts">${fact('应用数据',t.payload_bytes,'B')}${fact('CSI-2开销',t.protocol_bytes,'B')}${fact('发送字节',t.wire_bytes,'B')}${fact('长包数量',t.long_packets,'包')}${fact('链路服务速率',t.effective_rate_mbps,'Mbit/s')}${fact('字节发送',t.serial_time_ns==null?null:t.serial_time_ns/1000,'μs')}${fact('额外间隔',t.gap_time_ns/1000,'μs')}</div><div class="pipeline-formula" data-timing-formula="budget_mipi_capacity"></div><p class="note">${t.capacity_mode==='lanes'?'每接口 '+f(t.lane_count)+' data lane · 每lane '+f(t.lane_rate_mbps)+' Mbit/s · 物理利用率 '+f(t.physical_utilization)+'。':'按总服务速率均分到接口。'}首slot另加FS、末slot另加FE，各 ${f(t.frame_short_packet_bytes_each)} B / ${f(t.frame_short_time_ns_each)} ns；只有一个slot时两项都加。下表包含当前slot的帧边界开销。</p><table><thead><tr><th>slot</th><th>发送开始 / μs</th><th>发送结束 / μs</th><th>实际发送时长 / μs</th></tr></thead><tbody>${t.slot_send_times.map(r=>`<tr><td>S${r.column}</td><td>${f(r.start_ns/1000)}</td><td>${f(r.end_ns/1000)}</td><td>${f(r.duration_ns/1000)}</td></tr>`).join('')}</tbody></table></details>`;
 }
 function render(result){currentResult=result;return `<div id="budgetPipelineView" class="pipeline-view" tabindex="0" aria-label="可缩放的三slot时序图">${renderContent(result)}</div>`;}
 function activate(){const root=document.getElementById('budgetPipelineView');if(!root)return;for(const node of root.querySelectorAll('[data-timing-formula]')){const definition=currentResult.formulas.find(f=>f.id===node.dataset.timingFormula);try{if(!definition)throw Error('公式定义未加载');katex.render(definition.latex,node,{displayMode:true,throwOnError:true});node.removeAttribute('data-formula-error');}catch(error){node.textContent='公式渲染失败：'+error.message+' '+(definition?.latex||'');node.dataset.formulaError='true';}}}
 function redraw(){const root=document.getElementById('budgetPipelineView');if(root){const open=root.querySelector('.phy-details')?.open;root.innerHTML=renderContent(currentResult);if(open)root.querySelector('.phy-details').open=true;activate();}}
 function act(action){if(!currentResult?.electrical.selected.pipeline?.feasible)return;const span=viewport.hi-viewport.lo;
  if(action==='in')viewport.zoom(.5,.5);else if(action==='out')viewport.zoom(2,.5);else if(action==='left')viewport.pan(-span/4);else if(action==='right')viewport.pan(span/4);else if(action==='fit')viewport.set(0,viewport.full);else if(action==='send'){const row=currentResult.electrical.selected.pipeline.rows[0],middle=(row.start_ns+row.end_ns)/2,width=Math.max((row.end_ns-row.start_ns)*4,viewport.full/128);viewport.set(middle-width/2,middle+width/2);}else return;
  redraw();document.getElementById('budgetPipelineView')?.focus({preventScroll:true});
 }
 document.addEventListener('click',event=>{const button=event.target.closest('[data-timing-action]');if(button){event.preventDefault();act(button.dataset.timingAction);}});
 document.addEventListener('keydown',event=>{if(!event.target.closest('#budgetPipelineView'))return;const action={'+':'in','=':'in','-':'out',ArrowLeft:'left',ArrowRight:'right',Home:'fit'}[event.key];if(action){event.preventDefault();act(action);}});
 document.addEventListener('wheel',event=>{const svg=event.target.closest('.pipeline-svg');if(!svg||!event.ctrlKey)return;const rect=svg.getBoundingClientRect(),anchor=Math.max(0,Math.min(1,((event.clientX-rect.left)*944/rect.width-156)/750));event.preventDefault();viewport.zoom(Math.exp(event.deltaY*.002),anchor);redraw();},{passive:false});
 document.addEventListener('pointerdown',event=>{const svg=event.target.closest('.pipeline-svg');if(!svg||event.button!==0)return;const rect=svg.getBoundingClientRect(),local=(event.clientX-rect.left)*944/rect.width;if(local<156||local>906)return;const root=document.getElementById('budgetPipelineView');drag={id:event.pointerId,startX:event.clientX,lo:viewport.lo,hi:viewport.hi,width:rect.width*750/944};root.setPointerCapture(event.pointerId);root.classList.add('dragging');event.preventDefault();});
 document.addEventListener('pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;const shift=(drag.startX-event.clientX)/drag.width*(drag.hi-drag.lo);viewport.set(drag.lo+shift,drag.hi+shift);redraw();});
 const endDrag=event=>{if(drag&&event.pointerId===drag.id){document.getElementById('budgetPipelineView')?.classList.remove('dragging');drag=null;}};
 document.addEventListener('pointerup',endDrag);document.addEventListener('pointercancel',endDrag);
 globalThis.BudgetPipelineViews={render,activate,TimelineViewport};
})();
