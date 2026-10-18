(async()=>{
 const checks=[];const check=(name,ok,detail)=>{checks.push({name,ok:!!ok,detail});if(!ok)throw Error(name+' '+JSON.stringify(detail))};
 const el=s=>document.querySelector(s),click=s=>{const n=el(s);if(!n)throw Error('Missing '+s);n.click()},input=(s,v)=>{el(s).value=v;el(s).dispatchEvent(new Event('input',{bubbles:true}))};
 const tick=()=>new Promise(r=>setTimeout(r,40));
 check('application initialized',window.atlasReady===true);
 for(const page of ['overview','reuse','handoffs','diagrams','parameters','directory','dependencies','decisions','proposal','evidence']){
  click(`[data-page="${page}"]`);await tick();check('section '+page,!el('#page-'+page).hidden&&[...document.querySelectorAll('.page')].filter(n=>!n.hidden).length===1);
  check('desktop page width '+page,document.documentElement.scrollWidth<=innerWidth,{scrollWidth:document.documentElement.scrollWidth,innerWidth});
 }
 click('[data-page="reuse"]');input('#reuseSearch','量化');check('reuse search',el('#reuseMatrix tbody').rows.length===1);input('#reuseSearch','');
 click('[data-platform="a"]');check('platform column filter',el('#reuseMatrix thead tr').cells.length===5);click('#allPlatforms');check('platform reset',el('#reuseMatrix thead tr').cells.length===6);
 el('#reuseKind').value='separate';el('#reuseKind').dispatchEvent(new Event('change'));check('implementation filter',el('#reuseMatrix tbody').rows.length>0&&el('#reuseMatrix tbody').rows.length<13);el('#reuseKind').value='';el('#reuseKind').dispatchEvent(new Event('change'));
 click('#reuseMatrix [data-srcpath]');await tick();check('source modal',el('#sourceDialog').open);check('source line highlight',el('#sourceCode .hl')!==null);check('source provenance',el('#sourceMeta').textContent.includes('HEAD'));click('#closeSource');
 click('[data-page="parameters"]');input('#paramSearch','readout_mean_trials');check('parameter search',el('#paramValues tbody').rows.length===1);check('actual A default',el('#paramValues tbody').textContent.includes('8'));input('#paramSearch','');
 click('[data-config="columns"]');check('canonical config view',el('#sourceDialog').open&&el('#sourceCode').textContent.includes('system_targets'));click('#closeSource');input('#algoSearch','b_initial_condition');check('algorithm source',el('#algoValues').textContent.includes('fully_recovered'));input('#algoSearch','');
 click('[data-page="directory"]');input('#fileSearch','scripts/');check('script directory coverage',el('#fileResults').textContent.includes('render-photon-budget-doc.py'));input('#fileSearch','spad/acquisition.py');check('file search',el('#fileResults [data-srcpath]')!==null);click('#fileResults [data-srcpath]');check('file source view',el('#sourceDialog').open&&el('#sourceTitle').textContent.includes('acquisition'));click('#closeSource');input('#fileSearch','');
 click('[data-page="dependencies"]');el('#moduleSelect').value='spad_lidar.spad.acquisition';el('#moduleSelect').dispatchEvent(new Event('change'));check('dependency module selection',el('#moduleHeader').textContent.includes('spad_lidar.spad.acquisition'));check('incoming edges',el('#incomingDeps [data-mod]')!==null);click('#incomingDeps [data-mod]');check('dependency navigation',el('#moduleHeader').textContent!==''&&!el('#page-dependencies').hidden);
 click('[data-page="diagrams"]');
 const frames=[];
 for(const id of ['shared-core','job-states','job-sequence','job-result','config-flow']){
  click(`[data-diagram="${id}"]`);
  const expected=ATLAS.diagrams[id].spec.meta.title+' Diagram';
  const ready=await new Promise(resolve=>{const start=Date.now();const poll=()=>{const doc=el('#diagramFrame').contentDocument;if(doc?.querySelector('svg')&&doc.title===expected)resolve(true);else if(Date.now()-start>5000)resolve(false);else setTimeout(poll,50)};poll()});
  check('embedded diagram '+id,ready);check('explicit source evidence '+id,el('#diagramEvidence').textContent.includes('源码依据：'));frames.push({id,title:el('#diagramFrame').contentDocument.title});
 }
 const originalClick=HTMLAnchorElement.prototype.click,originalURL=URL.createObjectURL;let exported;
 try{
  HTMLAnchorElement.prototype.click=function(){};URL.createObjectURL=blob=>{exported=blob;return originalURL(blob)};
  click('#downloadAnalysis');const json=JSON.parse(await exported.text());check('analysis JSON export',json.revision===ATLAS.snapshot.revision&&json.configs.columns.values.system_targets!==undefined);
  click('#downloadDiagram');const text=await exported.text();check('standalone diagram export',text.includes('参数数据流')&&text.includes('<svg'));
 }finally{HTMLAnchorElement.prototype.click=originalClick;URL.createObjectURL=originalURL}
 click('#toggleTheme');check('dark theme',document.body.classList.contains('dark'));click('#toggleTheme');check('light theme',!document.body.classList.contains('dark'));
 const remote=performance.getEntriesByType('resource').filter(e=>/^https?:/.test(e.name));check('offline resources',remote.length===0,remote.map(x=>x.name));
 click('[data-page="overview"]');
 window.atlasBrowserResult={ok:checks.every(c=>c.ok),checks,frames,viewport:{width:innerWidth,height:innerHeight},url:location.href};
 return window.atlasBrowserResult;
})()
