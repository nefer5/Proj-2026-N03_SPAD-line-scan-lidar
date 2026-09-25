/* Review-only B channel locator. Geometry and all physical arrays come from Python. */
'use strict';
const $=id=>document.getElementById(id);
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(value,d=2)=>Number(value).toLocaleString('en-US',{maximumFractionDigits:d});
const photonLabel=v=>v!==0&&Math.abs(v)<.001?v.toExponential(3):fmt(v,3);
const channelId=id=>String(id).padStart(2,'0');
let snapshot,data,selected,range,inspected;
function error(id,message){$(id).hidden=!message;$(id).textContent=message;}
function color(f){const stops=[[0,[19,33,55]],[.35,[56,104,161]],[.65,[74,162,164]],[1,[230,215,140]]];let i=1;while(i<stops.length-1&&f>stops[i][0])i++;const [a,ca]=stops[i-1],[b,cb]=stops[i];return `rgb(${ca.map((v,k)=>Math.round(v+(cb[k]-v)*(f-a)/(b-a))).join(',')})`;}
function loadCase(index){
 data=snapshot.cases[index];const l=data.layout;selected=[l.channels[0].id,l.channels[Math.floor(l.channels.length/2)].id].filter((v,i,a)=>a.indexOf(v)===i);inspected=selected.at(-1);range=[...data.focus_window_ns];
 $('sourceState').textContent=data.kind==='acquisition'?'布局 / 光斑 / 直方图：均来自这一次采集':'布局 / 光斑：来自 YAML 默认参数快照；尚未采集';
 $('sourceDetail').textContent=(data.job_id?'任务 '+data.job_id.slice(0,12)+' · ':'')+'配置 '+data.provenance.configuration_sha256.slice(0,12);
 $('sourceDescription').innerHTML=`${data.kind==='acquisition'?'已保存的采集记录；本预览未重新采样。':'构建本预览时，从 config/defaults.yaml 重新读取并由 Python 生成的参数图。'}<br>数据时间：${esc(data.provenance.utc)} · 模型 ${esc(data.provenance.model_version)}<br>完整配置指纹：${esc(data.provenance.configuration_sha256)}${data.job_id?`<br>任务：${esc(data.job_id)} · <a href="/system?job=${encodeURIComponent(data.job_id)}">查看原采集</a>`:''}`;
 $('layoutMetrics').innerHTML=[['读出通道 · H × V',`${l.channels_h} × ${l.channels_v}`,`共 ${l.total_channels} 个通道`,true],['每通道 binning · H × V',`${l.binning_h} × ${l.binning_v}`,`每通道 ${l.spads_per_channel} 个 SPAD`],['物理像素 · H × V',`${l.pixels_h} × ${l.pixels_v}`,'两轴分别按通道数 × binning 展开'],['阵列 SPAD 总数',fmt(l.total_pixels,0),'由物理像素布局派生']].map(([label,value,note,accent])=>`<article class="metric"><span>${label}</span><strong class="${accent?'accent':''}">${value}</strong><small>${note}</small></article>`).join('');
 const columns=`26px repeat(${l.channels_h},minmax(0,1fr))`;$('pickerHeading').style.gridTemplateColumns=columns;$('channelPicker').style.gridTemplateColumns=columns;
 $('pickerHeading').innerHTML='<span>V</span>'+Array.from({length:l.channels_h},(_,h)=>`<span>H${h}</span>`).join('');
 let buttons='';for(let v=l.channels_v-1;v>=0;v--){buttons+=`<span class="row-index">V${v}</span>`;for(const c of l.channels.filter(c=>c.v===v))buttons+=`<button class="channel-button" data-picker-channel="${c.id}" aria-label="展示 CH ${channelId(c.id)} H${c.h} V${c.v}" aria-pressed="false"><strong>CH ${channelId(c.id)}</strong><small>H${c.h} · V${c.v}</small></button>`;}
 $('channelPicker').innerHTML=buttons;
 const example=l.channels.filter(c=>c.h<2&&c.v<2).sort((a,b)=>b.v-a.v||a.h-b.h);$('numberingExample').style.gridTemplateColumns=`repeat(${Math.min(2,l.channels_h)},1fr)`;$('numberingExample').innerHTML=example.map(c=>`<span class="${c.id===0?'origin':''}">CH ${channelId(c.id)}<br>H${c.h} · V${c.v}</span>`).join('');
 $('photonPeak').textContent=photonLabel(data.signal_peak);$('histSource').textContent=data.histogram?'真实采集 · 随所选通道联动':'当前为参数预览';$('histControls').hidden=!data.histogram;
 for(const input of document.querySelectorAll('[data-series]')){const available=input.dataset.series==='observed'||input.dataset.series==='ideal'&&!!data.references||['noise','error'].includes(input.dataset.series)&&!!data.statistics;input.disabled=!available;input.checked=available;}
 $('statisticsNote').textContent=data.statistics?`${data.statistics.trial_count} 次含噪采集，${data.statistics.noise_trial_count} 次纯噪声采集。误差棒表示逐时间分箱的样本最小—最大值，包含当前探测记录；不是置信区间。`:'未保存的随机记录与统计不会补造。';
 error('selectionError','');error('timeError','');drawSensor();updateSelection();showDetail(inspected);
}
function drawSensor(){
 const l=data.layout,xe=data.x_edges_um,ye=data.y_edges_um,xmin=xe[0],xmax=xe.at(-1),ymin=ye[0],ymax=ye.at(-1);
 const scale=Math.min(270/(xmax-xmin),425/(ymax-ymin)),w=(xmax-xmin)*scale,h=(ymax-ymin)*scale,left=210-w/2,top=48+(425-h)/2;
 const sx=x=>left+(x-xmin)*scale,sy=y=>top+h-(y-ymin)*scale;
 let svg=`<svg viewBox="0 0 440 535" xmlns="http://www.w3.org/2000/svg" aria-label="读出通道，H 向右、V 向上；实际像面等比例" role="group"><rect x="${left}" y="${top}" width="${w}" height="${h}" fill="#091019"/><g id="spotLayer">`;
 for(let v=0;v<l.pixels_v;v++)for(let u=0;u<l.pixels_h;u++){const photons=data.signal_photons_per_pixel_per_pulse[v*l.pixels_h+u];svg+=`<rect x="${sx(xe[u])}" y="${sy(ye[v+1])}" width="${(xe[u+1]-xe[u])*scale}" height="${(ye[v+1]-ye[v])*scale}" fill="${color(data.signal_peak?photons/data.signal_peak:0)}"/>`;}
 svg+='</g><g id="pixelLayer" stroke="#9cc4d840" stroke-width=".45" pointer-events="none">';
 for(const x of xe)svg+=`<path d="M${sx(x)} ${top}v${h}"/>`;for(const y of ye)svg+=`<path d="M${left} ${sy(y)}h${w}"/>`;svg+='</g>';
 for(const t of [0,.25,.5,.75,1]){const y=ymin+t*(ymax-ymin);svg+=`<path d="M${left-5} ${sy(y)}h-5" stroke="#627f91"/><text class="map-axis" x="${left-14}" y="${sy(y)+3}" text-anchor="end">${fmt(y,1)}</text>`;}
 for(const t of [0,.5,1]){const x=xmin+t*(xmax-xmin);svg+=`<path d="M${sx(x)} ${top+h+5}v5" stroke="#627f91"/><text class="map-axis" x="${sx(x)}" y="${top+h+24}" text-anchor="middle">${fmt(x,1)}</text>`;}
 svg+=`<text class="map-axis" x="${left-12}" y="${top-28}" text-anchor="end">y / μm</text><text class="map-axis" x="${left+w/2}" y="${top+h+47}" text-anchor="middle">x / μm</text>`;
 for(const c of l.channels){if(c.v===l.channels_v-1)svg+=`<text class="map-axis index" x="${sx((c.x_um[0]+c.x_um[1])/2)}" y="${top-14}" text-anchor="middle">H${c.h}</text>`;if(c.h===l.channels_h-1)svg+=`<text class="map-axis index" x="${left+w+13}" y="${sy((c.y_um[0]+c.y_um[1])/2)+3}">V${c.v}</text>`;}
 for(const c of l.channels){const x=sx(c.x_um[0]),y=sy(c.y_um[1]),cw=(c.x_um[1]-c.x_um[0])*scale,ch=(c.y_um[1]-c.y_um[0])*scale;svg+=`<g class="map-channel" data-map-channel="${c.id}" role="button" tabindex="0" aria-label="像面 CH ${channelId(c.id)} H${c.h} V${c.v}" aria-pressed="false"><title>CH ${channelId(c.id)} · H${c.h} V${c.v} · ${c.spad_count} SPAD</title><rect class="channel-frame" x="${x+1}" y="${y+1}" width="${Math.max(0,cw-2)}" height="${Math.max(0,ch-2)}"/><text x="${x+cw/2}" y="${y+ch/2+4}" text-anchor="middle" font-size="${cw>65?13:10}">${cw>65?'CH ':''}${channelId(c.id)}</text></g>`;}
 svg+='</svg>';$('sensorMap').innerHTML=svg;updateMapLayers();
}
function updateMapLayers(){const alpha=Number($('spotOpacity').value)/100;$('spotLayer').setAttribute('opacity',$('spotVisible').checked?alpha:0);$('colorScale').style.opacity=$('spotVisible').checked?alpha:0;$('pixelLayer').style.display=$('pixelGrid').checked?'':'none';$('opacityValue').textContent=$('spotOpacity').value+'%';}
function showDetail(id){inspected=id;const c=data.layout.channels.find(c=>c.id===id);$('detailTitle').textContent=`CH ${channelId(id)} · H${c.h} V${c.v}`;const rows=[['选择状态',selected.includes(id)?'已选择':'未选择'],['包含 SPAD',`${c.pixels_h} × ${c.pixels_v} = ${c.spad_count}`],['x 范围 / μm',c.x_um.map(v=>fmt(v,1)).join(' … ')],['y 范围 / μm',c.y_um.map(v=>fmt(v,1)).join(' … ')],['入射信号光子 / 发',photonLabel(c.signal_photons_per_pulse)],['最终记录数',c.record_count===undefined?'尚未采集':fmt(c.record_count,0)]];$('channelDetail').innerHTML=rows.map(([k,v])=>`<div class="detail-row"><span>${k}</span><strong>${v}</strong></div>`).join('');}
function updateSelection(){
 $('channelInput').value=selected.join(', ');$('selectionCount').textContent=`已选 ${selected.length} / ${data.layout.total_channels}`;
 for(const el of document.querySelectorAll('[data-picker-channel],[data-map-channel]')){const id=Number(el.dataset.pickerChannel??el.dataset.mapChannel),active=selected.includes(id);el.classList.toggle('selected',active);el.setAttribute('aria-pressed',String(active));}
 showDetail(inspected);renderHistograms();
}
function setSelection(next){if(!next.length){error('selectionError','请至少选择一个通道。');return false;}if(next.length>snapshot.max_visible_channels){error('selectionError',`同时展示上限为 ${snapshot.max_visible_channels} 个通道。`);return false;}selected=[...next].sort((a,b)=>a-b);error('selectionError','');updateSelection();return true;}
function toggleChannel(id){inspected=id;setSelection(selected.includes(id)?selected.filter(v=>v!==id):[...selected,id]);}
function parseSelection(){try{const raw=$('channelInput').value.trim();if(!raw)throw Error('请输入至少一个通道编号。');const ids=new Set();for(const token of raw.split(/[，,\s]+/)){const match=/^(\d+)(?:-(\d+))?$/.exec(token);if(!match)throw Error('使用编号或范围，例如 0, 2, 4-5。');const lo=Number(match[1]),hi=match[2]===undefined?lo:Number(match[2]);if(lo>hi||hi>=data.layout.total_channels)throw Error(`有效通道范围为 0–${data.layout.total_channels-1}。`);for(let i=lo;i<=hi;i++)ids.add(i);}setSelection([...ids]);}catch(e){error('selectionError',e.message);}}
function series(){return Object.fromEntries([...document.querySelectorAll('[data-series]')].map(e=>[e.dataset.series,e.checked]));}
function renderHistograms(){if(!data.histogram){$('histograms').innerHTML=`<div class="empty-state"><strong>本工况尚未采集</strong>上方可审核 ${data.layout.channels_h} × ${data.layout.channels_v} 通道的编号与点选；真实直方图请切换到“本次采集”。</div>`;return;}
 $('histograms').innerHTML=selected.map(id=>{const c=data.layout.channels[id];return `<article class="hist-plot" data-hist-card="${id}"><header><strong>CH ${channelId(id)} <small>/ H${c.h} · V${c.v}</small></strong><span>${fmt(c.record_count,0)} 条记录</span></header><canvas data-hist="${id}" aria-label="CH ${channelId(id)} 探测直方图"></canvas><div class="overview-label"><span>全门概览 · 拖动窗口或边界</span><span>橙色：观察窗口</span></div><canvas class="overview" data-overview="${id}" aria-label="CH ${channelId(id)} 全门概览"></canvas></article>`;}).join('');
 const gate=[data.histogram.edges_ns[0],data.histogram.edges_ns.at(-1)];for(const id of selected)PhotonHistogram.bindOverview(document.querySelector(`[data-overview="${id}"]`),gate,()=>range,value=>{range=value;drawHistograms();});drawHistograms();
}
function drawHistograms(){if(!data.histogram)return;$('timeMin').value=Number(range[0].toPrecision(12));$('timeMax').value=Number(range[1].toPrecision(12));const visible=series(),maximum=Math.max(...selected.map(id=>PhotonHistogram.maximum(data,id,range,visible))),gate=[data.histogram.edges_ns[0],data.histogram.edges_ns.at(-1)];for(const id of selected){PhotonHistogram.draw(document.querySelector(`[data-hist="${id}"]`),data,id,range,maximum,visible);PhotonHistogram.draw(document.querySelector(`[data-overview="${id}"]`),data,id,gate,PhotonHistogram.maximum(data,id,gate,{observed:true}),visible,true,range);}}
function applyTime(){const lo=$('timeMin').valueAsNumber,hi=$('timeMax').valueAsNumber,g=data.histogram.edges_ns;if(!Number.isFinite(lo)||!Number.isFinite(hi)||lo>=hi||lo<g[0]||hi>g.at(-1)){error('timeError',`时间须位于 ${g[0]}–${g.at(-1)} ns 内，且起点小于终点。`);return;}range=[lo,hi];error('timeError','');drawHistograms();}
async function init(){const response=await fetch(document.body.dataset.snapshot,{cache:'no-store'});if(!response.ok)throw Error(`快照加载失败：HTTP ${response.status}`);snapshot=await response.json();try{katex.render(String.raw`\mathrm{CH}=V\,N_H+H`,$('numberingFormula'),{throwOnError:true});}catch(e){$('numberingFormula').textContent='CH = V × N_H + H（公式渲染失败：'+e.message+'）';}$('casePicker').innerHTML=snapshot.cases.map((c,i)=>`<option value="${i}">${esc(c.label)} · ${c.layout.channels_h} × ${c.layout.channels_v}</option>`).join('');$('casePicker').onchange=()=>loadCase(Number($('casePicker').value));
 $('sourceToggle').onclick=()=>{const show=$('sourceDescription').hidden;$('sourceDescription').hidden=!show;$('sourceToggle').setAttribute('aria-expanded',String(show));};
 $('applyChannels').onclick=parseSelection;$('channelInput').onkeydown=e=>{if(e.key==='Enter')parseSelection();};$('firstChannel').onclick=()=>{inspected=0;setSelection([0]);};
 $('channelPicker').onclick=e=>{const el=e.target.closest('[data-picker-channel]');if(el)toggleChannel(Number(el.dataset.pickerChannel));};
 $('sensorMap').onclick=e=>{const el=e.target.closest('[data-map-channel]');if(el)toggleChannel(Number(el.dataset.mapChannel));};
 $('sensorMap').onkeydown=e=>{const el=e.target.closest('[data-map-channel]');if(el&&['Enter',' '].includes(e.key)){e.preventDefault();toggleChannel(Number(el.dataset.mapChannel));}};
 for(const name of ['pointerover','focusin'])$('sensorMap').addEventListener(name,e=>{const el=e.target.closest('[data-map-channel]');if(el)showDetail(Number(el.dataset.mapChannel));});
 for(const id of ['spotVisible','spotOpacity','pixelGrid'])$(id).addEventListener('input',updateMapLayers);
 $('applyWindow').onclick=applyTime;for(const id of ['timeMin','timeMax'])$(id).onkeydown=e=>{if(e.key==='Enter')applyTime();};$('focusEcho').onclick=()=>{range=[...data.focus_window_ns];error('timeError','');drawHistograms();};$('fullGate').onclick=()=>{range=[data.histogram.edges_ns[0],data.histogram.edges_ns.at(-1)];error('timeError','');drawHistograms();};
 for(const e of document.querySelectorAll('[data-series]'))e.onchange=drawHistograms;window.addEventListener('resize',drawHistograms);loadCase(0);document.body.dataset.ready='true';
}
init().catch(e=>{error('loadingError',e.message);console.error(e);});
