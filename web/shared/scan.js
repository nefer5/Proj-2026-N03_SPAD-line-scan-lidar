/* Rendering only. Schedules, angular membership, ranging and XYZ live in Python. */
let scanData=null,scanTablePage=0;
const scanColors=['#41d9d0','#659cff','#ffb55b','#d291ff','#f77a91','#b8df77'];
function scanPlot(id,series,xLabel,yLabel,scatter=false){
 const [c,w,h]=setup($(id));const pairs=series.flatMap(s=>s.points.filter(p=>p&&p.every(Number.isFinite)));
 if(!pairs.length){c.fillStyle='#8da0b3';c.font='13px Segoe UI';c.fillText('暂无可绘制数据',30,45);return;}
 let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;for(const [x,y]of pairs){xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
 const dx=xmax-xmin||1,dy=ymax-ymin||1;xmin-=dx*.04;xmax+=dx*.04;ymin-=dy*.08;ymax+=dy*.08;if(id==='scanDwellPlot'){ymin=0;ymax=Math.max(1,Math.ceil(ymax));}
 const left=58,top=16,pw=w-left-15,ph=h-top-40;const px=x=>left+(x-xmin)/(xmax-xmin)*pw,py=y=>top+ph-(y-ymin)/(ymax-ymin)*ph;
 c.strokeStyle='#263547';c.beginPath();c.moveTo(left,top);c.lineTo(left,top+ph);c.lineTo(left+pw,top+ph);c.stroke();
 for(const s of series){c.strokeStyle=s.color;c.fillStyle=s.color;c.lineWidth=1.5;let started=false;c.beginPath();for(const point of s.points){if(!point||!point.every(Number.isFinite)){started=false;continue;}const [x,y]=point;if(scatter){c.moveTo(px(x)+2,py(y));c.arc(px(x),py(y),2,0,2*Math.PI);}else{if(!started)c.moveTo(px(x),py(y));else c.lineTo(px(x),py(y));started=true;}}if(scatter)c.fill();else c.stroke();}
 c.fillStyle='#8da0b3';c.font='10px Segoe UI';c.fillText(xmin.toPrecision(4),left,h-15);c.fillText(xmax.toPrecision(4),Math.max(left,w-90),h-15);c.fillText(ymax.toPrecision(4),2,top+8);c.fillText(ymin.toPrecision(4),2,top+ph);c.fillText(xLabel,left+pw/2-25,h-1);c.fillText(yLabel,left+4,top+8);
}
function scanSelect(id,options,previous){const select=$(id);select.replaceChildren();for(const [value,label]of options){const option=node('option',label);option.value=String(value);select.append(option);}if(options.some(o=>String(o[0])===previous))select.value=previous;}
globalThis.renderScan=function(data,preview=false){
 scanData=data;scanTablePage=0;$('scanPanel').classList.remove('hidden');$('scanViewStatus').textContent=preview?'仅预览时序，尚未模拟光子':'实际采集记录 · '+data.processing_bin_ps+' ps';
 const summary=data.summary;$('scanMetrics').replaceChildren();
 const metric=v=>v===null||v===undefined?'—':Number(v).toPrecision(4);
 $('scanErrorSummary').textContent=preview?'':'有输出且有源信号参考的格点 RMSE：'+metric(summary.conditional_range_rmse_m)+' m · 最大编码器/发射角差：'+metric(summary.max_encoder_vs_emission_error_mrad)+' mrad · 末门截断：'+metric(summary.gate_truncated_ns)+' ns';
 for(const [label,key]of [['名义触发时隙','scheduled_slots'],['启用发射时隙','emitted_reference_slots'],['真实有效发数','true_useful_pulses'],['角bin分配发数','assigned_pulses'],['保留记录','retained_records'],['空角bin','empty_angle_bins']]){const el=node('div');el.className='metric';el.append(node('small',label),node('strong',summary[key]===undefined?'—':String(summary[key])));$('scanMetrics').append(el);}
 scanSelect('scanFrame',data.assigned_pulses_per_frame_bin.map((_,i)=>[i,'帧 '+i]),$('scanFrame').value);
 scanSelect('scanAngle',data.angle_bin_centers_mrad.map((v,i)=>[i,'bin '+i+' · '+v.toFixed(3)+' mrad']),$('scanAngle').value);
 const channels=data.histogram_cube_counts?.[0]?.[0]?.length||0;scanSelect('scanChannel',Array.from({length:channels},(_,i)=>[i,'通道 '+i]),$('scanChannel').value);
 $('scanReplay').disabled=preview;$('exportCloud').disabled=preview;$('showScanPulse').disabled=preview;
 if(!preview){$('scanReplayBin').value=data.processing_bin_ps;$('scanPulse').value=data.schedule[0]?.cycle??'';}
 $('scanNotes').textContent=preview?'预览只计算轨迹和真实离散发数；Rx覆盖和光子采集由提交仿真继续验证。':data.reconstruction_note+' '+(data.assumptions||[]).join(' ');
 drawScanViews();drawScanTable();
};
function drawScanViews(){
 if(!scanData)return;const f=Number($('scanFrame').value);const rows=scanData.schedule.filter(r=>r.frame===f);
 scanPlot('scanTrajectoryPlot',[{color:'#41d9d0',points:rows.map(r=>[r.nominal_time_ns,r.true_tx_optical_mrad])},{color:'#ffb55b',points:rows.map(r=>[r.nominal_time_ns,r.encoder_optical_mrad])},{color:'#8da0b3',points:rows.map(r=>[r.nominal_time_ns,r.command_optical_mrad])}],'时间 ns','光学角 mrad');
 scanPlot('scanDwellPlot',[{color:'#41d9d0',points:scanData.angle_bin_centers_mrad.map((x,i)=>[x,scanData.true_useful_pulses_per_frame_bin[f][i]])},{color:'#ffb55b',points:scanData.angle_bin_centers_mrad.map((x,i)=>[x,scanData.assigned_pulses_per_frame_bin[f][i]])}],'扫描角 mrad','发数',true);
 const n=scanData.histogram_cube_counts?.[f]?.[0]?.length||0;
 scanPlot('scanRangePlot',Array.from({length:n},(_,ch)=>({color:scanColors[ch%scanColors.length],points:(scanData.range_rows||[]).filter(r=>r.frame===f&&r.channel===ch).map(r=>r.raw_distance_m===null||r.reported_h_mrad===null?null:[r.reported_h_mrad,r.raw_distance_m])})),'报告H角 mrad','距离 m');
 scanPlot('scanCloudPlot',Array.from({length:n},(_,ch)=>({color:scanColors[ch%scanColors.length],points:(scanData.point_cloud||[]).filter(r=>r.frame===f&&r.channel===ch).map(r=>[r.x_m,r.z_m])})),'X m','Z m',true);
 drawScanBin();
}
function drawScanBin(){if(!scanData)return;const f=Number($('scanFrame').value),b=Number($('scanAngle').value),ch=Number($('scanChannel').value);const values=scanData.histogram_cube_counts?.[f]?.[b]?.[ch];scanPlot('scanBinPlot',values?[{color:scanColors[ch%scanColors.length],points:values.map((v,i)=>[scanData.histogram_time_ns[i],v])}]:[],'相对时间 ns','记录');}
function drawScanTable(){if(!scanData)return;const size=catalog.algorithms.scan_preview_table_rows,rows=scanData.schedule.filter(r=>r.frame===Number($('scanFrame').value));const pages=Math.ceil(rows.length/size);scanTablePage=Math.max(0,Math.min(scanTablePage,pages-1));const current=rows.slice(scanTablePage*size,(scanTablePage+1)*size);$('scanTable').replaceChildren(makeTable(['时隙','名义 ns','发射 ns','机械 mrad','实际光学 mrad','编码器 mrad','发射','标签bin','真实bin'],current.map(r=>[r.cycle,r.nominal_time_ns.toFixed(2),r.emission_time_ns.toFixed(2),r.mechanical_angle_mrad.toFixed(3),r.true_tx_optical_mrad.toFixed(3),r.encoder_optical_mrad.toFixed(3),r.emitted?'是':'关闭',r.assigned_bin,r.true_bin])));$('scanPageInfo').textContent=rows.length+' 个时隙 · 页 '+(pages?scanTablePage+1:0)+'/'+pages;}
if(kind==='scan'){
 $('scanActions').classList.remove('hidden');
 $('previewScan').addEventListener('click',async()=>{try{$('previewScan').disabled=true;$('error').classList.add('hidden');renderScan(await request('/api/experiments/scan/preview',collect()),true);}catch(e){fail(e);}finally{$('previewScan').disabled=false;}});
}
$('scanFrame').addEventListener('change',()=>{scanTablePage=0;drawScanViews();drawScanTable();});
$('scanAngle').addEventListener('change',drawScanBin);$('scanChannel').addEventListener('change',drawScanBin);
$('scanPrevious').addEventListener('click',()=>{scanTablePage--;drawScanTable();});$('scanNext').addEventListener('click',()=>{scanTablePage++;drawScanTable();});
$('scanReplay').addEventListener('click',async()=>{try{const r=await request('/api/jobs/'+lastJob+'/scan-replay',{bin_ps:Number($('scanReplayBin').value)});renderScan({...scanData,...r});$('scanViewStatus').textContent='同一采集记录重放 · '+r.processing_bin_ps+' ps；未重新采样';}catch(e){fail(e);}});
$('showScanPulse').addEventListener('click',()=>{try{const cycle=Number($('scanPulse').value),pulse=scanData.signal_components.find(p=>p.cycle===cycle);if(!pulse)throw new Error('该参考时隙不存在');heatmap(pulse.signal_photons_per_pixel,lastResult.illumination.shape);$('planeNote').textContent='参考时隙 '+cycle+' 的探测面光子 / 发，PDE/FF之前；关闭发射时全为0。';$('illuminationPlot').scrollIntoView({block:'center'});}catch(e){fail(e);}});
$('exportCloud').addEventListener('click',()=>{const a=node('a');a.href='/api/jobs/'+lastJob+'/point-cloud.csv?bin_ps='+encodeURIComponent(scanData.processing_bin_ps);a.download=lastJob+'-point-cloud.csv';a.click();});
if(kind==='system'){
 $('systemToScan').classList.remove('hidden');
 $('useSystemForScan').addEventListener('click',async()=>{try{const result=await request('/api/experiments/scan/from-system',collect());sessionStorage.setItem('lidar-system-to-scan',JSON.stringify(result));location.href='/system/scan';}catch(e){fail(e);}});
}
window.addEventListener('resize',drawScanViews);
