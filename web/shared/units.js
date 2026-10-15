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
