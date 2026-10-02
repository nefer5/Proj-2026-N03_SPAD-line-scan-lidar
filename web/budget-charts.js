/* Rendering only. Time plans, pulse PDFs, energy and counts come from Python. */
(function(){
  const $=id=>document.getElementById(id),f=v=>BudgetNumbers.format(v);
  let pulseIndex=0,windowKey='gate',chainQuantity='energy',chainLog=true;
  const svg=(body,height,label)=>`<svg viewBox="0 0 920 ${height}" role="img" aria-label="${label}">${body}</svg>`;
  const text=(x,y,value,kind='',anchor='start')=>`<text x="${x}" y="${y}" class="plot-label ${kind}" text-anchor="${anchor}">${value}</text>`;
  function axis(low,high,y,unit){let b='';for(let i=0;i<=4;i++){const v=low+(high-low)*i/4,x=120+i*187.5;b+=`<path d="M${x} ${(unit==='μs'?22:y-135)}V${y+5}" class="plot-grid"/>`+text(x,y+23,f(v)+' '+unit,'plot-muted','middle');}return b;}
  function lanes(result,end,zoom){const t=result.timing,rows=t.rows,e=result.electrical?.selected,mipi=e?.wire_ns!==null&&e?.wire_ns!==undefined&&e?.ready_ns!==null&&e?.ready_ns!==undefined;if(mipi&&!zoom)end=Math.max(end,e.ready_ns+e.wire_ns);const x=v=>120+v/end*750;let b=axis(0,end/1000,mipi?255:215,'μs');
    b+=text(15,65,'Tx发射')+text(15,110,'接收gate')+text(15,155,'回波中心')+(zoom?'':text(15,mipi?235:195,'列余量'));if(mipi){b+=text(15,192,'MIPI输出');const start=x(e.ready_ns),right=x(Math.min(end,e.ready_ns+e.wire_ns));b+=`<rect x="${start}" y="178" width="${Math.max(1,right-start)}" height="23" class="plot-gate"/>`;if(e.ready_ns+e.wire_ns>end)b+=text(870,195,'→续','plot-muted','end');}
    for(const y of [60,105,150])b+=`<path d="M120 ${y}H870" class="plot-baseline"/>`;
    for(const [i,r]of rows.entries()){const active=i===pulseIndex;
      b+=`<path d="M${x(r.emission_ns)} 61v-18h4v18" class="plot-tx ${active?'selected':''}"/>`;
      b+=`<rect x="${x(r.gate_start_ns)}" y="92" width="${Math.max(1,x(r.gate_end_ns)-x(r.gate_start_ns))}" height="25" rx="3" class="plot-gate"/>`;
      b+=`<path d="M${x(r.return_ns)} 143l6 7-6 7-6-7z" class="plot-echo"/>`;
      if(rows.length<=6||i<2||i>=rows.length-2)b+=text(x(r.emission_ns)+5,35,'发'+r.pulse,active?'plot-accent':'');
    }
    if(!zoom){b+=`<path d="M${x(t.envelope_ns)} 24V211" class="plot-boundary"/>`;const start=t.envelope_ns+(t.reset_ns||0);
      if(t.reset_ns!==null)b+=`<rect x="${x(t.envelope_ns)}" y="${mipi?220:180}" width="${Math.max(0,x(start)-x(t.envelope_ns))}" height="22" class="plot-reset"/>`;
      if(start<t.slot_max_ns)b+=`<rect x="${x(start)}" y="${mipi?220:180}" width="${x(t.slot_max_ns)-x(start)}" height="22" rx="3" class="plot-spare"/>`;
      b+=text(125,mipi?238:198,t.reset_ns===null?'未计复位的空余时间':'复位后空余时间','plot-muted');
      b+=`<path d="M${x(t.slot_max_ns)} 24V212" class="plot-boundary end"/>`;
    }
    return svg(b,mipi?295:255,zoom?'slot内有效收发段展开，横轴微秒':'完整slot中的Tx、gate、回波与余量');
  }
  function profile(result,source=false){const p=result.channel_photons,q=p.profile,a=q.offset_ns,lo=a[0],hi=a[a.length-1],x=v=>120+(v-lo)/(hi-lo)*750;
    const values=source?q.power_w:q.normalized_density,max=Math.max(...values),y=v=>153-(max? v/max:0)*104;
    let b=axis(lo,hi,178,'ns');
    if(!source&&q.gate_clip_relative_ns)b+=`<rect x="${x(q.gate_clip_relative_ns[0])}" y="38" width="${x(q.gate_clip_relative_ns[1])-x(q.gate_clip_relative_ns[0])}" height="115" class="plot-gate faint"/>`;
    b+=`<rect x="${x(q.width_bounds_ns[0])}" y="38" width="${x(q.width_bounds_ns[1])-x(q.width_bounds_ns[0])}" height="115" class="plot-width"/>`;
    b+=`<path d="M${x(0)} 30V158" class="plot-boundary"/><polyline points="${a.map((v,i)=>x(v)+','+y(values[i])).join(' ')}" class="${source?'plot-tx':'plot-echo-line'}"/>`;
    for(let i=0;i<=2;i++)b+=text(106,y(max*i/2)+4,f(max*i/2),'plot-muted','end');
    b+=text(10,25,source?'功率 / W':'归一化回波')+text(x(0),23,source?'光源脉冲中心':'回波脉冲中心','plot-accent','middle');
    b+=text(600,25,'高亮：等效脉宽 '+f(p.equivalent_width_ns)+' ns','plot-muted');
    return svg(b,218,source?'单通道光源真实时间功率分布':'回波中心附近的脉宽和gate局部放大');
  }
  function timing(result){const t=result.timing,scale=v=>120+v/t.frame_period_ns*750;let frame=axis(0,t.frame_period_ns/1e6,155,'ms');
    frame+=`<rect x="120" y="30" width="${scale(t.scan_allocatable_ns)-120}" height="32" rx="5" class="plot-active"/><rect x="${scale(t.scan_allocatable_ns)}" y="30" width="${870-scale(t.scan_allocatable_ns)}" height="32" rx="5" class="plot-inactive"/>`;
    frame+=text(130,51,'有效扫描 '+f(t.scan_allocatable_ns/1e6)+' ms','plot-accent')+text(scale(t.scan_allocatable_ns)+10,51,'其他开销 '+f(t.non_scan_ns/1e6)+' ms','plot-muted');
    frame+=`<rect x="120" y="90" width="${scale(t.scan_allocatable_ns)-120}" height="24" class="plot-spare"/>`;for(const row of (t.frame_preview_slots||[])){const left=scale(row.start_ns),right=scale(row.end_ns);frame+=`<rect x="${left}" y="90" width="${Math.max(1,right-left)}" height="24" class="plot-slot" data-slot="${row.index}" data-start-ns="${row.start_ns}" data-end-ns="${row.end_ns}"/>`+text((left+right)/2,84,'slot '+row.index,'plot-muted','middle');}frame+=`<path d="M${scale(t.scan_allocatable_ns)} 26V120" class="plot-boundary end"/>`;
    frame+=text(120,134,'两排共用帧时间轴；只显示抽样slot位置（共'+result.configuration.experiment.targets.slot_count+'列）。非扫描段不分配slot。','plot-muted');
    pulseIndex=Math.min(pulseIndex,t.rows.length-1);
    $('timeline').innerHTML=`<div class="timing-level"><h3><span>01</span> 一帧 · 扫描与slot分配</h3>${svg(frame,195,'一帧有效扫描、其他开销和slot索引抽样')}${result.electrical?BudgetHardwareViews.networkTimeline(result):''}</div><div class="timing-level"><h3><span>02</span> 一个slot · 完整时间预算</h3>${lanes(result,t.plot_end_ns,false)}</div><details class="timing-level" open><summary>展开有效收发段 · 排除长空余区间</summary>${lanes(result,Math.max(t.envelope_ns,t.rows[t.rows.length-1].return_ns),true)}</details><div class="timing-level"><h3><span>03</span> 单发 · 回波中心附近的纳秒细节 <select id="timingPulse" aria-label="选择展开的发射脉冲">${t.rows.map((r,i)=>`<option value="${i}" ${i===pulseIndex?'selected':''}>第${r.pulse}发</option>`).join('')}</select></h3><p class="note">该发Tx中心 ${f(t.rows[pulseIndex].emission_ns)} ns；回波中心 ${f(t.rows[pulseIndex].return_ns)} ns。下图横轴为相对回波中心时间，gate只显示与局部视窗的交集。</p>${profile(result)}</div>`;
    $('timingPulse').onchange=()=>{pulseIndex=Number($('timingPulse').value);timing(result);};
    $('timingNote').textContent='Tx脉冲在微秒图上用事件标记表示；纳秒宽度见局部图。'+(t.reset_ns===null?'复位未知，余量不是最终可行性结论。':'')+(t.truncated?'只展示前'+t.rows.length+'发，预算包含全部发数。':'')+'匀速扫描未用于修正静态光子数。';
  }
  function photons(result,renderFormulas){const p=result.channel_photons,w=p.windows.find(w=>w.key===windowKey),band=result.single_channel.optical_budget.background_integration_band_nm;
    for(const b of document.querySelectorAll('[data-photon-window]')){b.setAttribute('aria-pressed',String(b.dataset.photonWindow===windowKey));b.onclick=()=>{windowKey=b.dataset.photonWindow;photons(result,renderFormulas);};}
    $('photonWindowNote').textContent=w.label+'（相对本发发射中心计时）：'+f(w.start_ns)+'～'+f(w.end_ns)+' ns，时长 '+f(w.duration_ns)+' ns；包含本发 '+f(w.signal_fraction*100)+'% 信号能量。'+p.scope_note+(windowKey==='pulse_width'?' 此参考窗口未按gate截断；实际gate内的脉宽贡献见“两窗口交集”。':'');
    const cards=[['信号候选',w.signal_candidates],['光学背景候选',w.background_candidates],['器件噪声候选',w.device_noise_candidates]];
    $('photonSummary').innerHTML=cards.map(([label,value])=>`<div class="metric"><div class="label">${label}</div><div class="value">${f(value)}</div><div class="unit">次 / 通道 / 当前窗口</div></div>`).join('');
    let body='';for(const [i,[label,value,energy]]of [['入瞳光子',w.signal_pupil_photons,w.signal_pupil_energy_nj],['探测面光子',w.signal_sensor_photons,w.signal_sensor_energy_nj],['候选雪崩',w.signal_candidates,null]].entries()){const left=25+i*298;body+=`<rect x="${left}" y="15" width="267" height="100" rx="9" class="photon-stage"/>`+text(left+18,40,label,'plot-muted')+text(left+18,70,f(value),'photon-value')+text(left+18,98,energy===null?'已含PDE/FF；尚未读出':f(energy)+' nJ','plot-muted');if(i<2)body+=text(left+278,71,'→','plot-accent');}
    $('photonChart').innerHTML=svg(body,132,'单通道当前窗口的入瞳、探测面与候选雪崩链路');
    $('spectralBand').textContent='背景原始光子积分波段 '+band.map(f).join('～')+' nm；背景按本通道独立Rx角域积分。';
    renderFormulas($('photonFlow'),w.flow);
    $('pulseEnergy').innerHTML=`<div class="energy-analysis-grid"><section class="source-energy-card"><h3>单通道光源 · 等效脉宽内的能量分布</h3><div class="pulse-energy-facts"><span>全脉冲能量 <b>${f(p.tx_total_energy_nj)} nJ</b></span><span>脉宽窗口能量 <b>${f(p.tx_width_energy_nj)} nJ</b></span><span>窗口占比 <b>${f(p.width_energy_fraction*100)}%</b></span><span>窗口平均功率 <b>${f(p.tx_width_average_w)} W</b></span><span>波形峰值 <b>${f(p.tx_peak_w)} W</b></span></div>${sourceProfile(result)}<p class="note">源窗口以发射中心计时；总能量为等效功率×脉宽，高斯FWHM窗只含部分能量，矩形窗含全部能量。</p></section><section class="signal-chain-card"><h3>单通道全脉冲 · 发射与回波链路</h3><div class="chain-toolbar"><button data-chain-quantity="energy">能量 / nJ</button><button data-chain-quantity="photons">光子 / 候选</button><button id="chainScale"></button></div><div id="signalChainChart"></div><p id="signalChainNote" class="note"></p></section></div>`;
    drawChain(result);

  }
  function sourceProfile(result){const p=result.channel_photons,q=p.profile,a=q.offset_ns,lo=a[0],hi=a[a.length-1],x=v=>70+(v-lo)/(hi-lo)*520,max=Math.max(...q.power_w),y=v=>185-(max?v/max:0)*130;let b='';
    for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4; b+=`<path d="M${x(v)} 42V190" class="plot-grid"/>`+text(x(v),211,f(v),'plot-muted','middle');}
    b+=`<path d="M70 42V185H595" class="plot-baseline"/><rect x="${x(q.width_bounds_ns[0])}" y="42" width="${x(q.width_bounds_ns[1])-x(q.width_bounds_ns[0])}" height="143" class="plot-width"/><polyline points="${a.map((v,i)=>x(v)+','+y(q.power_w[i])).join(' ')}" class="plot-tx"/><path d="M${x(0)} 37V190" class="plot-boundary"/>`;
    for(let i=0;i<=2;i++)b+=text(60,y(max*i/2)+4,f(max*i/2),'plot-muted','end');b+=text(12,26,'功率 / W')+text(x(0),26,'源脉冲中心','plot-accent','middle')+text(590,231,'相对时间 / ns','plot-muted','end');return `<svg viewBox="0 0 620 245" role="img" aria-label="单通道光源功率波形及脉宽窗口">${b}</svg>`;
  }
  function drawChain(result){const chain=result.channel_photons.signal_chain;if(!chain){$('signalChainNote').textContent='链路数据待同步，请普通刷新加载最新接口。';return;}const rows=chain.stages.filter(s=>chainQuantity==='photons'||s.kind==='optical'),values=rows.map(s=>chainQuantity==='energy'?s.energy_nj:s.photons_or_candidates),positive=values.filter(v=>v>0),max=Math.max(0,...values);
    const low=chainLog&&positive.length?Math.floor(Math.log10(Math.min(...positive))/2)*2-2:0,high=chainLog?Math.max(low+2,Math.ceil(Math.log10(max||1)/2)*2):max||1;
    const y=v=>chainLog?(v>0?246-180*(Math.log10(v)-low)/(high-low):246):246-180*v/high;
    let b=`<path d="M70 40V246H600" class="plot-baseline"/>`;const ticks=[];if(chainLog){const stride=2*Math.max(1,Math.ceil((high-low)/12));for(let k=Math.ceil(low/stride)*stride;k<=high;k+=stride)ticks.push(10**k);}else for(let i=0;i<=5;i++)ticks.push(high*i/5);for(const v of ticks){const yy=y(v);b+=`<path d="M70 ${yy}H600" class="plot-grid"/>`+text(62,yy+4,f(v),'plot-muted','end');}
    const step=530/rows.length;rows.forEach((s,i)=>{const v=values[i],left=70+i*step+step*.19,width=step*.62,top=y(v);b+=`<rect x="${left}" y="${top}" width="${width}" height="${246-top}" rx="2" class="${s.kind==='candidate'?'chain-candidate-bar':'chain-energy-bar'}"><title>${s.label}：${f(v)} ${chainQuantity==='energy'?'nJ':s.kind==='candidate'?'候选雪崩':'光子'}</title></rect>`+text(left+width/2,Math.max(39,top-7),f(v),'plot-muted','middle')+text(left+width/2,270,s.short,'plot-muted','middle');});
    b+=text(12,23,(chainQuantity==='energy'?'能量 / nJ':'光子 / 候选计数')+(chainLog?' · 对数轴':' · 线性轴'))+text(600,294,'链路阶段 →','plot-muted','end');$('signalChainChart').innerHTML=`<svg viewBox="0 0 620 312" role="img" aria-label="单通道全脉冲分阶段能量或光子柱状图">${b}</svg>`;
    const candidate=chain.stages.find(s=>s.kind==='candidate');$('signalChainNote').textContent='单通道一次发射、全脉冲。'+(chainQuantity==='energy'?'最后另计候选雪崩 '+f(candidate.photons_or_candidates)+' 次，不赋予光学能量。':'最后一柱为候选雪崩，其他柱为光子数。')+' 最终混合记录未仿真。柱状图表示阶段量，不是时间分箱；'+(chainLog?'零值不取对数，显示零柱。':'')+'原始值及参考面可在完整快照中查阅。';
    for(const button of document.querySelectorAll('[data-chain-quantity]')){button.setAttribute('aria-pressed',String(button.dataset.chainQuantity===chainQuantity));button.onclick=()=>{chainQuantity=button.dataset.chainQuantity;drawChain(result);};}$('chainScale').textContent=chainLog?'对数纵轴':'线性纵轴';$('chainScale').setAttribute('aria-pressed',String(chainLog));$('chainScale').onclick=()=>{chainLog=!chainLog;drawChain(result);};
  }
  globalThis.BudgetCharts={timing,photons};
})();
