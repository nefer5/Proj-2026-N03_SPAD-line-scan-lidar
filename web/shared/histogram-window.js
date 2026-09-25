/* Shared A/B/SPAD histogram renderer and display-only observation window. */
(function(){
'use strict';
const fmt=(v,d=2)=>Number(v).toLocaleString('en-US',{maximumFractionDigits:d});
function canvasSetup(canvas){const r=canvas.getBoundingClientRect(),d=window.devicePixelRatio||1;canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d);const c=canvas.getContext('2d');c.scale(d,d);return[c,r.width,r.height];}
function histMaximum(data,ch,range,series){const h=data.histogram,mask=h.time_ns.map((t,i)=>h.edges_ns[i]<range[1]&&h.edges_ns[i+1]>range[0]);let max=series.noise&&data.noise_reference?data.noise_reference.counts_per_bin[ch]:0;for(let i=0;i<mask.length;i++)if(mask[i]){if(series.observed)max=Math.max(max,h.counts[ch][i]);if(series.error&&data.statistics?.upper)max=Math.max(max,data.statistics?.upper[ch][i]);if(series.ideal&&data.references?.[ch])max=Math.max(max,data.references[ch].counts[i]);if(series.noise&&data.statistics?.noise_mean)max=Math.max(max,data.statistics.noise_mean[ch][i]);}if(series.ideal&&data.references?.[ch]){const fine=data.references[ch].high_resolution;fine.time_ns.forEach((t,i)=>{if(t>=range[0]&&t<=range[1])max=Math.max(max,fine.counts_per_nominal_bin[i]);});}return Math.max(1,max)*1.15;}
function drawHistogram(canvas,data,ch,range,ymax,series,overview=false,windowRange=range){
 const [c,w,h]=canvasSetup(canvas),left=overview?43:43,right=15,top=overview?5:22,bottom=overview?16:32,pw=w-left-right,ph=h-top-bottom;
 const sx=t=>left+(t-range[0])/(range[1]-range[0])*pw,sy=y=>top+ph-y/ymax*ph;
 c.clearRect(0,0,w,h);c.font='9px Consolas, monospace';c.lineWidth=1;
 if(!overview){for(let i=0;i<=4;i++){const y=top+ph*i/4;c.strokeStyle='#1b3041';c.beginPath();c.moveTo(left,y);c.lineTo(w-right,y);c.stroke();c.fillStyle='#68899f';c.textAlign='right';c.fillText(fmt(ymax*(1-i/4),1),left-9,y+3);}c.fillStyle='#85a3b6';c.textAlign='left';c.fillText('计数 / 时间分箱',left,11);}
 for(let i=0;i<=4;i++){const t=range[0]+(range[1]-range[0])*i/4;c.fillStyle='#6f90a5';c.textAlign='center';c.fillText(fmt(t,1),sx(t),h-(overview?2:14));}if(!overview){c.textAlign='right';c.fillText('时间 · ns',w-right,h-1);}
 c.save();c.beginPath();c.rect(left,top,pw,ph);c.clip();
 const counts=data.histogram.counts[ch],edges=data.histogram.edges_ns,centers=data.histogram.time_ns;

 if(series.observed||overview){c.fillStyle=overview?'#568fae':'#5e91dc';counts.forEach((v,i)=>{if(edges[i+1]<range[0]||edges[i]>range[1]||!v)return;const x=sx(edges[i]),bw=Math.max(1,sx(edges[i+1])-x);c.fillRect(x+.5,sy(v),Math.max(1,bw-1),top+ph-sy(v));});}
 if(!overview&&series.error&&data.statistics?.upper){c.strokeStyle='#aacbf599';c.lineWidth=1;centers.forEach((t,i)=>{if(t<range[0]||t>range[1])return;const low=data.statistics?.lower[ch][i],high=data.statistics?.upper[ch][i];if(!high)return;const x=sx(t);c.beginPath();c.moveTo(x,sy(low));c.lineTo(x,sy(high));c.moveTo(x-3,sy(low));c.lineTo(x+3,sy(low));c.moveTo(x-3,sy(high));c.lineTo(x+3,sy(high));c.stroke();});}
 function line(times,values,color,dash){c.strokeStyle=color;c.setLineDash(dash);c.lineWidth=1.5;c.beginPath();times.forEach((t,i)=>{const x=sx(t),y=sy(values[i]);if(i===0)c.moveTo(x,y);else c.lineTo(x,y);});c.stroke();c.setLineDash([]);}
 if(!overview&&series.ideal&&data.references?.[ch]){const f=data.references[ch].high_resolution;line(f.time_ns,f.counts_per_nominal_bin,'#57d8ca',[4,3]);c.fillStyle='#65ecda';centers.forEach((t,i)=>{const v=data.references[ch].counts[i];if(t>=range[0]&&t<=range[1]&&v>0){c.beginPath();c.arc(sx(t),sy(v),2.3,0,Math.PI*2);c.fill();}});}
 if(!overview&&series.noise){if(data.noise_reference){const level=data.noise_reference.counts_per_bin[ch];line(range,[level,level],'#dba768',[]);}else if(data.statistics?.noise_mean)line(centers,data.statistics.noise_mean[ch],'#dba768',[]);}
 if(overview){const x=sx(windowRange[0]),width=sx(windowRange[1])-x;c.fillStyle='rgba(255,172,69,.30)';c.fillRect(x,top,width,ph);c.strokeStyle='#ffbc65';c.lineWidth=2;c.strokeRect(x,top,width,ph);for(const edge of [x,x+width]){c.fillStyle='#ffe1a8';c.fillRect(edge-1.5,top,3,ph);}}
 c.restore();
}

function bindOverview(canvas,gate,getRange,onChange){
 let drag=null;
 const value=e=>{const r=canvas.getBoundingClientRect();return gate[0]+(e.clientX-r.left-43)/(r.width-58)*(gate[1]-gate[0]);};
 const valid=v=>Math.max(gate[0],Math.min(gate[1],v));
 canvas.style.touchAction='none';canvas.style.cursor='grab';
 canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;const r=canvas.getBoundingClientRect();if(e.clientX<r.left+43||e.clientX>r.right-15)return;e.preventDefault();const current=getRange(),t=value(e),handle=(gate[1]-gate[0])*7/(r.width-58);let mode=current[1]-current[0]<2*handle?'move':Math.abs(t-current[0])<=handle?'left':Math.abs(t-current[1])<=handle?'right':'move';drag={id:e.pointerId,mode,start:t,range:[...current]};canvas.setPointerCapture(e.pointerId);canvas.style.cursor='grabbing';if(mode==='move'&&(t<current[0]||t>current[1])){const width=current[1]-current[0],lo=Math.max(gate[0],Math.min(gate[1]-width,t-width/2));drag.range=[lo,lo+width];onChange([...drag.range]);}});
 canvas.addEventListener('pointermove',e=>{if(!drag)return;const t=value(e),[lo,hi]=drag.range;let next;if(drag.mode==='move'){const width=hi-lo,start=Math.max(gate[0],Math.min(gate[1]-width,lo+t-drag.start));next=[start,start+width];}else if(drag.mode==='left'){next=[valid(t),hi];}else{next=[lo,valid(t)];}if(next[0]<next[1])onChange(next);});
 const end=e=>{if(drag&&drag.id===e.pointerId){drag=null;canvas.style.cursor='grab';if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);}};
 canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);canvas.addEventListener('lostpointercapture',()=>drag=null);
}
globalThis.PhotonHistogram={draw:drawHistogram,maximum:histMaximum,bindOverview};
})();
