import fs from 'node:fs';
import crypto from 'node:crypto';
import {content} from './content.mjs';
const dir='artifacts/c4-architecture-20261018-172542';
const snapshot=JSON.parse(fs.readFileSync(`${dir}/snapshot.json`,'utf8'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const diagrams={};
for(const id of ['c1','c2','c3']){
 const receiptFolder={c1:'actor-final',c2:'storage-final',c3:'component-final'}[id];
 const spec=JSON.parse(fs.readFileSync(`${dir}/${id}.json`)),html=fs.readFileSync(`${dir}/${id}.html`),receipt=JSON.parse(fs.readFileSync(`${dir}/${receiptFolder}/${id}.finalize-summary.json`));
 if(!receipt.ok||sha(html)!==receipt.artifact.sha256||sha(fs.readFileSync(`${dir}/${id}.json`))!==receipt.specification.sha256)throw Error('Unverified '+id);
 diagrams[id]={spec,receipt,html:html.toString('base64')};
}
const data={snapshot,content,diagrams};
const html=fs.readFileSync(`${dir}/index.template.html`,'utf8').replace('__CSS__',()=>fs.readFileSync(`${dir}/style.css`,'utf8')).replace('__DATA__',()=>JSON.stringify(data).replace(/</g,'\\u003c')).replace('__APP__',()=>fs.readFileSync(`${dir}/app.js`,'utf8'));
fs.writeFileSync(`${dir}/index.html`,html);
const result={reportSha256:sha(html),bytes:Buffer.byteLength(html),snapshotSha256:sha(fs.readFileSync(`${dir}/snapshot.json`)),generated:snapshot.generated,productHead:snapshot.productHead,proofRevision:snapshot.proofRevision,graphs:Object.fromEntries(Object.entries(diagrams).map(([k,v])=>[k,{sha256:v.receipt.artifact.sha256,gates:v.receipt.gates}])),expertSource:{path:snapshot.expert.path,sha256:snapshot.expert.sha256,C4SectionConfirmed:true,hostReloadVerified:false},modelChanges:false,configurationMigration:false};
fs.writeFileSync(`${dir}/build-receipt.json`,JSON.stringify(result,null,2));console.log(JSON.stringify(result));
