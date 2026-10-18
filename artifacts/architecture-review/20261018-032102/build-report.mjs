import fs from 'node:fs';
import crypto from 'node:crypto';
import {analysis} from './analysis-data.mjs';
const dir='artifacts/architecture-review/20261018-032102';
const snapshot=JSON.parse(fs.readFileSync(`${dir}/snapshot.json`,'utf8'));
const names=['shared-core','job-states','job-sequence','job-result','config-flow'];
const receiptPaths={'shared-core':'core-final','job-states':'state-final','job-sequence':'sequence-final','job-result':'','config-flow':'config-final'};
const diagrams={},receipts=[];
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
for(const id of names){
 const html=fs.readFileSync(`${dir}/${id}.html`);
 const receipt=JSON.parse(fs.readFileSync(`${dir}/${receiptPaths[id]?receiptPaths[id]+'/':''}${id}.finalize-summary.json`,'utf8'));
 if(!receipt.ok||receipt.artifact.sha256!==sha(html))throw Error(`Unverified artifact ${id}`);
 const spec=JSON.parse(fs.readFileSync(`${dir}/${id}.json`,'utf8'));
 if(receipt.specification.sha256!==sha(fs.readFileSync(`${dir}/${id}.json`)))throw Error(`Spec changed ${id}`);
 diagrams[id]={spec,base64:html.toString('base64')};receipts.push({id,...receipt});
}
// Tarjan SCC on resolvable project imports; function-local imports remain static facts.
const adj=Object.fromEntries(Object.keys(snapshot.modules).map(m=>[m,[]]));
snapshot.edges.forEach(e=>adj[e.from].push(e.to));
let idx=0;const stack=[],index={},low={},active=new Set(),cycles=[];
function visit(v){index[v]=low[v]=idx++;stack.push(v);active.add(v);for(const w of adj[v]){if(index[w]===undefined){visit(w);low[v]=Math.min(low[v],low[w])}else if(active.has(w))low[v]=Math.min(low[v],index[w])}if(low[v]===index[v]){const group=[];let w;do{w=stack.pop();active.delete(w);group.push(w)}while(w!==v);if(group.length>1)cycles.push(group.sort())}}
Object.keys(adj).forEach(v=>{if(index[v]===undefined)visit(v)});
const proposalDir=`${dir}/proposal-20261018-041154`;
const proposal={summary:JSON.parse(fs.readFileSync(`${proposalDir}/proposal-data.json`,'utf8')),diagrams:{}};
for(const id of ['current','proposed']){
 const html=fs.readFileSync(`${proposalDir}/${id}.html`),spec=JSON.parse(fs.readFileSync(`${proposalDir}/${id}.json`,'utf8'));
 const receipt=JSON.parse(fs.readFileSync(`${proposalDir}/${id}.finalize-summary.json`,'utf8'));
 if(!receipt.ok||receipt.artifact.sha256!==sha(html)||receipt.specification.sha256!==sha(fs.readFileSync(`${proposalDir}/${id}.json`)))throw Error(`Unverified comparison ${id}`);
 proposal.diagrams[id]={spec,receipt,base64:html.toString('base64')};
}
const dataset={snapshot,analysis,diagrams,receipts,proposal,cycles:cycles.sort((a,b)=>b.length-a.length)};
const html=fs.readFileSync(`${dir}/report-template.html`,'utf8').replace('__STYLE__',()=>fs.readFileSync(`${dir}/report.css`,'utf8')).replace('__DATA__',()=>JSON.stringify(dataset).replace(/</g,'\\u003c')).replace('__APP__',()=>fs.readFileSync(`${dir}/report-app.js`,'utf8'));
if(!fs.existsSync(`${proposalDir}/index.before.html`))fs.copyFileSync(`${dir}/index.html`,`${proposalDir}/index.before.html`);
if(!fs.existsSync(`${proposalDir}/report-build.before.json`))fs.copyFileSync(`${dir}/report-build.json`,`${proposalDir}/report-build.before.json`);
fs.writeFileSync(`${dir}/index.html`,html);
fs.writeFileSync(`${dir}/analysis.json`,JSON.stringify(analysis,null,2));
const receipt={kind:'architecture-atlas-build',basis:snapshot.revision,generated:snapshot.generated,proposalUpdated:proposal.summary.updated,proposalImplemented:false,snapshotSha256:sha(fs.readFileSync(`${dir}/snapshot.json`)),reportSha256:sha(html),bytes:Buffer.byteLength(html),diagrams:receipts.map(r=>({id:r.id,sha256:r.artifact.sha256,gates:r.gates})),comparisonDiagrams:Object.entries(proposal.diagrams).map(([id,v])=>({id,sha256:v.receipt.artifact.sha256,gates:v.receipt.gates})),sourceSnapshots:Object.keys(snapshot.sources).length,pythonModules:Object.keys(snapshot.modules).length,staticEdges:snapshot.edges.length,cycles:cycles.length,configErrors:snapshot.configErrors};
fs.writeFileSync(`${dir}/report-build.json`,JSON.stringify(receipt,null,2));
console.log(JSON.stringify(receipt));
