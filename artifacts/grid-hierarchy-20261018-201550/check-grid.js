(async () => {
  const theme=document.documentElement.dataset.auditTheme;
  if(document.documentElement.dataset.theme!==theme)document.querySelector('#themeToggle').click();
  await new Promise(resolve=>setTimeout(resolve,100));
  const canvas=document.querySelector('#histZoom'),before=typeof histogramView==='object'?JSON.stringify(histogramView.result):null;
  const proto=CanvasRenderingContext2D.prototype,original={},paths=new WeakMap(),strokes=[];
  for(const name of ['beginPath','moveTo','lineTo','stroke'])original[name]=proto[name];
  proto.beginPath=function(){paths.set(this,{point:null,segments:[]});return original.beginPath.apply(this,arguments);};
  proto.moveTo=function(x,y){const path=paths.get(this);if(path)path.point=[x,y];return original.moveTo.apply(this,arguments);};
  proto.lineTo=function(x,y){const path=paths.get(this);if(path?.point){path.segments.push([...path.point,x,y]);path.point=[x,y];}return original.lineTo.apply(this,arguments);};
  proto.stroke=function(){if(this.canvas===canvas)strokes.push({color:this.strokeStyle,dash:this.getLineDash(),width:this.lineWidth,segments:paths.get(this)?.segments||[]});return original.stroke.apply(this,arguments);};
  try{window.dispatchEvent(new Event('resize'));await new Promise(resolve=>setTimeout(resolve,120));}
  finally{for(const name of Object.keys(original))proto[name]=original[name];}
  const grid=LidarTheme.plotColor('grid'),axis=LidarTheme.plotColor('axis'),expected=LidarTheme.gridDash();
  const gridStrokes=strokes.filter(s=>s.color===grid),axisStrokes=strokes.filter(s=>s.color===axis);
  const assert=(ok,why)=>{if(!ok)throw Error(why);};
  assert(gridStrokes.length>0,'未绘制网格');
  assert(gridStrokes.every(s=>JSON.stringify(s.dash)===JSON.stringify(expected)),'网格不是统一虚线');
  const hasH=gridStrokes.some(s=>s.segments.some(([x,y,xx,yy])=>y===yy&&x!==xx));
  const hasV=gridStrokes.some(s=>s.segments.some(([x,y,xx,yy])=>x===xx&&y!==yy));
  assert(hasH&&hasV,'横纵网格有缺失');
  assert(axisStrokes.length>0&&axisStrokes.every(s=>s.dash.length===0&&s.width===1.25),'轴线线型/粗细改变');
  assert(before===null||before===JSON.stringify(histogramView.result),'重绘修改了采集结果');
  assert(document.documentElement.scrollWidth<=innerWidth+1,'整页横向溢出');
  return {theme,viewport:[innerWidth,innerHeight],grid,axis,dash:expected,horizontal:hasH,vertical:hasV,axisSolid:true,axisWidth:1.25,resultUnchanged:true};
})();
