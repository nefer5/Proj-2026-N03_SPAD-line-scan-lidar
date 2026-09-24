/* UI only: all photon budgets, waveforms, spatial maps and binning run in Python. */
const kind=document.body.dataset.lab, $=id=>document.getElementById(id);
let catalog,config,editors,lastResult,lastJob,pollTimer;
let configLoading=false;
const storageKey='lidar-experiment-v2-'+kind;
const sectionNames={device:'SPAD 器件',readout:'读出电子学',timing:'实验时序',illumination:'探测面直接照明',optics:'空间光学与场景',scan:'扫描与同步',scene_motion:'构造场景运动'};
function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function fail(error){$('error').textContent=error.message||String(error);$('error').classList.remove('hidden');}
async function request(path,body,raw=false){const r=await fetch(path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':raw?'text/plain':'application/json'},body:raw?body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));return d;}
function schemaOf(s){return s.$ref?catalog.schema.$defs[s.$ref.split('/').pop()]:s;}
function helpFor(path){return catalog.help.experiments?.[path]||catalog.help[path.split('.').pop()]||{label:path,unit:'',description:'参见配置类型与调试导出。'};}
function createFields(values,schema,parent,path){schema=schemaOf(schema);for(const [key,value]of (path===''&&kind==='scan'?Object.entries(values).sort((a,b)=>['scan','timing','scene_motion','device','readout','optics','rng_seed','spectral_inputs'].indexOf(a[0])-['scan','timing','scene_motion','device','readout','optics','rng_seed','spectral_inputs'].indexOf(b[0])):Object.entries(values))){if(key==='spectral_inputs')continue;const p=path?path+'.'+key:key;let def=schemaOf(schema.properties[key]);if(value!==null&&typeof value==='object'&&!Array.isArray(value)&&!['dataset'].includes(key)){const d=node('details');d.open=(kind==='scan'?['scan']:['device','illumination','optics']).includes(key);d.append(node('summary',sectionNames[key]||key));const grid=node('div');grid.className='field-grid';createFields(value,def,grid,p);d.append(grid);parent.append(d);continue;}const h=helpFor(p),label=node('label',h.label+(h.unit?' ('+h.unit+')':''));label.title=h.description;let input;if(def.enum||def.type==='boolean'){input=node('select');const options=def.enum||(def.type==='boolean'?['true','false']:[]);for(const choice of options){if(p==='readout.readout_mode'&&choice==='analytic_reference')continue;const option=node('option',catalog.readout_modes[choice]?.label||String(choice));option.value=String(choice);input.append(option);}}else if(Array.isArray(value)||key==='dataset'){input=node('textarea');input.rows=3;label.classList.add('wide');}else{input=node('input');input.type=typeof value==='number'?'number':'text';input.step=def.type==='integer'?'1':'any';if(def.minimum!==undefined)input.min=def.minimum;if(def.maximum!==undefined)input.max=def.maximum;}input.dataset.path=p;input.dataset.type=def.type||((Array.isArray(value)||key==='dataset')?'json':'string');input.value=typeof value==='object'?JSON.stringify(value):String(value);label.append(input);parent.append(label);}}
function fill(cfg){config=structuredClone(cfg);$('fields').replaceChildren();createFields(config,catalog.schema,$('fields'),'');editors.fill(config.spectral_inputs);$('fields').querySelectorAll('input,select,textarea').forEach(x=>x.addEventListener('change',saveDraft));$('formStatus').textContent='参数来自后端配置；只有当前选择的输入模式生效。';updateVisibility();}
function collect(){if(configLoading)throw new Error('正在加载默认值，请稍候。');const out=structuredClone(config);for(const input of $('fields').querySelectorAll('[data-path]')){const bits=input.dataset.path.split('.');let target=out;for(const b of bits.slice(0,-1))target=target[b];const key=bits.at(-1),type=input.dataset.type;let v=input.value;if(['number','integer'].includes(type)){if(v.trim()===''||!Number.isFinite(Number(v)))throw new Error(input.dataset.path+' 需要有限数字');v=Number(v);}else if(type==='boolean')v=v==='true';else if(type==='array'||type==='json')v=JSON.parse(v);target[key]=v;}out.spectral_inputs=editors.values();return out;}
function envelope(cfg){return {schema_version:2,kind,experiment:cfg};}
function saveDraft(){try{localStorage.setItem(storageKey,JSON.stringify(envelope(collect())));if(lastResult){$('resultStatus').textContent='参数已修改；下方仍为任务 '+lastJob.slice(0,8)+' 的结果。';if(lastResult.scan)$('scanViewStatus').textContent='参数已修改；显示的是原任务采集结果。';}updateVisibility();}catch(e){$('formStatus').textContent='草稿未保存：'+e.message;}}
function download(name,data){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=node('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
function setup(canvas){const box=canvas.getBoundingClientRect(),d=window.devicePixelRatio||1;canvas.width=box.width*d;canvas.height=box.height*d;const c=canvas.getContext('2d');c.scale(d,d);c.clearRect(0,0,box.width,box.height);return [c,box.width,box.height];}
function heatmap(values,shape){const [c,w,h]=setup($('illuminationPlot')),[rows,cols]=shape,max=Math.max(...values,0);const left=40,top=15,cw=(w-left-15)/cols,ch=(h-top-35)/rows;c.font='11px Segoe UI';for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){const v=values[y*cols+x],f=max?v/max:0;c.fillStyle=`hsl(${180-30*f} 65% ${12+48*f}%)`;c.fillRect(left+x*cw,top+y*ch,cw-1,ch-1);}c.fillStyle='#8da0b3';c.fillText('物理像素 x →',left,h-8);c.fillText('y',10,top+15);c.fillText('峰值 '+max.toPrecision(4)+' photons/pulse',left+100,h-8);}
let displayedHistogram;
function histogram(h){
 displayedHistogram=h;const [c,w,height]=setup($('histogramPlot')),left=45,top=15,plotW=w-left-15,plotH=height-50;
 const lo=$('plotStart').value===''?h.edges_ns[0]:Number($('plotStart').value),hi=$('plotEnd').value===''?h.edges_ns.at(-1):Number($('plotEnd').value);
 if(!Number.isFinite(lo)||!Number.isFinite(hi)||hi<=lo)throw new Error('图形显示终点必须大于起点');
 const indices=h.time_ns.map((t,i)=>t>=lo&&t<=hi?i:-1).filter(i=>i>=0);let max=0;
 for(const row of h.counts)for(const i of indices)max=Math.max(max,row[i]);
 c.strokeStyle='#263547';c.beginPath();c.moveTo(left,top);c.lineTo(left,top+plotH);c.lineTo(left+plotW,top+plotH);c.stroke();
 const colors=['#41d9d0','#659cff','#ffb55b','#d291ff','#f77a91','#b8df77'];$('histogramLegend').replaceChildren();
 h.counts.forEach((row,ch)=>{c.strokeStyle=colors[ch%colors.length];c.beginPath();indices.forEach((i,j)=>{const x=left+(h.time_ns[i]-lo)/(hi-lo)*plotW,y=top+plotH-(max?row[i]/max:0)*plotH;if(j===0)c.moveTo(x,y);else c.lineTo(x,y);});c.stroke();const label=node('span','通道 '+ch);label.style.color=colors[ch%colors.length];label.style.marginRight='12px';$('histogramLegend').append(label);});
 c.fillStyle='#8da0b3';c.font='11px Segoe UI';c.fillText(lo.toFixed(2),left,height-12);c.fillText(hi.toFixed(2)+' ns',Math.max(left,w-100),height-12);c.fillText(String(max),8,top+10);
 $('histogramNote').textContent=h.counts.length+' 个读出通道 · 分箱 '+h.bin_ps+' ps · 显示缩放不改变采集或统计';
}

function render(result,id){lastResult=result;lastJob=id;$('exportResult').disabled=false;$('replay').disabled=false;$('replayBin').value=result.record_schema.tdc_bin_ps;$('plotStart').value=result.histogram.edges_ns[0];$('plotEnd').value=result.histogram.edges_ns.at(-1);$('zoomHistogram').disabled=false;$('fullHistogram').disabled=false;$('resultStatus').textContent=result.provenance.scope+' · '+result.provenance.configuration_sha256.slice(0,16);$('metrics').replaceChildren();for(const [name,value]of [['最终记录',result.audit.final_records],['有效雪崩',result.audit.avalanches],['器件死时间损失',result.audit.spad_dead_losses],['TDC/容量损失',result.audit.tdc_dead_losses+result.audit.capacity_losses]]){const d=node('div');d.className='metric';d.append(node('small',name),node('strong',String(value)));$('metrics').append(d);}heatmap(result.illumination.signal_photons_per_pixel_per_pulse,result.illumination.shape);histogram(result.histogram);$('planeNote').textContent='完整像素接收平面，尚未乘 PDE/FF；像素位置与读出通道分别管理。';$('audit').textContent=JSON.stringify({configuration:result.configuration,provenance:result.provenance,audit:result.audit,record_schema:result.record_schema},null,2);if(globalThis.renderOptics)globalThis.renderOptics(result);if(result.scan&&globalThis.renderScan){renderScan(result.scan);$('planeNote').textContent='测量参考时隙中启用发射的各脉冲平均探测面光子 / 发；PDE/FF之前。';}let differs=true;try{differs=JSON.stringify(collect())!==JSON.stringify(result.configuration.experiment);}catch{}if(differs){$('resultStatus').textContent+=' · 当前表单与结果快照不同';if(result.scan)$('scanViewStatus').textContent+=' · 当前表单已改变';}}
let jobListRevision=0;
async function refreshJobs(){
 const revision=++jobListRevision;clearTimeout(pollTimer);
 const jobs=(await request('/api/jobs')).filter(j=>j.kind===kind);if(revision!==jobListRevision)return;
 const container=$('jobs'),ids=new Set(jobs.map(j=>j.id));
 for(const row of container.querySelectorAll('.job'))if(!ids.has(row.dataset.id))row.remove();
 container.querySelector('.job-empty')?.remove();
 if(!jobs.length){const empty=node('p','暂无任务。');empty.className='job-empty';container.append(empty);}
 jobs.forEach((j,index)=>{
   let row=container.querySelector('[data-id="'+j.id+'"]');
   if(!row){
     row=node('div');row.className='job';row.dataset.id=j.id;
     const info=node('div');info.className='job-info';info.append(node('strong'),node('small'),node('progress'));row.append(info);
     const view=node('button','查看结果');view.className='job-view';view.addEventListener('click',()=>request('/api/jobs/'+j.id+'/result').then(r=>render(r,j.id)).catch(fail));
     const cancel=node('button','取消');cancel.className='job-cancel';cancel.addEventListener('click',async()=>{cancel.disabled=true;try{await request('/api/jobs/'+j.id+'/cancel',{});await refreshJobs();}catch(e){fail(e);cancel.disabled=false;}});
     row.append(view,cancel);
   }
   row.querySelector('strong').textContent=j.id.slice(0,8)+' · '+j.status;row.querySelector('small').textContent=j.message;
   const meter=row.querySelector('progress');meter.max=j.total;meter.value=j.completed;
   row.querySelector('.job-view').classList.toggle('hidden',j.status!=='completed');
   const cancel=row.querySelector('.job-cancel');cancel.classList.toggle('hidden',!['queued','running'].includes(j.status));cancel.disabled=Boolean(j.cancel_requested);cancel.textContent=j.cancel_requested?'取消中…':'取消';
   if(container.children[index]!==row)container.insertBefore(row,container.children[index]||null);
 });
 if(lastJob&&!lastResult){const j=jobs.find(j=>j.id===lastJob);if(j?.status==='completed')render(await request('/api/jobs/'+j.id+'/result'),j.id);else if(j&&['failed','cancelled','interrupted'].includes(j.status))$('resultStatus').textContent='任务 '+j.id.slice(0,8)+' · '+j.status+' · '+j.message+'；没有新的完整结果。';}
 if(jobs.some(j=>['queued','running'].includes(j.status)))pollTimer=setTimeout(()=>refreshJobs().catch(fail),catalog.algorithms.job_poll_ms);
}

async function init(){catalog=await request('/api/experiments/'+kind);if(kind==='system'){$('title').textContent='整机仿真台 · B 空间光学';$('subtitle').textContent='Tx 角能量分布 → Rx PSF → 物理像素 → 共用 SPAD 与读出';document.title='B 空间光学 · 整机仿真台';}if(kind==='scan'){$('title').textContent='整机仿真台 · C 扫描采集';$('subtitle').textContent='逐发Tx/Rx姿态 → 连续SPAD状态 → 真实角bin累计 → 距离线图与点云';document.title='C 扫描采集 · 整机仿真台';}for(const [k,meta]of Object.entries(catalog.curves.groups)){const d=node('details');d.append(node('summary',meta.label));const root=node('div');root.id='curve-'+k;d.append(root);$('curves').append(d);}editors=new CurveEditors(catalog.curves,saveDraft,(k,s)=>request('/api/curve/validate?kind='+k,s));let initial=catalog.defaults;const saved=localStorage.getItem(storageKey);if(saved){try{initial=await request('/api/experiments/'+kind+'/import',saved,true);}catch(e){fail(new Error('旧草稿未加载，已显示当前默认值。'+e.message));}}const transfer=kind==='scan'?sessionStorage.getItem('lidar-system-to-scan'):null;if(transfer){const payload=JSON.parse(transfer);initial=await request('/api/experiments/scan/validate',payload.experiment);sessionStorage.removeItem('lidar-system-to-scan');}fill(initial);if(transfer){saveDraft();$('formStatus').textContent='已继承B参数；C发数由扫描帧预算重新决定。';}await refreshJobs();const selected=new URLSearchParams(location.search).get('job');if(selected){const job=await request('/api/jobs/'+selected);if(job.kind!==kind)throw new Error('任务类型与当前研究入口不一致');if(job.status==='completed'){const result=await request('/api/jobs/'+selected+'/result');fill(await request('/api/experiments/'+kind+'/validate',result.configuration.experiment));render(result,selected);$('formStatus').textContent='已载入所选任务的参数快照；修改参数后需重新提交。';}else{lastJob=selected;await refreshJobs();}}}
$('runLab').addEventListener('click',async()=>{try{$('error').classList.add('hidden');$('runLab').disabled=true;const cfg=await request('/api/experiments/'+kind+'/validate',collect());saveDraft();lastResult=null;const j=await request('/api/jobs',{kind,config:cfg});lastJob=j.id;$('resultStatus').textContent='任务 '+j.id.slice(0,8)+' 正在计算；下方图形为上次结果。';$('exportResult').disabled=true;$('replay').disabled=true;await refreshJobs();}catch(e){fail(e);}finally{$('runLab').disabled=false;}});
$('resetLab').addEventListener('click',async()=>{configLoading=true;$('resetLab').disabled=true;$('runLab').disabled=true;document.querySelectorAll('.controls input,.controls select,.controls textarea').forEach(e=>e.disabled=true);$('formStatus').textContent='正在重新加载默认值…';try{catalog=await request('/api/experiments/'+kind);fill(catalog.defaults);configLoading=false;saveDraft();$('error').classList.add('hidden');}catch(e){fail(e);}finally{configLoading=false;$('resetLab').disabled=false;$('runLab').disabled=false;document.querySelectorAll('.controls input,.controls select,.controls textarea').forEach(e=>e.disabled=false);}});
$('refreshJobs').addEventListener('click',()=>refreshJobs().catch(fail));
$('exportConfig').addEventListener('click',async()=>{try{download(kind+'-config.json',envelope(await request('/api/experiments/'+kind+'/validate',collect())));}catch(e){fail(e);}});
$('importConfig').addEventListener('change',async e=>{try{const file=e.target.files[0];if(file){fill(await request('/api/experiments/'+kind+'/import',await file.text(),true));saveDraft();}}catch(e){fail(e);}});
$('exportResult').addEventListener('click',()=>download(lastJob+'-result.json',lastResult));
$('replay').addEventListener('click',async()=>{try{const h=await request('/api/jobs/'+lastJob+'/replay',{bin_ps:Number($('replayBin').value)});histogram(h);$('formStatus').textContent='已用同一份采集记录重放，没有重新采样。';}catch(e){fail(e);}});
window.addEventListener('resize',()=>{if(lastResult){heatmap(lastResult.illumination.signal_photons_per_pixel_per_pulse,lastResult.illumination.shape);histogram(lastResult.histogram);}});
init().catch(fail);

function updateVisibility(){
 const field=p=>$('fields').querySelector('[data-path="'+p+'"]');
 const show=(p,visible)=>{const el=field(p);if(el)el.closest('label').classList.toggle('hidden',!visible);};
 if(kind==='spad'){show('illumination.pixel_weights',field('illumination.spatial_mode')?.value==='weights');return;}
 const tx=field('optics.tx_model')?.value,rx=field('optics.rx_model')?.value;
 for(const k of ['tx_fwhm_h_mrad','tx_fwhm_v_mrad','tx_center_h_mrad','tx_center_v_mrad'])show('optics.'+k,tx==='gaussian');
 for(const k of ['psf_sigma_um','focal_length_h_mm','focal_length_v_mm','mapping_mode','rx_offset_x_um','rx_offset_y_um'])show('optics.'+k,rx==='gaussian_psf');
 for(const k of ['pixel_pitch_um','rx_efficiency'])show('optics.'+k,rx!=='dataset');
 show('optics.dataset',tx==='dataset'||rx==='dataset');for(const k of ['rx_angle_h_min_mrad','rx_angle_h_max_mrad','rx_angle_v_min_mrad','rx_angle_v_max_mrad'])show('optics.'+k,rx!=='dataset');if(kind==='scan'){show('scan.active_fraction',field('scan.trajectory')?.value==='sawtooth');show('scan.mechanical_end_mrad',field('scan.trajectory')?.value!=='static');for(const k of ['channel_h_mrad','channel_v_mrad'])show('scan.'+k,field('scan.channel_direction_mode')?.value==='explicit');}
 $('sourceBanner').textContent=tx!=='dataset'||rx!=='dataset'?'当前包含构造光学模型；用于验证与参数研究，不代表实测光学系统。':'当前使用导入光学数据；来源和构造标识将在结果中保留。';
}

$('zoomHistogram').addEventListener('click',()=>{try{histogram(displayedHistogram);}catch(e){fail(e);}});
$('fullHistogram').addEventListener('click',()=>{if(displayedHistogram){$('plotStart').value=displayedHistogram.edges_ns[0];$('plotEnd').value=displayedHistogram.edges_ns.at(-1);histogram(displayedHistogram);}});

$('collapseLabParameters').onclick=()=>document.querySelectorAll('.controls details').forEach(d=>d.open=false);
$('expandLabParameters').onclick=()=>document.querySelectorAll('.controls details').forEach(d=>d.open=true);
