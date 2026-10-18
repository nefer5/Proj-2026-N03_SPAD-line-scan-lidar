(async()=>{
 const q=s=>document.querySelector(s),click=s=>{if(!q(s))throw Error('Missing '+s);q(s).click()};
 const checks=[];function check(name,ok,detail){checks.push({name,ok:!!ok,detail});if(!ok)throw Error(name+': '+JSON.stringify(detail))}
 const waitFrame=async id=>{const start=Date.now();while(Date.now()-start<5000){const doc=q('#comparisonFrame').contentDocument;if(doc?.querySelector('svg')&&doc.title===ATLAS.proposal.diagrams[id].spec.meta.title+' Diagram')return doc;await new Promise(r=>setTimeout(r,40))}throw Error('Frame timed out '+id)};
 check('proposal initialized',window.atlasProposalReady===true);check('10 analysis sections',document.querySelectorAll('.page').length===10);
 click('[data-page="proposal"]');check('proposal visible',!q('#page-proposal').hidden);check('proposal model unimplemented',ATLAS.proposal.summary.implemented===false);
 click('[data-compare="current"]');let doc=await waitFrame('current');check('current architecture loaded',doc.title.includes('当前架构'));check('current repository pinned',ATLAS.proposal.diagrams.current.spec.meta.repository.revision===ATLAS.snapshot.revision);check('current source refs',q('#comparisonEvidence [data-srcpath]')!==null);
 q('#comparisonEvidence').parentElement.open=true;click('#comparisonEvidence [data-srcpath]');check('source opens',q('#sourceDialog').open&&q('#sourceMeta').textContent.includes('HEAD'));click('#closeSource');
 click('[data-compare="proposed"]');doc=await waitFrame('proposed');check('proposed architecture loaded',doc.title.includes('建议架构'));check('proposal warning',q('#comparisonStatus').textContent.includes('尚未实施'));check('no invented source references',q('#comparisonEvidence [data-srcpath]')===null&&!ATLAS.proposal.diagrams.proposed.spec.meta.repository);check('core role preserved',q('#comparisonEvidence').textContent.includes('现有器件与读出核心'));
 check('10 change decisions',q('#proposalChanges tbody').rows.length===10);click('[data-change="merge"]');check('6 merge/reuse decisions',q('#proposalChanges tbody').rows.length===6);click('[data-change="keep"]');check('4 independent decisions',q('#proposalChanges tbody').rows.length===4);check('transport remains independent',q('#proposalChanges').textContent.includes('策略独立'));click('[data-change="all"]');
 check('proposed directory exists as text',q('#proposalDirectory').textContent.includes('acquisition/')&&q('#proposalDirectory').textContent.includes('spad/acquisition.py'));check('directory clearly draft',q('#proposalDirectory').textContent.includes('均未创建'));check('7 responsibility mappings',q('#proposalMapping tbody').rows.length===7);check('existing directory distinguished',q('#proposalMapping').textContent.includes('保持现有'));check('4 suggested phases',q('#proposalPhases').children.length===4);
 click('#comparisonReceipt');check('proposal receipt inspectable',q('#sourceDialog').open&&q('#sourceMeta').textContent.includes('不代表重构实施'));click('#closeSource');
 const originalClick=HTMLAnchorElement.prototype.click,originalURL=URL.createObjectURL;let blob;
 try{HTMLAnchorElement.prototype.click=function(){};URL.createObjectURL=b=>{blob=b;return originalURL(b)};
  click('#comparisonDownload');check('proposal standalone export',(await blob.text()).includes('建议架构'));
  click('#downloadAnalysis');const data=JSON.parse(await blob.text());check('proposal exported with unimplemented flag',data.proposal.implemented===false&&data.proposal.changes.length===10);
 }finally{HTMLAnchorElement.prototype.click=originalClick;URL.createObjectURL=originalURL}
 click('#toggleTheme');check('dark mode',document.body.classList.contains('dark'));click('#toggleTheme');
 check('no page horizontal overflow',document.documentElement.scrollWidth<=innerWidth,{scrollWidth:document.documentElement.scrollWidth,innerWidth});
 const remote=performance.getEntriesByType('resource').filter(r=>/^https?:/.test(r.name));check('offline self-contained',remote.length===0);
 q('#comparisonEvidence').parentElement.open=false;
 const result={ok:true,checks,viewport:{width:innerWidth,height:innerHeight},reportBasis:ATLAS.snapshot.revision,proposalImplemented:false,diagramTitles:Object.values(ATLAS.proposal.diagrams).map(d=>d.spec.meta.title)};
 window.atlasProposalTest=result;return result;
})()
