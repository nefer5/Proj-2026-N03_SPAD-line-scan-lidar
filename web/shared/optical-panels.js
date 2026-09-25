/* Optional parameter plots and dB views. All physical data comes from Python. */
'use strict';
const figureLabels={pulse:'Tx 波形',filter:'滤光片',solar:'太阳光',environment:'环境光合成',pde:'PDE / FF',combined:'综合光谱响应',tx_profile:'Tx 角分布',mapping:'Rx H/V 映射',psf:'PSF 剖面',timing:'采集时序'};
const figureColors={cyan:'#51d8ce',blue:'#75a9f6',amber:'#e9b874'};
let activeFigure='pulse';
const previewFormulas={get mapping(){const d=previewData||data;return d.formulas[d.form_configuration.optics.mapping_mode==='inverted'?'b_rx_mapping_inverted':'b_rx_mapping_legacy'];},get crosstalk(){return data.formulas.b_channel_ratio_db;}};
function showFormula(element,latex){try{katex.render(latex,element,{displayMode:false,throwOnError:true});}catch(error){element.textContent='公式渲染失败：'+error.message+' / '+latex;}}
function scientificLabel(value){return value!==0&&(Math.abs(value)<.001||Math.abs(value)>=1e5)?value.toExponential(2):fmt(value,3);}
function drawSeries(canvas,figure){return PhotonPlots.drawSeries(canvas,figure);}
function drawTiming(figure){
 const left=65,right=660,width=right-left,sx=t=>left+t/figure.period_ns*width;
 let svg=`<svg viewBox="0 0 740 230" role="img" aria-label="发射、接收门和回波时序"><path d="M${left} 185H${right}" stroke="#355366"/><text x="${left}" y="22">单周期时间轴 · ns</text>`;
 const labels=[['发射',60],['接收门',112],['回波',160]];
 for(const [label,y]of labels)svg+=`<text x="12" y="${y+4}">${label}</text><path d="M${left} ${y}H${right}" stroke="#233c4d"/>`;
 svg+=`<path d="M${sx(0)} 42V75" stroke="#51d8ce" stroke-width="3"/><rect x="${sx(figure.gate_start_ns)}" y="99" width="${sx(figure.gate_end_ns)-sx(figure.gate_start_ns)}" height="25" fill="#1b6269" stroke="#52b9b4"/><path d="M${sx(figure.echo_ns)} 142V174" stroke="#e9b874" stroke-width="2"/><text x="${sx(figure.echo_ns)+7}" y="155">${fmt(figure.echo_ns,2)} ns</text>`;
 for(let i=0;i<=4;i++){const t=figure.period_ns*i/4;svg+=`<text x="${sx(t)}" y="207" text-anchor="middle">${fmt(t,0)}</text>`;}
 return svg+'</svg>';
}
function renderParameterFigure(){
 if(!$('parameterVizDetails').open)return;
 const source=previewData||data,figure=source.parameter_figures[activeFigure];
 $('parameterVizTabs').innerHTML=Object.entries(figureLabels).map(([id,label])=>`<button type="button" role="tab" aria-selected="${id===activeFigure}" class="${id===activeFigure?'active':''}" data-figure="${id}">${label}</button>`).join('');
 let body=`<div class="plot-heading"><h3>${esc(figure.title)}</h3><span class="sample-label">当前配置预览</span></div>`;
 if(activeFigure==='timing'){
   body+=`<div class="timing-plot">${drawTiming(figure)}</div><div class="figure-facts"><span>PRF <b>${fmt(figure.prf_hz,0)}</b> Hz</span><span>门宽 <b>${fmt(figure.gate_end_ns-figure.gate_start_ns,0)}</b> ns</span><span>累计 <b>${figure.shots}</b> 发</span><span>时长 <b>${fmt(figure.acquisition_time_ms,3)}</b> ms</span></div>`;
 }else{
   body+=`<div class="parameter-plot-layout ${figure.heatmap?'with-heatmap':''}"><div><canvas id="parameterCurveCanvas" aria-label="${esc(figure.title)}曲线"></canvas><div class="figure-legend">${figure.series.map(s=>`<span><i style="background:${figureColors[s.color]}"></i>${esc(s.label)}</span>`).join('')}</div></div>${figure.heatmap?'<div id="parameterHeatmap" class="heatmap" role="img" aria-label="参数二维分布"></div>':''}</div>`;
   if(figure.facts)body+=`<div class="figure-facts">${figure.facts.map(([key,value,unit])=>`<span>${esc(key)} <b>${scientificLabel(value)}</b> ${esc(unit)}</span>`).join('')}</div>`;
   if(activeFigure==='mapping')body+='<div id="parameterMappingFormula" class="parameter-formula"></div>';
 }
 body+=`<p class="figure-note">${esc(figure.note)}</p>`;$('parameterVizContent').innerHTML=body;
 if(activeFigure!=='timing')drawSeries($('parameterCurveCanvas'),figure);
 if(figure.heatmap==='tx')heatmap('parameterHeatmap',source.optics.tx_energy_fraction,source.optics.tx_h_edges_mrad,source.optics.tx_v_edges_mrad,{percent:true});
 if(figure.heatmap==='psf'){const map=figure.psf_map;heatmap('parameterHeatmap',map.values,map.x_edges_um,map.y_edges_um,{pixel:true,density:true,grid:false,xLabel:'x · μm',yLabel:'y · μm',colorLabel:map.color_label});}
 if(activeFigure==='mapping'&&['gaussian_psf','super_gaussian_psf'].includes(source.form_configuration.optics.rx_model))showFormula($('parameterMappingFormula'),previewFormulas.mapping);
}
function openParameterFigure(id){activeFigure=id;$('parameterVizDetails').open=true;renderParameterFigure();$('parameterVizPanel').scrollIntoView({behavior:'smooth',block:'start'});}
function dbLabel(value){return value===null?'未定义':value==='-inf'?'−∞':fmt(value,1);}
function dbColor(value,lo,hi){if(value===null)return '#253442';if(value==='-inf')return '#08111d';return color(hi===lo?1:(value-lo)/(hi-lo));}
function dbLight(value,lo,hi){return typeof value==='number'&&(hi===lo||(value-lo)/(hi-lo)>.72)?'light-cell':'';}
function selectedAngleIndex(){return selectedV*(data.optics.tx_h_edges_mrad.length-1)+selectedH;}
function renderCrosstalk(){
 const idx=selectedAngleIndex(),matrix=data.crosstalk.matrix_db[idx],auto=data.crosstalk.strongest_channel[idx],selection=$('crosstalkReference').value,ref=selection==='auto'?auto:Number(selection),values=matrix.map(row=>row[ref]);
 $('crosstalkAngle').textContent=`H[${selectedH}] · V[${selectedV}] / H ${fmt(data.optics.angular_h_centers_mrad[idx],3)}, V ${fmt(data.optics.angular_v_centers_mrad[idx],3)} mrad`;
 const finite=values.filter(v=>typeof v==='number'),lo=finite.length?Math.min(...finite):null,hi=finite.length?Math.max(...finite):null;
 const cols=base.optics.channels_h,rows=base.optics.channels_v;
 $('crosstalkSpatial').style.gridTemplateColumns=`repeat(${cols},minmax(0,1fr))`;
 const order=Array.from({length:rows},(_,v)=>rows-1-v).flatMap(v=>Array.from({length:cols},(_,h)=>v*cols+h));
 $('crosstalkSpatial').innerHTML=order.map(ch=>{const value=values[ch];return `<button class="db-cell ${ch===ref?'reference':''} ${dbLight(value,lo,hi)}" style="background:${dbColor(value,lo,hi)}" data-reference-channel="${ch}" aria-label="选择通道 ${ch} 为串扰参考" title="${esc('CH '+ch+' / '+channelName(ch)+'，相对 CH '+ref+'：'+dbLabel(value)+' dB')}"><span>CH ${ch} · ${channelName(ch)}</span><strong>${dbLabel(value)}<small>${value===null?'':' dB'}</small></strong><em>${ch===ref?'参考通道':'点击设为参考'}</em></button>`;}).join('');
 $('crosstalkScale').innerHTML=finite.length?`<span class="db-scale-bar"></span> ${fmt(lo,1)} → ${fmt(hi,1)} dB（有限值自动色域） · −∞ 使用最暗色 · V 向上为正`:'所选参考通道的能量为零，比值未定义。';
 const all=matrix.flat().filter(v=>typeof v==='number'),min=all.length?Math.min(...all):0,max=all.length?Math.max(...all):0;
 $('crosstalkMatrix').innerHTML=`<table class="db-table"><thead><tr><th>观测 ↓ / 参考 →</th>${matrix.map((_,ch)=>`<th class="${ch===ref?'reference-col':''}">CH ${ch}<small>${channelName(ch)}</small></th>`).join('')}</tr></thead><tbody>${matrix.map((row,ch)=>`<tr><th>CH ${ch}<small>${channelName(ch)}</small></th>${row.map((v,j)=>`<td class="${j===ref?'reference-col':''} ${dbLight(v,min,max)}" style="background:${dbColor(v,min,max)}" title="${esc('观测 CH '+ch+' / 参考 CH '+j+'：'+dbLabel(v)+' dB')}">${dbLabel(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
 $('matrixScale').innerHTML=`<span class="db-scale-bar"></span> ${fmt(min,1)} → ${fmt(max,1)} dB（矩阵有限值色域） · 灰色为未定义`;
}
function bindExtraPanels(){
 $('parameterVizDetails').ontoggle=()=>{const open=$('parameterVizDetails').open;document.querySelector('.viz-expand-label').innerHTML=open?'收起 <b>−</b>':'展开查看 <b>＋</b>';renderParameterFigure();};
 $('parameterVizTabs').onclick=e=>{const button=e.target.closest('[data-figure]');if(button){activeFigure=button.dataset.figure;renderParameterFigure();}};
 $('exportParameterFigure').onclick=()=>download('b-fixed-parameter-'+activeFigure+'.json',{configuration_sha256:(previewData||data).provenance.configuration_sha256,figure:(previewData||data).parameter_figures[activeFigure]});
 $('crosstalkReference').innerHTML='<option value="auto">自动 · 当前最强通道</option>'+data.optics.angle_to_channel_fraction[0].map((_,ch)=>`<option value="${ch}">CH ${ch} · ${channelName(ch)}</option>`).join('');
 $('crosstalkReference').onchange=renderCrosstalk;
 $('crosstalkSpatial').onclick=e=>{const b=e.target.closest('[data-reference-channel]');if(b){$('crosstalkReference').value=b.dataset.referenceChannel;renderCrosstalk();}};
 $('backToAngle').onclick=()=>$('mappingPanel').scrollIntoView({behavior:'smooth',block:'start'});
 $('exportCrosstalk').onclick=()=>{const idx=selectedAngleIndex(),ref=$('crosstalkReference').value==='auto'?data.crosstalk.strongest_channel[idx]:Number($('crosstalkReference').value);download('b-angular-channel-ratios-db.json',{h_index:selectedH,v_index:selectedV,h_mrad:data.optics.angular_h_centers_mrad[idx],v_mrad:data.optics.angular_v_centers_mrad[idx],reference_channel:ref,energy_fractions:data.optics.angle_to_channel_fraction[idx],matrix_db:data.crosstalk.matrix_db[idx],definition:data.crosstalk.definition,orientation:data.crosstalk.orientation,zero_reference:'undefined represented by null',zero_numerator:'negative infinity represented by -inf',scope:'conditional channel energy ratios for one angle, not independently excited input-channel transfer matrix',configuration_sha256:data.provenance.configuration_sha256});};
 if(data.formulas){if(['gaussian_psf','super_gaussian_psf'].includes(base.optics.rx_model))showFormula($('invertedMappingFormula'),data.formulas[base.optics.mapping_mode==='inverted'?'b_rx_mapping_inverted':'b_rx_mapping_legacy']);else $('invertedMappingFormula').textContent='当前使用响应矩阵定义映射；构造焦距公式不生效。';showFormula($('crosstalkFormula'),previewFormulas.crosstalk);}
}
