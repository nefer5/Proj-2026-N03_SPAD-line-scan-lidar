/* Reusable readout locator. Python owns geometry, photons and record totals.
 * Selection is controlled by the host so map, picker and histograms cannot drift.
 */
(function(){
'use strict';
const fmt=(n,d=2)=>Number(n).toLocaleString('en-US',{maximumFractionDigits:d});
const number=n=>n!==0&&Math.abs(n)<.001?n.toExponential(3):fmt(n,3);
const id=n=>String(n).padStart(2,'0');
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function color(f){const stops=[[0,[19,33,55]],[.35,[56,104,161]],[.65,[74,162,164]],[1,[230,215,140]]];let i=1;while(i<stops.length-1&&f>stops[i][0])i++;const[a,ca]=stops[i-1],[b,cb]=stops[i];return `rgb(${ca.map((v,k)=>Math.round(v+(cb[k]-v)*(f-a)/(b-a))).join(',')})`;}
class PhotonChannelLocator{
 constructor(root,controls,{onToggle,onSelect}){
  this.root=root;this.controls=controls;this.onToggle=onToggle;this.selected=[];this.inspected=undefined;
  root.innerHTML=`<div class="cl-source" data-cl="source"></div><div class="cl-metrics" data-cl="metrics"></div><div class="cl-layout"><aside class="cl-selection"><div data-cl="controls"></div><div class="cl-count"><span data-cl="count"></span><button class="text-button" data-cl="first">仅选 CH 00</button></div><div data-cl="picker-heading" class="cl-picker-heading"></div><div data-cl="picker-slot"></div><p class="cl-key"><span><i></i>已选通道</span><span>↑ V 增大</span></p><p class="field-note">选择只改变显示，不改变采集通道、能量或统计。</p></aside><div class="cl-sensor"><div class="cl-heading"><h3>SPAD 像面 · 读出通道分布</h3><span class="unit">物理等比例 · μm</span></div><div class="cl-tools"><label><input type="checkbox" data-cl="spot-visible" checked>光斑底图</label><label>不透明度<input type="range" data-cl="opacity" aria-label="光斑不透明度" min="0" max="100" value="55"><output data-cl="opacity-value">55%</output></label><label><input type="checkbox" data-cl="pixel-grid" checked>SPAD 像素边界</label></div><div class="cl-sensor-body"><div class="cl-map-wrap"><div data-cl="map" role="group" aria-label="可点选的 SPAD 通道分布"></div><p>H / x →　V / y ↑　<span>正上 · 负下</span></p></div><aside class="cl-detail"><div class="cl-detail-card"><span class="section-kicker">CHANNEL DETAIL</span><h3 data-cl="detail-title"></h3><div data-cl="detail-values"></div><p class="field-note">悬停或键盘聚焦查看；点击加入 / 移出选择。</p></div><div class="cl-numbering"><h3>编号从左下角开始</h3><div data-cl="formula"></div><p data-cl="numbering-note"></p><div class="cl-example" data-cl="example"></div></div><div class="cl-spot-key"><span>光斑底图色标</span><div class="cl-scale" data-cl="scale"></div><div class="cl-scale-labels"><span>0</span><span data-cl="peak"></span></div><p>信号光子 / 物理像素 / 发<br><span class="muted">探测面 · PDE / FF 前</span></p></div></aside></div><p class="cl-note">底图为该采集工况全光斑在像面的像素积分，非单角 PSF，也非最终探测计数。网格表示完整物理像素；当前 FF 模型未定义像素内部感光区的具体形状。</p></div></div>`;
  this.q('controls').append(controls);
  this.picker=controls.querySelector('#channelPicker');this.q('picker-slot').append(this.picker);
  this.q('first').onclick=()=>{this.inspected=0;onSelect([0]);};
  this.q('map').onclick=e=>{const cell=e.target.closest('[data-map-channel]');if(cell){this.inspected=+cell.dataset.mapChannel;onToggle(this.inspected);}};
  this.q('map').onkeydown=e=>{const cell=e.target.closest('[data-map-channel]');if(cell&&['Enter',' '].includes(e.key)){e.preventDefault();this.inspected=+cell.dataset.mapChannel;onToggle(this.inspected);}};
  for(const event of ['pointerover','focusin'])this.q('map').addEventListener(event,e=>{const cell=e.target.closest('[data-map-channel]');if(cell)this.showDetail(+cell.dataset.mapChannel);});
  for(const key of ['spot-visible','opacity','pixel-grid'])this.q(key).oninput=()=>this.updateLayers();
 }
 q(key){return this.root.querySelector(`[data-cl="${key}"]`);}
 setModel(view,jobId){
  this.view=view;this.layout=view.readout_layout;this.values=view.readout_channel_values;
  if(!this.layout||!this.values)throw Error('通道分布缺少服务端布局或光子汇总，请刷新重试。');
  const l=this.layout;this.root.classList.remove('hidden');this.root.dataset.configuration=view.provenance.configuration_sha256;
  this.q('source').textContent=`布局 / 光斑 / 直方图均来自采集 ${jobId} · 配置 ${view.provenance.configuration_sha256.slice(0,12)}`;
  this.q('metrics').innerHTML=[['读出通道 · H × V',`${l.channels_h} × ${l.channels_v}`,`${l.total_channels} 个通道`],['每通道 binning · H × V',`${l.binning_h} × ${l.binning_v}`,`${l.spads_per_channel} 个 SPAD / 通道`],['物理像素 · H × V',`${l.pixels_h} × ${l.pixels_v}`,`全阵列 ${fmt(l.total_pixels,0)} 个 SPAD`]].map(([label,value,note])=>`<div><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
  const cols=`26px repeat(${l.channels_h},minmax(${l.channels_h<=2?0:68}px,1fr))`;this.picker.style.gridTemplateColumns=cols;this.q('picker-heading').style.gridTemplateColumns=cols;
  this.q('picker-heading').innerHTML='<span>V</span>'+Array.from({length:l.channels_h},(_,h)=>`<span>H${h}</span>`).join('');
  let html='';for(let v=l.channels_v-1;v>=0;v--){html+=`<span class="cl-row-index">V${v}</span>`;for(const c of l.channels.filter(c=>c.v===v))html+=`<button data-channel="${c.id}" aria-label="展示 CH ${id(c.id)} H${c.h} V${c.v}" aria-pressed="false"><strong>CH ${id(c.id)}</strong><small>H${c.h} · V${c.v}</small></button>`;}
  this.picker.innerHTML=html;
  // Both headings and cells scroll horizontally together for wide arrays.
  this.picker.onscroll=()=>this.q('picker-heading').scrollLeft=this.picker.scrollLeft;
  const example=l.channels.filter(c=>c.h<2&&c.v<2).sort((a,b)=>b.v-a.v||a.h-b.h);
  this.q('example').style.gridTemplateColumns=`repeat(${Math.min(2,l.channels_h)},1fr)`;this.q('example').innerHTML=example.map(c=>`<span class="${c.id===0?'origin':''}">CH ${id(c.id)}<br>H${c.h} · V${c.v}</span>`).join('');
  try{katex.render(view.formulas.b_readout_channel_index,this.q('formula'),{throwOnError:true});}catch(e){this.q('formula').textContent='公式渲染失败：'+e.message+' / '+view.formulas.b_readout_channel_index;}
  this.q('numbering-note').textContent=view.formula_notes.b_readout_channel_index;
  this.q('peak').textContent=number(this.values.signal_peak);
  if(!l.channels.some(c=>c.id===this.inspected))this.inspected=l.channels[0].id;
  this.drawSensor();
 }
 setSelection(selected){
  this.selected=[...selected];if(!this.layout)return;
  this.q('count').textContent=`已选 ${selected.length} / ${this.layout.total_channels}`;
  for(const node of this.root.querySelectorAll('[data-channel],[data-map-channel]')){const active=selected.includes(+(node.dataset.channel??node.dataset.mapChannel));node.classList.toggle('selected',active);node.setAttribute('aria-pressed',String(active));}
  this.showDetail(this.inspected);
 }
 updateLayers(){const alpha=Number(this.q('opacity').value)/100,visible=this.q('spot-visible').checked;this.q('spot').setAttribute('opacity',visible?alpha:0);this.q('scale').style.opacity=visible?alpha:0;this.q('pixels').style.display=this.q('pixel-grid').checked?'':'none';this.q('opacity-value').textContent=this.q('opacity').value+'%';}
 showDetail(channel){
  this.inspected=channel;const c=this.layout.channels.find(c=>c.id===channel),value=this.values.channels.find(c=>c.id===channel);
  this.q('detail-title').textContent=`CH ${id(channel)} · H${c.h} V${c.v}`;
  const rows=[['选择状态',this.selected.includes(channel)?'已选择':'未选择'],['包含 SPAD',`${c.pixels_h} × ${c.pixels_v} = ${c.spad_count}`],['x 范围 / μm',c.x_um.map(v=>fmt(v,2)).join(' … ')],['y 范围 / μm',c.y_um.map(v=>fmt(v,2)).join(' … ')],['入射信号光子 / 发',number(value.signal_photons_per_pulse)],['最终记录数',value.record_count===undefined?'尚未采集':fmt(value.record_count,0)]];
  this.q('detail-values').innerHTML=rows.map(([name,value])=>`<div class="cl-detail-row"><span>${name}</span><strong>${escape(value)}</strong></div>`).join('');
 }
 drawSensor(){
  const l=this.layout,xe=this.view.x_edges_um,ye=this.view.y_edges_um,xmin=xe[0],xmax=xe.at(-1),ymin=ye[0],ymax=ye.at(-1);
  const scale=Math.min(270/(xmax-xmin),425/(ymax-ymin)),w=(xmax-xmin)*scale,h=(ymax-ymin)*scale,left=210-w/2,top=48+(425-h)/2;
  const sx=x=>left+(x-xmin)*scale,sy=y=>top+h-(y-ymin)*scale;
  let svg=`<svg viewBox="0 0 440 535" xmlns="http://www.w3.org/2000/svg" role="group" aria-label="读出通道，H 向右、V 向上；实际像面等比例"><rect x="${left}" y="${top}" width="${w}" height="${h}" fill="#091019"/><g data-cl="spot">`;
  const photons=this.view.illumination.signal_photons_per_pixel_per_pulse;
  for(let v=0;v<l.pixels_v;v++)for(let u=0;u<l.pixels_h;u++){const n=photons[v*l.pixels_h+u];svg+=`<rect x="${sx(xe[u])}" y="${sy(ye[v+1])}" width="${(xe[u+1]-xe[u])*scale}" height="${(ye[v+1]-ye[v])*scale}" fill="${color(this.values.signal_peak?n/this.values.signal_peak:0)}"/>`;}
  svg+='</g><g data-cl="pixels" stroke="#9cc4d840" stroke-width=".45" pointer-events="none">';for(const x of xe)svg+=`<path d="M${sx(x)} ${top}v${h}"/>`;for(const y of ye)svg+=`<path d="M${left} ${sy(y)}h${w}"/>`;svg+='</g>';
  for(const t of [0,.25,.5,.75,1]){const y=ymin+t*(ymax-ymin);svg+=`<path d="M${left-5} ${sy(y)}h-5" stroke="#627f91"/><text class="cl-axis" x="${left-14}" y="${sy(y)+3}" text-anchor="end">${fmt(y,1)}</text>`;}
  for(const t of [0,.5,1]){const x=xmin+t*(xmax-xmin);svg+=`<path d="M${sx(x)} ${top+h+5}v5" stroke="#627f91"/><text class="cl-axis" x="${sx(x)}" y="${top+h+24}" text-anchor="middle">${fmt(x,1)}</text>`;}
  svg+=`<text class="cl-axis" x="${left-12}" y="${top-28}" text-anchor="end">y / μm</text><text class="cl-axis" x="${left+w/2}" y="${top+h+47}" text-anchor="middle">x / μm</text>`;
  for(const c of l.channels){if(c.v===l.channels_v-1)svg+=`<text class="cl-axis index" x="${sx((c.x_um[0]+c.x_um[1])/2)}" y="${top-14}" text-anchor="middle">H${c.h}</text>`;if(c.h===l.channels_h-1)svg+=`<text class="cl-axis index" x="${left+w+13}" y="${sy((c.y_um[0]+c.y_um[1])/2)+3}">V${c.v}</text>`;}
  for(const c of l.channels){const x=sx(c.x_um[0]),y=sy(c.y_um[1]),cw=(c.x_um[1]-c.x_um[0])*scale,ch=(c.y_um[1]-c.y_um[0])*scale,inset=Math.min(1,cw/8,ch/8);svg+=`<g class="cl-map-channel" data-map-channel="${c.id}" role="button" tabindex="0" aria-label="像面 CH ${id(c.id)} H${c.h} V${c.v}" aria-pressed="false"><title>CH ${id(c.id)} · H${c.h} V${c.v} · ${c.spad_count} SPAD</title><rect class="cl-channel-frame" x="${x+inset}" y="${y+inset}" width="${cw-2*inset}" height="${ch-2*inset}"/>${cw>=18&&ch>=12?`<text x="${x+cw/2}" y="${y+ch/2+4}" text-anchor="middle" font-size="${cw>65?13:10}">${cw>65?'CH ':''}${id(c.id)}</text>`:''}</g>`;}
  this.q('map').innerHTML=svg+'</svg>';this.updateLayers();
 }
}
globalThis.PhotonChannelLocator=PhotonChannelLocator;
})();
