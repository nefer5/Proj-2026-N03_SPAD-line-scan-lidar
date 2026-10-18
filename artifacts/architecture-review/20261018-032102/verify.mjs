import fs from 'node:fs';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {analysis} from './analysis-data.mjs';
const dir='artifacts/architecture-review/20261018-032102';
const read=p=>JSON.parse(fs.readFileSync(`${dir}/${p}`,'utf8').replace(/^\uFEFF/,''));
const snapshot=read('snapshot.json'),build=read('report-build.json');
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
const checks=[];function check(name,ok,detail){checks.push({name,ok,detail});if(!ok)throw Error(name+': '+JSON.stringify(detail))}
check('report hash matches build receipt',sha(fs.readFileSync(`${dir}/index.html`))===build.reportSha256);
check('configuration parsing succeeded',Object.keys(snapshot.configErrors).length===0);
let references=0;
function walk(v){if(!v||typeof v!=='object')return;if(typeof v.path==='string'&&Number.isInteger(v.line)){const f=snapshot.sources[v.path];check(`source reference ${v.path}:${v.line}`,!!f&&v.line>0&&v.line<=f.lines&&(v.end||v.line)>=v.line&&(v.end||v.line)<=f.lines);references++}for(const child of Object.values(v))if(typeof child==='object')walk(child)}
walk(analysis);
const artifacts=['shared-core','job-states','job-sequence','job-result','config-flow'];
for(const artifact of build.diagrams)check(`diagram bytes ${artifact.id}`,sha(fs.readFileSync(`${dir}/${artifact.id}.html`))===artifact.sha256);
const proposalDir='proposal-20261018-041154';
for(const artifact of build.comparisonDiagrams){
 check(`comparison diagram bytes ${artifact.id}`,sha(fs.readFileSync(`${dir}/${proposalDir}/${artifact.id}.html`))===artifact.sha256);
 const spec=read(`${proposalDir}/${artifact.id}.json`);
 if(artifact.id==='current')walk(spec);
 else check('proposed diagram has no invented repository source',!spec.meta.repository&&spec.components.every(n=>!n.sources));
}
check('proposal explicitly unimplemented',build.proposalImplemented===false&&read(`${proposalDir}/proposal-data.json`).implemented===false);
for(const viewport of ['desktop','narrow']){const result=read(`report-browser-${viewport}.json`);check(`browser ${viewport}`,result.success&&result.data.result.ok);check(`all diagrams loaded ${viewport}`,result.data.result.frames.length===artifacts.length&&new Set(result.data.result.frames.map(f=>f.title)).size===artifacts.length)}
for(const viewport of ['desktop','narrow']){const result=read(`${proposalDir}/browser-${viewport}.json`);check(`comparison browser ${viewport}`,result.success&&result.data.result.ok)}
let sourceFiles=0;
for(const [path,snap] of Object.entries(snapshot.sources)){
 if(path.startsWith('WORKTREE/')||!path.startsWith('src/'))continue;
 const basis=snapshot.sources['WORKTREE/'+path]||snap;
 check(`model source unchanged ${path}`,fs.readFileSync(path,'utf8').replace(/\r\n/g,'\n')===basis.text.replace(/\r\n/g,'\n'));sourceFiles++;
}
const currentStatus=execFileSync('git',['status','--porcelain=v1','-uall'],{encoding:'utf8'}).split('\n').filter(Boolean).filter(x=>!x.slice(3).startsWith(dir+'/')).sort();
const priorStatus=snapshot.dirty.map(x=>x.status+' '+x.path).sort();
check('pre-existing work preserved',JSON.stringify(currentStatus)===JSON.stringify(priorStatus),{prior:priorStatus,current:currentStatus});
const result={ok:checks.every(c=>c.ok),basis:snapshot.revision,reportSha256:build.reportSha256,checks:checks.length,sourceReferencesChecked:references,sourceFilesUnchanged:sourceFiles,proposalImplemented:false,archifyDiagrams:7,desktopChecks:read('report-browser-desktop.json').data.result.checks.length,narrowChecks:read('report-browser-narrow.json').data.result.checks.length,proposalDesktopChecks:read(`${proposalDir}/browser-desktop.json`).data.result.checks.length,proposalNarrowChecks:read(`${proposalDir}/browser-narrow.json`).data.result.checks.length,perceptualReview:{inspected:['overview-desktop.png','reuse-desktop.png','overview-narrow.png','core-report-desktop.png','state-captures/job-states.visual-check.1440x900.light.png',`${proposalDir}/current-visual/current.visual-check.1440x900.light.png`,`${proposalDir}/proposed-visual/proposed.visual-check.1440x900.light.png`,`${proposalDir}/report-proposed-desktop.png`,`${proposalDir}/report-proposed-narrow.png`],note:'State diagram retains bridged crossings; exact conditions also appear in a table.'},physicalModelTests:'not run; no model code changed',details:checks};
fs.writeFileSync(`${dir}/verification.json`,JSON.stringify(result,null,2));console.log(JSON.stringify({...result,details:undefined}));
