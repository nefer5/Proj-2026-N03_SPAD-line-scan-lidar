/* Display-only SI conversion. Stored configurations always retain canonical cps. */
(function(){
 'use strict';
 const isDcr=path=>path.split('.').at(-1)==='dcr_cps_per_spad';
 const factor=path=>isDcr(path)?1/1000:1;
 globalThis.LidarUnits={
  displayFactor:factor,
  display:(value,path)=>typeof value==='number'?value*factor(path):value,
  canonical:(value,path)=>{if(typeof value!=='number')return value;const result=value/factor(path);if(!Number.isFinite(result)&&isDcr(path))throw Error(path+'需要有限数值');return result;},
  unit:(path,unit)=>isDcr(path)?'kHz':unit
 };
})();

/* Display only; raw configuration and exported arrays keep full precision. */
(function(){
  function number(value,input=false,digits=2){
    if(value===null||value===undefined)return input?'':'待提供 / 未评估';
    if(typeof value!=='number')return String(value);
    if(!Number.isFinite(value))return String(value);
    const a=Math.abs(value);
    if(a!==0&&(a<.01||a>=1e6)){
      const [m,e]=value.toExponential(2).split('e');
      return Number(m)+'e'+Number(e);
    }
    digits=Math.max(0,Math.min(2,digits));
    const rounded=Number(value.toFixed(digits));
    return input?String(rounded):rounded.toLocaleString('zh-CN',{maximumFractionDigits:digits});
  }
  const states=new WeakMap();
  function setInput(el,value){
    const previous=states.get(el),title=previous?.title??el.title??'';
    el.value=number(value,true);
    states.set(el,{raw:value,shown:el.value,edited:false,title});
    el.title=title+(typeof value==='number'?'\n完整数值：'+String(value):'');
  }
  function readInput(el){
    const state=states.get(el);
    if(state&&!state.edited&&el.value===state.shown)return state.raw;
    return el.value.trim()===''?NaN:Number(el.value);
  }
  if(typeof document!=='undefined'){
    for(const event of ['input','change'])document.addEventListener(event,e=>{
      const state=states.get(e.target);if(state)state.edited=true;
    },true);
    document.addEventListener('blur',e=>{
      if(!states.has(e.target))return;
      const value=readInput(e.target);if(typeof value==='number'&&Number.isFinite(value))setInput(e.target,value);
    },true);
  }
  globalThis.LidarNumbers={format:(value,digits=2)=>number(value,false,digits),input:value=>number(value,true),setInput,readInput};
  globalThis.BudgetNumbers={format:value=>number(value),input:value=>number(value,true)};
})();
