import fs from 'node:fs';
import path from 'node:path';
import katex from '../../web/vendor/katex/katex.mjs';
let count=0;const failures=[];
function inspect(dir){for(const item of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,item.name);if(item.isDirectory())inspect(p);else if(item.name.endsWith('.md')){
 const text=fs.readFileSync(p,'utf8').replace(/```[\s\S]*?```|~~~[\s\S]*?~~~/g,'').replace(/`[^`\n]*`/g,'');
 for(const m of text.matchAll(/\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$/g)){try{katex.renderToString(m[1]??m[2],{throwOnError:true,displayMode:m[1]!==undefined});count++}catch(e){failures.push({path:p,error:e.message})}}
}}}
inspect('docs');const result={ok:failures.length===0,equations:count,failures,renderer:'project bundled KaTeX; parsing only, not VS Code screenshot acceptance'};fs.writeFileSync('artifacts/docs-reconcile-20261018-173339/math-check.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));process.exitCode=result.ok?0:1;
