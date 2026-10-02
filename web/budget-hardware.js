/* Hardware result views. All data sizes, schedules and range statistics are Python outputs. */
(function(){
 const $=id=>document.getElementById(id),f=v=>BudgetNumbers.format(v);
 const card=(label,value,unit)=>`<div class="metric"><div class="label">${label}</div><div class="value">${f(value)}</div><div class="unit">${unit}</div></div>`;
 const status=v=>v===null||v===undefined?'待指定':v?'满足':'不满足';
 function electrical(result){const e=result.electrical,s=e.selected,p=s.pipeline,m=s.memory,fmt={points:'Range完整点',histogram:'全Hist',echo:'Echo上限'};
  $('electricalMetrics').innerHTML=card('芯片数 / 所需链路',e.chip_count,'chip · '+e.link_count+' link')+card('总data lane数',e.total_data_lanes,'lane · clock不计载荷')+card('每链路服务速率',e.net_mbps_per_link,'Mbit/s · 物理利用率已计')+card('总服务 / 原始带宽',e.total_net_mbps,'Mbit/s · 原始 '+f(e.total_raw_mbps))+
   card('当前格式每帧应用数据',s.bytes_per_frame,'B/frame · '+fmt[e.format])+card('含CSI-2的线速需求',s.total_required_mbps,'Mbit/s · 不含时间间隔')+card('最忙链路单列发送',s.wire_ns==null?null:s.wire_ns/1000,'μs · 包开销与间隔已计')+card('资源帧率必要上界',s.max_frame_rate_hz,'Hz · 非精确最大帧率')+
   card('每帧CSI-2包开销',s.csi_overhead_bytes_per_frame,'B/frame')+card('每帧链路发送字节',s.wire_bytes_per_frame,'B/frame · 所有link合计')+card('单块SRAM自动预算',m?.maximum_bank_bytes,'B/chip/bank · 不含DSP工作区')+card('全系统SRAM自动预算',m?.total_sram_bytes,'B · 按单/双缓冲计')+card('每link FIFO自动预算',m?.maximum_fifo_bytes,'B/link · 有限 '+(m?.fifo_columns??'待计算')+' 列块')+card('输出FIFO实际占用峰值',s.peak_buffer_bytes_per_link,'B/link · 当前时序模型');
  const sustained=p?.feasible?p.sustained_ok:null,cadence=p?.feasible?p.cadence_ok:null;
  $('electricalChecks').innerHTML='<table><tr><th>链路平均服务</th><th>目标slot节拍</th><th>连续帧观测</th><th>严格帧截止</th><th>端口</th></tr><tr>'+[s.average_bandwidth_ok,cadence,sustained,s.frame_ok,e.ports_ok].map(v=>'<td>'+status(v)+'</td>').join('')+'</tr></table>'+(p?.feasible?'<p class="note">连续 '+p.frames.length+' 帧保留资源状态；首帧末发送完成 '+f(s.frame_completion_ns/1e6)+' ms；最后相邻帧拖尾增量 '+f(p.tail_growth_ns/1000)+' μs。固定延迟可能跨帧；积压增长或slot延后表示目标节拍受阻。模拟输出帧间隔对应 '+f(p.observed_output_frame_rate_hz)+' Hz，有限帧观测不等于长期稳定证明。</p>':'<p class="note">'+(p?.note||s.note||'时序输入未完整')+'</p>');
  $('electricalFormats').innerHTML='<table><tr><th>输出格式</th><th>每slot应用B</th><th>每帧应用B</th><th>每帧发送B</th><th>CSI-2开销B</th><th>总需求 Mbit/s</th><th>最忙link需求</th></tr>'+Object.entries(e.formats).map(([key,v])=>'<tr><td>'+fmt[key]+'</td><td>'+f(v.total_bytes_per_column)+'</td><td>'+f(v.bytes_per_frame)+'</td><td>'+f(v.wire_bytes_per_frame)+'</td><td>'+f(v.csi_overhead_bytes_per_frame)+'</td><td>'+f(v.total_required_mbps)+'</td><td>'+f(v.worst_link_required_mbps)+'</td></tr>').join('')+'</table>';
  $('electricalTimeline').innerHTML=networkTimeline(result);
  $('electricalNote').textContent=(m?m.note+' ':'')+e.note+(s.note?' '+s.note:'');
 }
 function networkTimeline(result){const s=result.electrical.selected,t=result.timing;if(!s.complete||s.frame_completion_ns===null||s.frame_completion_ns===undefined)return '<p class="note">片内SRAM、有限FIFO与处理/链路参数完整且可容纳当前数据后生成输出时序。</p>';
  const end=Math.max(t.frame_period_ns,s.frame_completion_ns),x=v=>120+v/end*750;let body='<text x="8" y="57" class="plot-label">MIPI包范围</text>';
  for(let i=0;i<=4;i++){const value=end*i/4;body+=`<path d="M${x(value)} 24V105" class="plot-grid"/><text x="${x(value)}" y="132" text-anchor="middle" class="plot-label plot-muted">${f(value/1e6)} ms</text>`;}
  body+=`<rect x="${x(s.ready_ns)}" y="43" width="${x(s.frame_completion_ns)-x(s.ready_ns)}" height="28" class="plot-spare"/><path d="M${x(t.scan_allocatable_ns)} 22V110" class="plot-boundary"/><path d="M${x(t.frame_period_ns)} 22V110" class="plot-boundary end"/>`;
  for(const row of s.timeline)body+=`<rect x="${x(row.start_ns)}" y="43" width="${Math.max(1,x(row.end_ns)-x(row.start_ns))}" height="28" class="plot-gate"/><text x="${x(row.start_ns)}" y="35" class="plot-label plot-muted" text-anchor="middle">${row.column}</text>`;
  body+='<text x="120" y="96" class="plot-label plot-muted">基于资源调度的真实位置；列包只抽样标记。浅框不是持续忙，红线为帧截止。</text>';
  return '<h3>MIPI最忙链路 · 一帧输出包范围</h3><svg viewBox="0 0 920 151" role="img" aria-label="MIPI逐列输出与帧截止时间">'+body+'</svg>';
 }
 function curve(points,measured,key,mkey,title,unit){const valid=points.filter(p=>p[key]!==null),lo=points[0].distance_m,hi=points[points.length-1].distance_m,values=[...valid.map(p=>p[key]),...measured.filter(p=>p[mkey]!==null).map(p=>p[mkey])],max=Math.max(0,...values)||1,x=v=>60+(v-lo)/(hi-lo)*310,y=v=>180-v/max*135;
  let b='<path d="M60 28V180H370" class="detail-axis"/>';
  for(let i=0;i<=3;i++){const value=max*i/3,xx=lo+(hi-lo)*i/3;b+=`<path d="M60 ${y(value)}H370" class="detail-grid"/><text x="52" y="${y(value)+4}" text-anchor="end">${f(value)}</text><text x="${x(xx)}" y="201" text-anchor="middle">${f(xx)}</text>`;}
  b+=`<polyline points="${valid.map(p=>x(p.distance_m)+','+y(p[key])).join(' ')}" class="reference-line"/>`;
  for(const p of measured)if(p[mkey]!==null&&p.distance_m>=lo&&p.distance_m<=hi)b+=`<circle cx="${x(p.distance_m)}" cy="${y(p[mkey])}" r="4" class="reference-measured"><title>实测 ${f(p.distance_m)}m / ${f(p[mkey])}${unit}</title></circle>`;
  b+=`<text x="16" y="20">${unit}</text><text x="370" y="222" text-anchor="end">距离 / m →</text>`;
  return `<section class="reference-plot"><h3>${title}</h3><svg viewBox="0 0 400 234" role="img" aria-label="${title}随距离变化及实测点">${b}</svg></section>`;
 }
 function reference(result){const r=result.range_reference;if(!r){$('rangeReferencePlots').innerHTML='未启用距离参考';$('rangeReferenceMetrics').innerHTML='';$('rangeReferenceNote').textContent='参考关闭；实测数据仍保留。';return;}const current=r.current,signal=r.area_kind==='signal';
  $('rangeReferenceMetrics').innerHTML=card('当前距离',current.distance_m,'m')+card('信号 / 原始总面积',current.signal_area_counts,'候选 · 总 '+f(current.total_area_counts))+card('理想IRF FWHM',current.irf_fwhm_ns,'ns · 不含分箱显示宽度')+card('理想精度下限',current.precision_crlb_mm,'mm · 不是实测精度');
  $('rangeReferencePlots').innerHTML=curve(r.points,r.measurements,signal?'signal_area_counts':'total_area_counts','area_counts',signal?'扣背景信号面积':'原始总计数面积','counts')+curve(r.points,r.measurements,signal?'peak_signal_counts':'peak_total_counts','peak_counts','峰值 · 每TDC bin','counts/bin')+curve(r.points,r.measurements,'irf_fwhm_ns','fwhm_ns','理想IRF脉宽','ns')+curve(r.points,r.measurements,'precision_crlb_mm','range_std_mm','理想测距统计下限','mm');
  $('rangeReferenceNote').textContent=r.note+' 线：理想参考；圆点：实测。当前门/分箱的信号质心参考偏移 '+f(current.gate_centroid_bias_mm)+' mm；不是可直接套用的标定修正量。';
  $('rangeMeasurementMode').value=r.measurement_mode;$('rangeManualPanel').hidden=r.measurement_mode!=='manual';$('rangeCsvPanel').hidden=r.measurement_mode!=='csv';$('rangeMeasurementStatus').textContent='当前 '+r.measurement_mode+' 数据集 '+r.measurements.length+' 点；未提供实测点时不生成虚构数据。';
 }
 async function inputMeasurements(text,mode,name){const ext=window.budgetExtensions;try{const points=await ext.request('/api/system-budget/measurements',text.trim()?text:'distance_m\n',true),cfg=ext.collect();cfg.range_reference.measurement_mode=mode;cfg.range_reference[mode+'_points']=points;if(mode==='csv')cfg.range_reference.csv_name=name;ext.fill(cfg);ext.changed();$('rangeMeasurementError').hidden=true;}catch(e){$('rangeMeasurementError').hidden=false;$('rangeMeasurementError').textContent='实测输入错误：'+e.message;}}
 function install(){
  $('loadElectricalExample').onclick=()=>{const ext=window.budgetExtensions,c=ext.collect(),d=ext.catalog().defaults;for(const key of ['payload_format','histogram_count_bits','point_bytes','column_header_bytes'])c.transport[key]=d.transport[key];c.electrical=structuredClone(d.electrical);ext.fill(c);ext.changed();};
  $('applyRangeMeasurements').onclick=()=>inputMeasurements($('rangeMeasurementText').value,'manual','');
  $('rangeMeasurementFile').onchange=async event=>{const file=event.target.files[0];if(file){await inputMeasurements(await file.text(),'csv',file.name);$('rangeMeasurementFilename').textContent=file.name;}};
  $('rangeMeasurementMode').onchange=()=>{const ext=window.budgetExtensions,c=ext.collect();c.range_reference.measurement_mode=$('rangeMeasurementMode').value;ext.fill(c);ext.changed();};
 }
 globalThis.BudgetHardwareViews={render(result){electrical(result);reference(result);},networkTimeline};
 window.addEventListener('DOMContentLoaded',install);
})();
