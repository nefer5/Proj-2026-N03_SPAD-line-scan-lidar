let defaults = {};
let curveEditors = null;
let lastResult = null;
let help = {};
let debugPage = 0;
let latestDerived = null;
let derivedSequence = 0;
let readoutModes = {};
const isDebug = location.pathname === "/debug";

const $ = (id) => document.getElementById(id);
const inputEls = () => [...document.querySelectorAll("[data-key]")];
const colors = { cyan: "#41d9d0", blue: "#659cff", orange: "#ffb55b", muted: "#8da0b3", grid: "#243244" };

function fillForm(config) {
  inputEls().forEach(el => { if (config[el.dataset.key] !== undefined) {
    if(el.type==='checkbox')el.checked=config[el.dataset.key];else el.value=config[el.dataset.key];
  }});
  curveEditors.fill(config.spectral_inputs);
}

function collectConfig() {
  const cfg = { ...defaults };
  inputEls().forEach(el => {
    const key = el.dataset.key;
    const isInteger = ["spads_per_channel", "laser_shots", "monte_carlo_trials", "rng_seed", "line_channels"].includes(key);
    if(el.type==='checkbox')cfg[key]=el.checked;
    else if (el.tagName === 'SELECT') {
      if (!el.value || !Array.from(el.options).some(option=>option.value===el.value)) throw new Error(`参数 ${key} 需要选择有效选项，请刷新页面后重试。`);
      cfg[key] = el.value;
    } else {
      cfg[key] = Number(el.value);
      if (el.value.trim() === '' || !Number.isFinite(cfg[key]) || (isInteger && !Number.isInteger(cfg[key]))) throw new Error(`参数 ${key} 需要有效${isInteger ? '整数' : '数值'}`);
    }
  });
  cfg.spectral_inputs = curveEditors.values();
  return cfg;
}

function fmt(x, digits=3) {
  if (!Number.isFinite(x)) return "—";
  if (Math.abs(x) >= 1e5 || (Math.abs(x) > 0 && Math.abs(x) < 1e-3)) return x.toExponential(2);
  return x.toFixed(digits);
}

function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = Number(canvas.dataset.logicalHeight || canvas.getAttribute("height"));
  canvas.dataset.logicalHeight = cssH;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: cssW, h: cssH };
}

function niceTicks(min, max, count=5) {
  if (!(max > min)) return [min];
  const raw = (max-min)/count;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw/pow;
  const step = (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * pow;
  const start = Math.ceil(min/step)*step;
  const out = [];
  for (let v=start; v<=max+step*0.01; v+=step) out.push(v);
  return out;
}

function drawLines(canvas, x, series, opts={}) {
  const {ctx,w,h} = setupCanvas(canvas);
  const pad = {l:58,r:18,t:18,b:40};
  const pw=w-pad.l-pad.r, ph=h-pad.t-pad.b;
  const i0=opts.i0 ?? 0, i1=opts.i1 ?? x.length;
  const xx=x.slice(i0,i1);
  const sliced=series.map(s => ({...s, y:s.y.slice(i0,i1)}));
  const dx = opts.binWidth || 0;
  const xmin=opts.edges ? opts.edges[i0] : Math.min(...xx)-dx/2;
  const xmax=opts.edges ? opts.edges[i1] : Math.max(...xx)+dx/2;
  let ymin=opts.ymin ?? 0;
  let ymax=opts.ymax ?? sliced.reduce((m,s)=>s.y.reduce((v,y)=>Number.isFinite(y)?Math.max(v,y):v,m),1)*1.08;
  const sx=v=>pad.l+(v-xmin)/(xmax-xmin||1)*pw;
  const sy=v=>pad.t+ph-(v-ymin)/(ymax-ymin||1)*ph;
  ctx.clearRect(0,0,w,h);
  ctx.font="11px ui-monospace, Consolas";
  ctx.fillStyle=colors.muted; ctx.strokeStyle=colors.grid; ctx.lineWidth=1;
  niceTicks(xmin,xmax,6).forEach(v=>{ const px=sx(v); ctx.beginPath();ctx.moveTo(px,pad.t);ctx.lineTo(px,pad.t+ph);ctx.stroke();ctx.fillText(fmt(v, opts.xDigits??1),px-12,h-18); });
  niceTicks(ymin,ymax,5).forEach(v=>{ const py=sy(v);ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke();ctx.fillText(fmt(v, opts.yDigits ?? (v<10?2:0)),6,py+4); });
  sliced.forEach(s=>{
    if (s.bars) {
      ctx.fillStyle=s.color; ctx.globalAlpha=0.75;
      const width = opts.binWidth || (xx.length > 1 ? xx[1]-xx[0] : 1);
      ctx.save(); ctx.beginPath(); ctx.rect(pad.l,pad.t,pw,ph); ctx.clip();
      for(let i=0;i<xx.length;i++) {
        const left=opts.edges ? opts.edges[i0+i] : xx[i]-width/2;
        const right=opts.edges ? opts.edges[i0+i+1] : xx[i]+width/2;
        ctx.fillRect(sx(left),sy(s.y[i]),Math.max(0.5,(right-left)/(xmax-xmin)*pw*0.9),sy(0)-sy(s.y[i]));
      }
      ctx.restore(); ctx.globalAlpha=1; return;
    }
    ctx.beginPath(); ctx.strokeStyle=s.color; ctx.lineWidth=s.width||1.5; ctx.globalAlpha=s.alpha||1;
    for(let i=0;i<xx.length;i++){ const px=sx(xx[i]),py=sy(s.y[i]); if(i===0)ctx.moveTo(px,py);else ctx.lineTo(px,py); }
    ctx.stroke(); ctx.globalAlpha=1;
  });
  ctx.fillStyle=colors.muted; ctx.textAlign="center"; ctx.fillText(opts.xLabel||"",pad.l+pw/2,h-4);ctx.textAlign="left";
  let lx=pad.l+6;
  sliced.forEach(s=>{ctx.fillStyle=s.color;ctx.fillRect(lx,pad.t+3,13,2);ctx.fillStyle=colors.muted;ctx.fillText(s.name,lx+18,pad.t+7);lx+=ctx.measureText(s.name).width+48;});
  if(opts.scatter && opts.scatter.x.length) {
    ctx.save();ctx.beginPath();ctx.rect(pad.l,pad.t,pw,ph);ctx.clip();
    opts.scatter.x.forEach((v,i)=>{
      ctx.beginPath();ctx.arc(sx(v),sy(opts.scatter.y[i]),5,0,2*Math.PI);
      ctx.fillStyle=colors.blue;ctx.fill();ctx.strokeStyle="#eef6ff";ctx.lineWidth=1;ctx.stroke();
    });
    ctx.restore();ctx.fillStyle=colors.blue;ctx.beginPath();ctx.arc(lx+6,pad.t+4,4,0,2*Math.PI);ctx.fill();
    ctx.fillStyle=colors.muted;ctx.fillText("原始采样点",lx+18,pad.t+7);
  }
  if (opts.marker) {
    const px=sx(opts.marker.x),py=sy(opts.marker.y);
    ctx.save();ctx.strokeStyle=colors.orange;ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(px,pad.t+20);ctx.lineTo(px,pad.t+ph);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle=colors.orange;ctx.beginPath();ctx.arc(px,py,4,0,2*Math.PI);ctx.fill();
    ctx.textAlign="center";ctx.fillText(opts.marker.label,Math.max(pad.l+70,Math.min(w-pad.r-70,px)),pad.t+18);ctx.restore();
  }
}

function drawRange(canvas, points) {
  const x=points.map(p=>p.range_m), counts=points.map(p=>p.signal_counts), snr=points.map(p=>p.shot_noise_snr);
  const {ctx,w,h}=setupCanvas(canvas); const pad={l:58,r:55,t:22,b:40}; const pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;
  const xmin=Math.min(...x),xmax=Math.max(...x),ymax=Math.max(...counts)*1.08,smax=Math.max(...snr)*1.08;
  const sx=v=>pad.l+(v-xmin)/(xmax-xmin||1)*pw, sy=v=>pad.t+ph-v/(ymax||1)*ph, ss=v=>pad.t+ph-v/(smax||1)*ph;
  ctx.clearRect(0,0,w,h);ctx.font="11px ui-monospace, Consolas";ctx.strokeStyle=colors.grid;ctx.fillStyle=colors.muted;
  niceTicks(xmin,xmax,5).forEach(v=>{let px=sx(v);ctx.beginPath();ctx.moveTo(px,pad.t);ctx.lineTo(px,pad.t+ph);ctx.stroke();ctx.fillText(fmt(v,0),px-10,h-18)});
  niceTicks(0,ymax,5).forEach(v=>{let py=sy(v);ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke();ctx.fillText(fmt(v,0),5,py+4)});
  const line=(arr,map,color)=>{ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2;arr.forEach((v,i)=>i?ctx.lineTo(sx(x[i]),map(v)):ctx.moveTo(sx(x[i]),map(v)));ctx.stroke();};
  line(counts,sy,colors.cyan);line(snr,ss,colors.orange);
  ctx.fillStyle=colors.muted;ctx.textAlign="center";ctx.fillText("距离 (m)",pad.l+pw/2,h-4);ctx.textAlign="left";
  ctx.fillStyle=colors.cyan;ctx.fillText("信号累计计数",pad.l+6,pad.t+8);ctx.fillStyle=colors.orange;ctx.fillText("SNR（右轴）",pad.l+98,pad.t+8);ctx.fillStyle=colors.muted;ctx.fillText(fmt(smax,1),w-pad.r+8,pad.t+4);ctx.fillText("0",w-pad.r+8,pad.t+ph+4);
}

function drawHeatmap(canvas, matrix) {
  const {ctx,w,h}=setupCanvas(canvas); const n=matrix.length,pad={l:42,r:15,t:15,b:38}; const side=Math.min(w-pad.l-pad.r,h-pad.t-pad.b); const cw=side/n;
  const vals=matrix.flat();const max=Math.max(...vals,1e-12);
  ctx.clearRect(0,0,w,h);
  for(let row=0;row<n;row++)for(let col=0;col<n;col++){
    const t=Math.sqrt(matrix[row][col]/max); const r=Math.round(20+45*t),g=Math.round(31+186*t),b=Math.round(44+164*t);
    ctx.fillStyle=`rgb(${r},${g},${b})`;ctx.fillRect(pad.l+col*cw,pad.t+row*cw,cw+.4,cw+.4);
  }
  ctx.fillStyle=colors.muted;ctx.font="11px ui-monospace, Consolas";ctx.fillText("受扰",4,pad.t+side/2);ctx.textAlign="center";ctx.fillText("源通道",pad.l+side/2,h-6);ctx.textAlign="left";
  const step=Math.max(1,Math.ceil(n/8));for(let i=0;i<n;i+=step){ctx.fillText(String(i),pad.l+i*cw,pad.t+side+15);ctx.fillText(String(i),pad.l-25,pad.t+(i+.7)*cw);}
}

function render(result) {
  lastResult=result;
  const m=result.metrics,b=result.budget;
  $('mSolar').textContent=fmt(b.solar_detected_per_gate,5);
  $('mOtherLight').textContent=fmt(b.other_light_detected_per_gate,5);
  $('readoutSummary').textContent=(readoutModes[result.readout.mode]?.label||result.readout.mode)+' · '+
    (result.readout.engine==='event_monte_carlo'?'事件MC；曲线为 '+result.readout.expected_trials+' 次独立实验均值，非解析期望。':'理想首光子解析参考。');
  $("mRange").textContent=fmt(m.estimated_range_m,3);$("mPrecision").textContent=fmt(m.precision_cm_1sigma,2);$("mBias").textContent=fmt(m.bias_cm,2);$("mSuccess").textContent=fmt(m.success_rate == null ? null : m.success_rate*100,1);
  $("mSignal").textContent=fmt(b.signal_detected_per_pulse,4);$("mNoise").textContent=fmt(b.background_detected_per_gate+b.dark_detected_per_gate+b.other_detected_per_gate,4);$("mSnr").textContent=fmt(m.observed_peak_snr,2);$("mPileup").textContent=fmt(m.pileup_loss_fraction*100,2);
  const h=result.histogram;
  const lines=[{name:"观测柱状",y:h.observed_counts,color:colors.blue,bars:true},{name:"期望",y:h.expected_counts,color:colors.cyan,width:2},{name:"纯噪声",y:h.expected_noise_counts,color:colors.orange,width:1.2}];
  drawLines($("histFull"),h.time_ns,lines,{xLabel:"时间 (ns)",edges:h.edges_ns,binWidth:result.configuration.simulation.tdc_bin_ps/1000});
  const cfg=result.configuration.simulation;
  const peak=h.time_ns.reduce((best,v,i)=>Math.abs(v-result.derived.tof_ns)<Math.abs(h.time_ns[best]-result.derived.tof_ns)?i:best,0);
  const half=Math.max(10,Math.ceil(5*result.derived.irf_sigma_ns/(cfg.tdc_bin_ps/1000)));
  drawLines($("histZoom"),h.time_ns,lines,{i0:Math.max(0,peak-half),i1:Math.min(h.time_ns.length,peak+half+1),edges:h.edges_ns,binWidth:cfg.tdc_bin_ps/1000,xLabel:"目标峰局部时间 (ns)",xDigits:2});
  drawRange($("rangeChart"),result.range_sweep);
  if(result.crosstalk.status === "ok") {
    if(isDebug) drawHeatmap($("xtalkChart"),result.crosstalk.total_induced_matrix);
    $("xtalkSummary").textContent=`中心源通道 ${result.crosstalk.source_channel}：总级联诱发比例 ${fmt(result.crosstalk.total_induced_fraction*100,3)}%`;
  } else {
    const {ctx,w,h}=setupCanvas($("xtalkChart"));ctx.clearRect(0,0,w,h);
    $("xtalkSummary").textContent="附加诊断参数无效（不影响A测距）："+result.crosstalk.error;
  }
  $("assumptionList").innerHTML=result.assumptions.map(x=>`<li>${x}</li>`).join("");
  $("saveHistogram").disabled=false;
  if (isDebug && result.debug) renderDebug(result);
}

function showError(error) {
  $("errorBox").textContent=error.message || String(error);
  $("errorBox").classList.remove("hidden");
}

async function request(url, body, raw=false) {
  const response=await fetch(url,{method:"POST",headers:{"Content-Type":raw?"text/plain":"application/json"},body:raw?body:JSON.stringify(body)});
  if(!response.ok) {
    const error=await response.text();
    let message=error;
    try {
      const detail=JSON.parse(error).detail;
      message=Array.isArray(detail)?detail.map(item=>{
        const key=item.loc?.find(part=>help[part]);
        return (key?help[key].label+"：":"")+item.msg;
      }).join("\n"):(typeof detail==="string"?detail:error);
    }catch{}
    throw new Error(message);
  }
  return response;
}

function apertureFields() {
  const shape=document.querySelector('[data-key="rx_aperture_shape"]').value;
  document.querySelectorAll("[data-aperture]").forEach(el=>el.classList.toggle("hidden",el.dataset.aperture==="circle"?shape!=="circle":shape==="circle"));
  $("apertureWidthLabel").textContent=shape==="rectangle"?"宽度 (mm)":"水平全轴长 (mm)";
  $("apertureHeightLabel").textContent=shape==="rectangle"?"高度 (mm)":"垂直全轴长 (mm)";
  const selected=document.querySelector('[data-key=readout_mode]').value;
  $('readoutDescription').textContent=readoutModes[selected]?.description||'';
  const uses={tdc_count:selected==='shared_multitdc',coincidence_window_ns:selected.startsWith('coincidence'),coincidence_threshold:selected.startsWith('coincidence'),or_pulse_width_ns:selected.startsWith('shared'),tdc_max_hits_per_cycle:!selected.endsWith('first')&&selected!=='analytic_reference',spad_dead_time_ns:selected!=='analytic_reference',tdc_dead_time_ns:selected!=='analytic_reference',detector_operation:selected!=='analytic_reference'};
  for(const [key,active] of Object.entries(uses)) {const el=document.querySelector('[data-key='+key+']');el.disabled=!active;el.closest('label').classList.toggle('inactive',!active);}

}

function renderDerived(d) {
  latestDerived=d;
  $("peakPower").textContent=fmt(d.peak_power_w,4);
  $("averagePower").textContent=fmt(d.average_power_w,6);
  $("acquisitionTime").textContent=fmt(d.acquisition_time_ms,4);
  $("apertureArea").textContent=fmt(d.aperture_area_mm2,3);
  $("derivedStatus").textContent="Tx后：峰值 "+fmt(d.tx_output_peak_power_w,4)+" W；平均 "+fmt(d.tx_output_average_power_w,6)+" W；周期 "+fmt(d.repetition_period_ns,2)+" ns";
  drawLines($("pulseChart"),d.pulse.time_ps,[{name:"时间功率 (W)",y:d.pulse.power_w,color:colors.cyan}],{xLabel:"相对脉冲中心 (ps)"});
  const filter=d.filter;
  const method=filter.input_mode==="basic"?curveEditors.catalog.shapes[filter.basic_shape].label:(filter.interpolation==="pchip"?"PCHIP插值":"线性插值");
  drawLines($("filterChart"),filter.wavelength_nm,[{name:method,y:filter.transmission,color:colors.cyan}],{
    xLabel:"波长 (nm)",ymin:0,ymax:1.05,
    scatter:{x:filter.original_wavelength_nm,y:filter.original_transmission},
    marker:{x:filter.laser_wavelength_nm,y:filter.laser_transmission,label:"激光 "+fmt(filter.laser_wavelength_nm,1)+" nm"}
  });
  $("filterSummary").textContent=(filter.source==="csv_curve"?filter.original_wavelength_nm.length+"个原始点 · "+method:method+"基础波形（无采样点）")+
    " · 激光处透过率 "+fmt(filter.laser_transmission*100,2)+"% · 加权带宽 ∫T dλ = "+fmt(filter.weighted_bandwidth_nm,3)+" nm";
  $("filterSummary").classList.toggle("warning",filter.laser_transmission===0);
  const s=d.spectra,c=s.curves;
  $('solarSummary').textContent=fmt(s.solar_lux,0)+' lux → '+fmt(s.solar_irradiance_w_m2,3)+' W/m²；所选谱形归一化前 '+fmt(s.solar_reference_lux,0)+' lux';
  drawLines($('solarChart'),c.wavelength_nm,[{name:'太阳辐照度 W/m²/nm',y:c.solar_irradiance,color:colors.orange}],{xLabel:'波长 (nm)',scatter:{x:c.solar_original_x,y:c.solar_original_y}});
  drawLines($('environmentChart'),c.wavelength_nm,[{name:'太阳反射',y:c.solar_radiance,color:colors.orange},{name:'其他光',y:c.other_radiance,color:colors.blue},{name:'合计',y:c.total_radiance,color:colors.cyan}],{xLabel:'波长 (nm)',yDigits:3,ymax:Math.max(...c.total_radiance,Number.EPSILON)*1.12,scatter:{x:c.other_original_x,y:c.other_original_y}});
  $('pdeSummary').textContent='激光处感光区PDE：'+fmt(s.pde_at_laser*100,2)+'%；再乘FF用于探测。样例不是芯片规格。';
  drawLines($('pdeChart'),c.wavelength_nm,[{name:'PDE',y:c.pde,color:colors.cyan}],{xLabel:'波长 (nm)',ymin:0,ymax:1.05,scatter:{x:c.pde_original_x,y:c.pde_original_y},marker:{x:filter.laser_wavelength_nm,y:s.pde_at_laser,label:'激光 '+fmt(filter.laser_wavelength_nm,1)+' nm'}});
}

async function updateDerived() {
  const ticket=++derivedSequence;
  apertureFields();
  try {
    const cfg=collectConfig();
    const d=await (await request("/api/derived",cfg)).json();
    if(ticket===derivedSequence) {curveEditors.confirmBasic(cfg.spectral_inputs);renderDerived(d);}
  } catch(error) {
    if(ticket===derivedSequence) {
      latestDerived=null;
      ["peakPower","averagePower","acquisitionTime","apertureArea"].forEach(id=>$(id).textContent="—");
      $("derivedStatus").textContent="参数待修正："+error.message;
      $("filterSummary").textContent="当前参数无效，图中仍为上次有效曲线。";
    }
  }
}

async function run() {
  $("runButton").disabled=true; $("runButton").textContent="计算中…"; $("errorBox").classList.add("hidden");
  try {
    const cfg=collectConfig();
    const result=await (await request("/api/simulate?debug="+isDebug,cfg)).json();
    debugPage=Math.floor(result.debug ? result.debug.estimator.peak_bin/100 : 0);
    render(result);
    if(JSON.stringify(collectConfig())===JSON.stringify(cfg)) {
      renderDerived(result.derived);
      $("resultStatus").textContent="本次结果：累计 "+cfg.laser_shots+" 发；成功容差 ±"+result.metrics.success_tolerance_m+" m。";
    } else {
      $("resultStatus").textContent="参数已改变；下方仿真结果对应上次提交，请重新运行。";
    }
  } catch(error) { showError(error); }
  finally {$("runButton").disabled=false;$("runButton").textContent="运行仿真";}
}

function table(target, headers, rows) {
  const t=document.createElement("table"),thead=document.createElement("thead"),tr=document.createElement("tr");
  headers.forEach(h=>{const th=document.createElement("th");th.textContent=h;tr.append(th);});
  thead.append(tr);t.append(thead);
  const tbody=document.createElement("tbody");
  rows.forEach(row=>{const tr=document.createElement("tr");row.forEach(value=>{const td=document.createElement("td");td.textContent=typeof value==="number"?fmt(value,6):value==null?"—":String(value);tr.append(td);});tbody.append(tr);});
  t.append(tbody);target.replaceChildren(t);
}

function renderBins() {
  if(!lastResult?.debug) return;
  const h=lastResult.histogram,b=lastResult.debug.bins;
  const pages=Math.ceil(h.time_ns.length/100);
  debugPage=Math.max(0,Math.min(debugPage,pages-1));
  $("binsPage").textContent=(debugPage+1)+" / "+pages;
  const rows=[];
  for(let i=debugPage*100;i<Math.min(h.time_ns.length,(debugPage+1)*100);i++) rows.push([i,h.time_ns[i],b.signal_fraction[i],b.mu_signal_per_spad[i],b.mu_noise_per_spad[i],b.survival_before_bin[i],b.first_event_probability[i],h.expected_counts[i],h.observed_counts[i]]);
  table($("debugBins"),["bin","t (ns)","门内信号份额","μs / SPAD","μnoise / SPAD","存活概率","首事件概率","期望计数","观测计数"],rows);
}

function renderDebug(result) {
  const d=result.debug;
  $('readoutAudit').textContent=JSON.stringify(d.readout_audit,null,2);
  $('spectralAudit').textContent=JSON.stringify(Object.fromEntries(Object.entries(d.spectral_audit).filter(([k])=>!['curves','integration'].includes(k))),null,2);
  $("provenance").textContent=JSON.stringify(result.provenance,null,2);
  const sections=d.steps.map(step=>{
    const el=document.createElement("details");el.open=true;
    const summary=document.createElement("summary");summary.textContent=step.title;
    const formula=document.createElement("div");formula.className='formula';
    const latex=d.formulas[step.formula_id];
    try {katex.render(latex,formula,{displayMode:true,throwOnError:true});}
    catch(error){formula.textContent='公式渲染失败：'+error.message+'\n'+latex;}
    const data=document.createElement("div");
    table(data,["中间量（名称含单位）","实际数值"],Object.entries(step.values));
    el.append(summary,formula,data);return el;
  });
  $("debugSteps").replaceChildren(...sections);
  table($("parameterTable"),["参数","本次值","单位","含义与边界"],Object.entries(result.configuration.simulation).map(([key,value])=>{
    const meta=d.parameter_help[key];
    return [meta.label+" · "+key,typeof value==="object"?JSON.stringify(value):value,meta.unit,meta.description];
  }));
  $("algorithmTrace").textContent=JSON.stringify({algorithms:result.configuration.algorithms,constants:d.constants},null,2);
  table($("trialTable"),["重复试验","距离 (m)","误差 (m)"],d.trial_estimates_m.map((r,i)=>[i+1,r,d.trial_errors_m[i]]));
  renderBins(); $("saveDebug").disabled=false;
}

function download(name,text,type) {
  const a=document.createElement("a"),url=URL.createObjectURL(new Blob([text],{type}));
  a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function changed() {
  apertureFields();
  ++derivedSequence; // Invalidate any request from the previous configuration immediately.
  if(lastResult) $("resultStatus").textContent="参数已修改：功率联动更新；直方图仍为上次结果，请点击运行仿真。";
  clearTimeout(changed.timer);
  changed.timer=setTimeout(updateDerived,200);
}

$("configFile").addEventListener("change",async e=>{
  try {
    const file=e.target.files[0];if(!file)return;
    const cfg=await (await request("/api/config/import",await file.text(),true)).json();
    defaults=cfg;fillForm(cfg);
    changed();await run();
  }catch(error){showError(error);}
});
inputEls().forEach(el=>el.addEventListener(el.tagName === "SELECT" || el.type==='checkbox' ? "change" : "input",changed));
$("runButton").addEventListener("click",run);
$("resetButton").addEventListener("click",async()=>{
  try {
    const response=await fetch("/api/defaults",{cache:"no-store"});if(!response.ok)throw new Error(await response.text());
    defaults=await response.json();$("configFile").value="";
    fillForm(defaults);changed();await run();
  }catch(error){showError(error);}
});
$("saveConfig").addEventListener("click",async()=>{try{
  const response=await request("/api/config/export",collectConfig());
  download("spad_lidar_config.yaml",await response.text(),"application/yaml");
}catch(error){showError(error);}});
$("saveHistogram").addEventListener("click",()=>{
  if(!lastResult)return;
  const h=lastResult.histogram;
  let text="time_ns,observed_counts,expected_counts,expected_noise_counts\n";
  for(let i=0;i<h.time_ns.length;i++)text+=[h.time_ns[i],h.observed_counts[i],h.expected_counts[i],h.expected_noise_counts[i]].join(",")+"\n";
  download("spad_lidar_histogram.csv",text,"text/csv");
});
$("saveDebug").addEventListener("click",()=>download("spad_debug_report.json",JSON.stringify(lastResult,null,2),"application/json"));
$("binsPrevious").addEventListener("click",()=>{debugPage--;renderBins();});
$("binsNext").addEventListener("click",()=>{debugPage++;renderBins();});
$("modeLink").addEventListener("click",()=>{try{sessionStorage.setItem("lidar-config",JSON.stringify(collectConfig()));}catch{}});
window.addEventListener("resize",()=>{
  if(lastResult)render(lastResult);
  if(latestDerived)renderDerived(latestDerived);
});

(async()=>{
  try {
    const [d,c]=await Promise.all([fetch("/api/defaults",{cache:"no-store"}),fetch("/api/catalog",{cache:"no-store"})]);
    if(!d.ok || !c.ok)throw new Error("无法读取YAML配置："+await (!d.ok?d:c).text());
    defaults=await d.json();const catalog=await c.json();help=catalog.parameters;readoutModes=catalog.readout_modes;
    curveEditors=new CurveEditors(catalog.curve_inputs,changed,async(kind,spec)=>await (await request('/api/curve/validate?kind='+kind,spec)).json());
    $('readoutMode').replaceChildren(...Object.entries(readoutModes).map(([key,meta])=>{const option=document.createElement('option');option.value=key;option.textContent=meta.label;return option;}));
    let initial=defaults;
    const saved=sessionStorage.getItem("lidar-config");
    sessionStorage.removeItem("lidar-config");
    if(saved) initial=await (await request("/api/config/import",saved,true)).json();
    fillForm(initial);apertureFields();
    inputEls().forEach(el=>{const meta=help[el.dataset.key];if(meta)el.closest("label").title=meta.description;});
    if(isDebug) {
      $("debugPanel").classList.remove("hidden");
      $("modeLink").href="/";$("modeLink").textContent="← 评估界面";
      document.querySelector("h1").textContent="A · 单角通道专家调试";
      document.querySelectorAll(".debug-only").forEach(el=>el.classList.remove("hidden"));
    }
    document.body.dataset.mode=isDebug?"debug":"evaluation";
    await updateDerived();await run();
  }catch(error){showError(error);}
})();
