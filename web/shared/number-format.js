/* Display only; raw configuration and exported arrays keep full precision. */
(function(){
  function number(value,input=false){
    if(value===null||value===undefined)return input?'':'待提供 / 未评估';
    if(typeof value!=='number')return String(value);
    if(!Number.isFinite(value))return String(value);
    const a=Math.abs(value);
    if(a!==0&&(a<.01||a>=1e6)){
      const [m,e]=value.toExponential(2).split('e');
      return Number(m)+'e'+Number(e);
    }
    const rounded=Number(value.toFixed(2));
    return input?String(rounded):rounded.toLocaleString('zh-CN',{maximumFractionDigits:2});
  }
  globalThis.BudgetNumbers={format:number,input:value=>number(value,true)};
})();
