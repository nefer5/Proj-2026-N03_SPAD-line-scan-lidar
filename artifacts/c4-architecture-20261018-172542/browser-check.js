(async()=>{
 const $=s=>document.querySelector(s),click=s=>{if(!$(s))throw Error('Missing '+s);$(s).click()};const checks=[];
 const check=(name,ok,detail)=>{checks.push({name,ok:!!ok,detail});if(!ok)throw Error(name+': '+JSON.stringify(detail))};
 const wait=async id=>{let start=Date.now();while(Date.now()-start<5000){const doc=$('#diagram').contentDocument;if(doc?.querySelector('svg')&&doc.title===DATA.diagrams[id].spec.meta.title)return doc;await new Promise(r=>setTimeout(r,40))}throw Error('C4 iframe timeout '+id)};
 check('initialized',window.c4Ready===true);check('only four pages',document.querySelectorAll('.page').length===4);
 for(const page of ['architecture','data','directory','reuse']){click(`[data-page="${page}"]`);check('page '+page,!$('#page-'+page).hidden);check('no horizontal page overflow '+page,document.documentElement.scrollWidth<=innerWidth,{width:innerWidth,scroll:document.documentElement.scrollWidth})}
 check('current directory has phase1 modules',$('#tree').textContent.includes('domains/')&&$('#tree').textContent.includes('optics/')&&$('#tree').textContent.includes('acquisition/'));
 click('[data-page="directory"]');click('[data-tree="target"]');check('target marked draft',$('#tree').textContent.includes('未实施'));click('[data-tree="current"]');check('current not old snapshot',$('#snapshotLabel').textContent.includes('第一阶段已提取'));
 click('[data-page="data"]');check('all six data destinations',$('#storage tbody').rows.length===6);check('five platform storage differences',$('#drafts tbody').rows.length===5);check('five default inheritance paths',$('#defaults tbody').rows.length===5);check('A storage accurately distinguished',$('#drafts').textContent.includes('不能等同完整持久配置草稿'));
 check('job request path',$('#storage').textContent.includes('request.json'));check('budget not a job',$('#page-data').textContent.includes('不自动生成采集作业'));
 click('#defaultSources [data-source]');check('source opens with pinned bytes',$('#modal').open&&$('#modalMeta').textContent.includes('SHA-256'));check('source highlight',$('#modalCode .hl')!==null);click('#close');
 click('#expert');check('C4 source prompt confirmed',$('#modalCode').textContent.includes('C1–C3')&&$('#modalCode').textContent.includes('C3 组件'));check('host loading not overclaimed',$('#modalMeta').textContent.includes('未验证宿主'));click('#close');
 click('[data-page="reuse"]');check('seven reuse responsibilities',$('#reuseMatrix tbody').rows.length===7);check('future work marked',$('#decisions').textContent.includes('后续建议'));
 click('[data-page="architecture"]');const levels=[];
 for(const id of ['c1','c2','c3']){click(`[data-level="${id}"]`);const doc=await wait(id);check('C4 level '+id,doc.title===DATA.diagrams[id].spec.meta.title);check('source index '+id,$('#diagramEvidence [data-source]')!==null);levels.push({id,title:doc.title})}
 click('#receipt');check('diagram receipts accessible',$('#modal').open&&$('#modalCode').textContent.includes('browser-check'));click('#close');
 const oldClick=HTMLAnchorElement.prototype.click,oldURL=URL.createObjectURL;let blob;
 try{HTMLAnchorElement.prototype.click=function(){};URL.createObjectURL=b=>{blob=b;return oldURL(b)};click('#exportSummary');const json=JSON.parse(await blob.text());check('summary export',Object.keys(json.levels).length===3&&json.content.storage.length===6);click('#exportDiagram');check('independent diagram export',(await blob.text()).includes('C3 后端组件'))}finally{HTMLAnchorElement.prototype.click=oldClick;URL.createObjectURL=oldURL}
 click('#theme');check('dark theme',document.body.classList.contains('dark'));click('#theme');check('light theme',!document.body.classList.contains('dark'));
 const remote=performance.getEntriesByType('resource').filter(x=>/^https?:/.test(x.name));check('no remote resources',remote.length===0);
 click('[data-level="c2"]');await wait('c2');return {ok:true,checks,levels,viewport:{width:innerWidth,height:innerHeight},generated:DATA.snapshot.generated};
})()
