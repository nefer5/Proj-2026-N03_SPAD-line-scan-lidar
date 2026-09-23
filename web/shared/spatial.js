/* Spatial views consume Python arrays and shared formula definitions only. */
globalThis.renderOptics=function(result){
  const root=$('opticalResults');root.replaceChildren();const o=result.optics;if(!o)return;
  const note=node('p',o.dataset.synthetic?'构造光学样例：用于模型验证，不代表实测Tx/Rx。所有生成参数与数据可导出。':'已导入外部光学数据：'+o.dataset.label);note.className='synthetic-note';root.append(note);
  const provenance=node('p','数据指纹 '+o.dataset_sha256.slice(0,20)+' · Tx '+o.dataset.provenance.tx_model+' / Rx '+o.dataset.provenance.rx_model);provenance.className='muted';root.append(provenance);
  const grid=node('div');grid.className='chart-grid';
  for(const [id,title]of [['txSpatialPlot','Tx 角度单元能量份额（Tx 后）'],['captureSpatialPlot','PSF 感光面截获比例（未补偿边缘损失）']]){const d=node('div');d.append(node('h3',title));const canvas=node('canvas');canvas.id=id;d.append(canvas);grid.append(d);}root.append(grid);
  drawSpatial('txSpatialPlot',o.tx_energy_fraction,'H 角度单元 →');drawSpatial('captureSpatialPlot',o.psf_capture_fraction,'H 角度单元 →');
  if(result.scan){const warning=node('p','下方Tx/PSF数据库图为静态B参考；实际逐发映射与累计结果见C扫描面板及完整导出。');warning.className='muted';root.append(warning);}const title=node('h3','角度单元 → 读出通道：PSF 能量份额');root.append(title);
  const select=node('select');select.id='angleSelect';for(let i=0;i<o.angle_to_channel_fraction.length;i++){const option=node('option','角度单元 '+i+' · H '+o.angular_h_centers_mrad[i].toFixed(3)+' / V '+o.angular_v_centers_mrad[i].toFixed(3)+' mrad');option.value=String(i);select.append(option);}root.append(select);const map=node('div');root.append(map);
  const renderMap=()=>{map.replaceChildren(makeTable(['读出通道','PSF份额'],o.angle_to_channel_fraction[Number(select.value)].map((v,i)=>[i,v.toPrecision(5)])));};select.addEventListener('change',renderMap);renderMap();
  root.append(node('h3',result.scan?'全采集混合角度的原始通道估计（分角结果见C面板）':'各通道测距（未经检测门限判定）'));
  root.append(makeTable(['通道','记录数','原始距离 / m','峰值评分'],result.channel_ranges.rows.map(r=>[r.channel,r.recorded_counts,r.raw_distance_m===null?'—':r.raw_distance_m.toFixed(4),r.peak_score.toPrecision(4)])));
  const rangeNote=node('p','本表是全门原始估计，不声明Pd/PFA或成功检出。无记录通道显示 —；周期参考时间可能存在距离混叠。');rangeNote.className='muted';root.append(rangeNote);
  const flow=result.photon_flow;root.append(node('h3',flow.title));const intro=node('p',flow.intro+' 背景原始光子积分波段：'+flow.background_integration_band_nm.join('–')+' nm。');intro.className='muted';root.append(intro);
  for(const step of flow.steps){const d=node('details');d.append(node('summary',step.title));const logic=node('p',step.logic);logic.className='muted';d.append(logic);const formula=node('div');formula.className='formula';d.append(formula);const symbols=node('p',step.symbols);symbols.className='muted';d.append(symbols);d.append(makeTable(['中间量','数值','单位'],step.values.map(v=>[v.label,typeof v.value==='number'?v.value.toPrecision(7):String(v.value),v.unit])));root.append(d);try{katex.render(step.latex,formula,{displayMode:true,throwOnError:true});}catch(e){formula.textContent='公式渲染失败：'+e.message+'\n'+step.latex;}}
};
function makeTable(headers,rows){const t=node('table'),head=node('tr');headers.forEach(h=>head.append(node('th',h)));t.append(head);for(const row of rows){const r=node('tr');row.forEach(v=>r.append(node('td',String(v))));t.append(r);}return t;}
function drawSpatial(id,rows,xlabel){const [c,w,h]=setup($(id)),ny=rows.length,nx=rows[0].length;let max=0;for(const row of rows)for(const v of row)max=Math.max(max,v);const left=34,top=12,cw=(w-left-12)/nx,ch=(h-top-36)/ny;for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const f=max?rows[y][x]/max:0;c.fillStyle=`hsl(${210-35*f} 70% ${12+48*f}%)`;c.fillRect(left+x*cw,top+y*ch,cw-1,ch-1);}c.fillStyle='#8da0b3';c.font='11px Segoe UI';c.fillText(xlabel,left,h-10);c.fillText('峰值 '+max.toPrecision(5),left+130,h-10);c.fillText('V',8,20);}
if(kind==='system'||kind==='scan'){
  $('opticalFiles').classList.remove('hidden');
  $('exportOptics').addEventListener('click',async()=>{try{download('optical-dataset.json',await request('/api/experiments/'+kind+'/optical-data',collect()));}catch(e){fail(e);}});
  $('importOptics').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;const data=await request('/api/optics/validate',await file.text(),true);const cfg=collect();cfg.optics.dataset=data;cfg.optics.tx_model='dataset';cfg.optics.rx_model='dataset';fill(await request('/api/experiments/'+kind+'/validate',cfg));saveDraft();$('formStatus').textContent='已导入并选择Tx/Rx数据库：'+data.label;}catch(e){fail(e);}});
}
window.addEventListener('resize',()=>{if(lastResult?.optics){drawSpatial('txSpatialPlot',lastResult.optics.tx_energy_fraction,'H 角度单元 →');drawSpatial('captureSpatialPlot',lastResult.optics.psf_capture_fraction,'H 角度单元 →');}});
