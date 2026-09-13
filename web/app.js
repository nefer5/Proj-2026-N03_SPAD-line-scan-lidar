let defaults = {};
let filterCurve = null;
let lastResult = null;

const $ = (id) => document.getElementById(id);
const inputEls = () => [...document.querySelectorAll("[data-key]")];
const colors = { cyan: "#41d9d0", blue: "#659cff", orange: "#ffb55b", muted: "#8da0b3", grid: "#243244" };

function fillForm(config) {
  inputEls().forEach(el => { if (config[el.dataset.key] !== undefined) el.value = config[el.dataset.key]; });
}

function collectConfig() {
  const cfg = { ...defaults };
  inputEls().forEach(el => {
    const key = el.dataset.key;
    const isInteger = ["spads_per_channel", "laser_shots", "monte_carlo_trials", "rng_seed", "line_channels"].includes(key);
    cfg[key] = isInteger ? parseInt(el.value, 10) : parseFloat(el.value);
  });
  cfg.filter_curve = filterCurve;
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
  const cssH = Number(canvas.getAttribute("height"));
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
  const xmin=Math.min(...xx), xmax=Math.max(...xx);
  let ymin=opts.ymin ?? 0;
  let ymax=opts.ymax ?? Math.max(1,...sliced.flatMap(s=>s.y.filter(Number.isFinite)))*1.08;
  const sx=v=>pad.l+(v-xmin)/(xmax-xmin||1)*pw;
  const sy=v=>pad.t+ph-(v-ymin)/(ymax-ymin||1)*ph;
  ctx.clearRect(0,0,w,h);
  ctx.font="11px ui-monospace, Consolas";
  ctx.fillStyle=colors.muted; ctx.strokeStyle=colors.grid; ctx.lineWidth=1;
  niceTicks(xmin,xmax,6).forEach(v=>{ const px=sx(v); ctx.beginPath();ctx.moveTo(px,pad.t);ctx.lineTo(px,pad.t+ph);ctx.stroke();ctx.fillText(fmt(v, opts.xDigits??1),px-12,h-18); });
  niceTicks(ymin,ymax,5).forEach(v=>{ const py=sy(v);ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke();ctx.fillText(fmt(v, v<10?2:0),6,py+4); });
  sliced.forEach(s=>{
    ctx.beginPath(); ctx.strokeStyle=s.color; ctx.lineWidth=s.width||1.5; ctx.globalAlpha=s.alpha||1;
    for(let i=0;i<xx.length;i++){ const px=sx(xx[i]),py=sy(s.y[i]); if(i===0)ctx.moveTo(px,py);else ctx.lineTo(px,py); }
    ctx.stroke(); ctx.globalAlpha=1;
  });
  ctx.fillStyle=colors.muted; ctx.textAlign="center"; ctx.fillText(opts.xLabel||"",pad.l+pw/2,h-4);ctx.textAlign="left";
  let lx=pad.l+6;
  sliced.forEach(s=>{ctx.fillStyle=s.color;ctx.fillRect(lx,pad.t+3,13,2);ctx.fillStyle=colors.muted;ctx.fillText(s.name,lx+18,pad.t+7);lx+=ctx.measureText(s.name).width+48;});
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
  $("mRange").textContent=fmt(m.estimated_range_m,3);$("mPrecision").textContent=fmt(m.precision_cm_1sigma,2);$("mBias").textContent=fmt(m.bias_cm,2);$("mSuccess").textContent=fmt(m.success_rate*100,1);
  $("mSignal").textContent=fmt(b.signal_detected_per_pulse,4);$("mNoise").textContent=fmt(b.background_detected_per_gate+b.dark_detected_per_gate+b.other_detected_per_gate,4);$("mSnr").textContent=fmt(m.observed_peak_snr,2);$("mPileup").textContent=fmt(m.pileup_loss_fraction*100,2);
  const h=result.histogram;
  const lines=[{name:"观测",y:h.observed_counts,color:colors.blue,width:1},{name:"期望",y:h.expected_counts,color:colors.cyan,width:2},{name:"纯噪声",y:h.expected_noise_counts,color:colors.orange,width:1.2}];
  drawLines($("histFull"),h.time_ns,lines,{xLabel:"时间 (ns)"});
  const peak=h.expected_counts.reduce((best,v,i)=>v>h.expected_counts[best]?i:best,0);const half=Math.max(20,Math.round(8*collectConfig().pulse_fwhm_ps/collectConfig().tdc_bin_ps));
  drawLines($("histZoom"),h.time_ns,lines,{i0:Math.max(0,peak-half),i1:Math.min(h.time_ns.length,peak+half),xLabel:"目标峰局部时间 (ns)",xDigits:2});
  drawRange($("rangeChart"),result.range_sweep);drawHeatmap($("xtalkChart"),result.crosstalk.total_induced_matrix);
  $("xtalkSummary").textContent=`中心源通道 ${result.crosstalk.source_channel}：总级联诱发比例 ${fmt(result.crosstalk.total_induced_fraction*100,3)}%`;
  $("assumptionList").innerHTML=result.assumptions.map(x=>`<li>${x}</li>`).join("");
  $("saveHistogram").disabled=false;
}

async function run() {
  $("runButton").disabled=true;$("runButton").textContent="计算中…";$("errorBox").classList.add("hidden");
  try {
    const resp=await fetch("/api/simulate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(collectConfig())});
    if(!resp.ok){const e=await resp.json();throw new Error(JSON.stringify(e.detail??e,null,2));}
    render(await resp.json());
  } catch(err) {$("errorBox").textContent=err.message;$("errorBox").classList.remove("hidden");}
  finally {$("runButton").disabled=false;$("runButton").textContent="运行仿真";}
}

function download(name,text,type) {const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();URL.revokeObjectURL(a.href);}

$("filterFile").addEventListener("change",async e=>{
  const file=e.target.files[0];if(!file){filterCurve=null;return;}
  const rows=(await file.text()).split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  const out=[];
  for(const row of rows){const p=row.split(/[,;\t]/).map(Number);if(Number.isFinite(p[0])&&Number.isFinite(p[1]))out.push({wavelength_nm:p[0],transmission:p[1]});}
  filterCurve=out.length>=2?out:null;$("filterStatus").textContent=filterCurve?`已加载 ${out.length} 个波长点`:"格式无效，仍使用矩形滤光片";
});
$("runButton").addEventListener("click",run);
$("resetButton").addEventListener("click",()=>{filterCurve=null;$("filterFile").value="";$("filterStatus").textContent="未加载，使用矩形滤光片";fillForm(defaults);run();});
$("saveConfig").addEventListener("click",()=>download("spad_lidar_config.json",JSON.stringify(collectConfig(),null,2),"application/json"));
$("saveHistogram").addEventListener("click",()=>{if(!lastResult)return;const h=lastResult.histogram;let s="time_ns,observed_counts,expected_counts,expected_noise_counts\n";for(let i=0;i<h.time_ns.length;i++)s+=`${h.time_ns[i]},${h.observed_counts[i]},${h.expected_counts[i]},${h.expected_noise_counts[i]}\n`;download("spad_lidar_histogram.csv",s,"text/csv");});
window.addEventListener("resize",()=>{if(lastResult)render(lastResult);});

(async()=>{defaults=await (await fetch("/api/defaults")).json();fillForm(defaults);run();})();

