(() => {
 const assert=(ok,message)=>{if(!ok)throw new Error(message);};
 assert(histogramView,'result ready');
 const baseline=JSON.stringify(lastResult),snapshot=histogramView.result;
 const requests=[];const originalFetch=window.fetch;window.fetch=(...args)=>{requests.push(String(args[0]));return originalFetch(...args);};
 const apply=(lo,hi)=>{document.getElementById('histWindowStart').value=lo;document.getElementById('histWindowEnd').value=hi;document.getElementById('histWindowApply').click();};
 apply('600.125','700.875');assert(histogramView.range[0]===600.125&&histogramView.range[1]===700.875,'precise inputs');
 const invalid=[];for(const pair of [['','700'],['701','700'],['-1','700'],['600','99999']]){apply(...pair);assert(!document.getElementById('histWindowError').classList.contains('hidden'),'invalid range error');assert(histogramView.range[0]===600.125&&histogramView.range[1]===700.875,'invalid input changed range');invalid.push(pair);}
 document.getElementById('histWindowFull').click();assert(JSON.stringify(histogramView.range)===JSON.stringify(histogramView.gate),'full gate');
 document.getElementById('histWindowPeak').click();assert(JSON.stringify(histogramView.range)===JSON.stringify(histogramView.peak),'peak reset');
 apply('500','900');render(lastResult);assert(histogramView.range[0]===500&&histogramView.range[1]===900,'rerender reset window');
 document.querySelector('#themeToggle').click();assert(histogramView.range[0]===500&&histogramView.range[1]===900,'theme reset window');
 document.querySelector('#themeToggle').click();
 assert(lastResult===snapshot&&JSON.stringify(lastResult)===baseline,'data mutated');assert(requests.length===0,'display interaction requested simulation');
 assert(JSON.parse(document.getElementById('histZoom').dataset.yTicks).every(Number.isInteger),'integer ticks');
 globalThis.aAudit={baseline,requests,initialRange:[...histogramView.range],checks:{precise:true,invalid,full:true,peak:true,rerender:true,theme:true,dataUnchanged:true,noRequests:true},fingerprint:lastResult.provenance};
 document.getElementById('histFull').scrollIntoView({block:'center'});const r=document.getElementById('histFull').getBoundingClientRect();
 return JSON.stringify({mode:document.body.dataset.mode,checks:aAudit.checks,drag:{x:r.left+43+(700-histogramView.gate[0])/(histogramView.gate[1]-histogramView.gate[0])*(r.width-58),y:r.top+30},heights:['histZoom','histFull'].map(id=>getComputedStyle(document.getElementById(id)).height)});
})()
