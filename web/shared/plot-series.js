/* Shared numerical-series renderer; accepts Python-computed values only. */
(function(){
'use strict';
const figureColors={cyan:'#51d8ce',blue:'#75a9f6',amber:'#e9b874'};
const fmt=(v,d=3)=>Number(v).toLocaleString('en-US',{maximumFractionDigits:d});
function scientificLabel(v){return v!==0&&(Math.abs(v)<.001||Math.abs(v)>=1e5)?v.toExponential(2):fmt(v);}
function canvasSetup(canvas){const r=canvas.getBoundingClientRect(),d=window.devicePixelRatio||1;canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d);const c=canvas.getContext('2d');c.scale(d,d);return[c,r.width,r.height];}
function drawSeries(canvas,figure){
 const [c,w,h]=canvasSetup(canvas),left=65,right=20,top=31,bottom=44,pw=w-left-right,ph=h-top-bottom;
 let xmin=Infinity,xmax=-Infinity,ymin=0,ymax=0;
 for(const line of figure.series){for(const x of line.x){xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);}for(const y of line.y){ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}}
 if(!Number.isFinite(xmin)||!Number.isFinite(xmax)){c.clearRect(0,0,w,h);c.fillStyle='#9ab3c5';c.font='12px sans-serif';c.fillText('当前配置没有可显示的有效响应点。',20,40);return;}if(xmin===xmax)xmax=xmin+1;if(ymin===ymax)ymax=ymin+1;
 const span=ymax-ymin;ymax+=span*.08;if(ymin<0)ymin-=span*.08;
 const sx=x=>left+(x-xmin)/(xmax-xmin)*pw,sy=y=>top+(ymax-y)/(ymax-ymin)*ph;
 c.clearRect(0,0,w,h);c.font='10px Consolas, monospace';c.lineWidth=1;
 for(let i=0;i<=4;i++){const y=ymin+(ymax-ymin)*i/4;c.strokeStyle='#233b4d';c.beginPath();c.moveTo(left,sy(y));c.lineTo(w-right,sy(y));c.stroke();c.fillStyle='#86a7bc';c.textAlign='right';c.fillText(scientificLabel(y),left-9,sy(y)+3);const x=xmin+(xmax-xmin)*i/4;c.textAlign='center';c.fillText(scientificLabel(x),sx(x),h-25);}
 c.fillStyle='#abc2d1';c.textAlign='left';c.fillText(figure.y_label,left,15);c.textAlign='right';c.fillText(figure.x_label,w-right,h-5);
 c.save();c.beginPath();c.rect(left,top,pw,ph);c.clip();
 if(figure.marker_x!==undefined&&figure.marker_x>=xmin&&figure.marker_x<=xmax){c.strokeStyle='#b38c5d';c.setLineDash([3,4]);c.beginPath();c.moveTo(sx(figure.marker_x),top);c.lineTo(sx(figure.marker_x),top+ph);c.stroke();c.setLineDash([]);c.fillStyle='#d8b785';c.textAlign='right';c.fillText(`${figure.marker_x} nm`,sx(figure.marker_x)-5,top+12);}
 for(const line of figure.series){c.strokeStyle=figureColors[line.color];c.fillStyle=figureColors[line.color];c.lineWidth=1.5;c.beginPath();line.x.forEach((x,i)=>{if(i)c.lineTo(sx(x),sy(line.y[i]));else c.moveTo(sx(x),sy(line.y[i]));});c.stroke();if(line.points_x)line.points_x.forEach((x,i)=>{c.beginPath();c.arc(sx(x),sy(line.points_y[i]),2.3,0,2*Math.PI);c.fill();});}
 c.restore();
}
globalThis.PhotonPlots={drawSeries,canvasSetup};
})();
