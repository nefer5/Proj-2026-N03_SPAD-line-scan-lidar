const S=ATLAS.snapshot,A=ATLAS.analysis,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const source=(r)=>`<button class="source" data-srcpath="${h(r.path)}" data-line="${r.line||1}" data-end="${r.end||r.line||1}" title="打开内嵌源码快照 ${h(r.path)}">${h(r.path.replace('src/spad_lidar/',''))} · ${h(r.label||'')} · L${r.line||1}${r.end&&r.end!==r.line?'–'+r.end:''}</button>`;
const evidence=refs=>`<div class="evidence">${refs.map(source).join('')}</div>`;
const names={shared:'共享同一核心',adapter:'专用适配',separate:'独立实现',bypass:'绕过 / 预算',none:'不适用'};
const badge=(kind,label)=>`<span class="badge ${kind}">${h(label||names[kind])}</span>`;
const overview=()=>{
 $('#heroMetrics').innerHTML=[['5','主要研究入口'],[Object.keys(S.modules).length,'Python 模块'],[S.edges.length,'静态导入关系'],['7','Archify 分析图（含对比）']].map(([v,t])=>`<div class="metric"><strong>${v}</strong><small>${t}</small></div>`).join('');
 $('#platformCards').innerHTML=A.platforms.map(p=>`<article class="panel"><div class="card-head"><div class="platform-mark">${p.short}</div><div><h3>${p.title}</h3><code>${h(p.route)}</code></div></div><p class="small muted">${h(p.input)}</p><dl class="kv"><dt>执行</dt><dd>${h(p.runtime)}</dd><dt>输出</dt><dd>${h(p.output)}</dd><dt>状态边界</dt><dd>${h(p.state)}</dd></dl><div class="chain">${p.chain.map(h).join(' → ')}</div>${evidence([p.entry])}<div style="margin-top:12px"><button data-focusplatform="${p.id}">检查 ${p.short} 的复用关系 →</button></div></article>`).join('');
 $('#contracts').innerHTML=A.contracts.map(c=>`<article class="contract"><strong><code>${h(c.name)}</code></strong><p>${h(c.meaning)}</p>${source(c.source)}</article>`).join('');
 $('#revision').textContent=S.revision.slice(0,12)+' · '+S.version;
 $('#snapshotTime').textContent=S.generated.slice(0,19).replace('T',' ')+' SGT';
 $('#scopeNote').innerHTML=`模型基线：<code>${S.revision}</code>。${S.dirty.filter(x=>x.status.trim()==='M').length} 个已跟踪文件有未提交修改；主要涉及启动器、API 和文档。分析图区分 HEAD 与 WORKTREE；下方源码浏览默认查看固定提交，不将未提交修改算进该提交。`;
};
let selectedPlatforms=new Set(A.platforms.map(p=>p.id));
function renderMatrix(){
 const cols=A.platforms.map((p,i)=>({p,i})).filter(({p})=>selectedPlatforms.has(p.id));
 const q=$('#reuseSearch').value.trim().toLowerCase(),filter=$('#reuseKind').value;
 const rows=A.rows.filter(r=>(!q||JSON.stringify(r).toLowerCase().includes(q))&&(!filter||r.cells.some((c,i)=>cols.some(x=>x.i===i)&&c.kind===filter)));
 $('#reuseMatrix').innerHTML=`<table class="matrix"><thead><tr><th>能力 / 实现层</th>${cols.map(({p})=>`<th>${p.short} · ${p.title}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${h(r.title)}</strong><div class="muted small">${h(r.group)}</div></td>${cols.map(({i})=>{const c=r.cells[i];return `<td>${badge(c.kind)}<p>${h(c.text)}</p>${c.sources.length?evidence(c.sources):''}</td>`}).join('')}</tr>`).join('')}</tbody></table>`;
 $('#reuseCount').textContent=`${cols.length} 个平台 × ${rows.length} 项能力。绿色表示已确认共用实现；蓝色为共同契约下的适配；橙色是分开的实现，不据此断定重复代码。`;
 $$('#platformFilters button').forEach(b=>{b.classList.toggle('active',selectedPlatforms.has(b.dataset.platform));b.setAttribute('aria-pressed',selectedPlatforms.has(b.dataset.platform))});
}
$('#platformFilters').innerHTML=A.platforms.map(p=>`<button class="active" data-platform="${p.id}" aria-pressed="true">${p.short}</button>`).join('')+'<button id="allPlatforms">显示全部</button>';
$('#platformFilters').onclick=e=>{const b=e.target.closest('[data-platform]');if(b){const id=b.dataset.platform;if(selectedPlatforms.has(id)&&selectedPlatforms.size>1)selectedPlatforms.delete(id);else selectedPlatforms.add(id);renderMatrix()}else if(e.target.closest('#allPlatforms')){selectedPlatforms=new Set(A.platforms.map(p=>p.id));renderMatrix()}};
$('#reuseSearch').oninput=renderMatrix;$('#reuseKind').onchange=renderMatrix;

$('#transfers').innerHTML=A.transfers.map(t=>`<article class="panel transfer"><div class="arrowbox">${h(t.from)}<div>↓</div>${h(t.to)}</div><div><span class="badge">${h(t.status)}</span><h3 style="margin-top:10px">转移的内容与保留的边界</h3><p>${h(t.detail)}</p><div class="note soft small">${h(t.keep)}</div>${evidence(t.sources)}</div></article>`).join('');

$('#paramMapping').innerHTML=A.parameterGroups.map(g=>`<details class="panel"><summary style="cursor:pointer;font-weight:600">${h(g.name)} <span class="badge adapter">语义映射</span></summary><div class="scrolltable" style="margin:15px 0"><table><thead><tr>${A.platforms.map(p=>`<th>${p.short}</th>`).join('')}</tr></thead><tbody><tr>${g.paths.map(p=>`<td class="parampath">${h(p)}</td>`).join('')}</tr></tbody></table></div><p>${h(g.meaning)}</p><div class="note small">整合判断：${h(g.decision)}</div>${evidence(g.sources)}</details>`).join('');

function flatten(obj,prefix='',rows=[]){for(const [key,value]of Object.entries(obj)){const path=prefix?prefix+'.'+key:key;if(value&&typeof value==='object'&&!Array.isArray(value))flatten(value,path,rows);else rows.push({path,key,value})}return rows}
const fields=A.platforms.flatMap(p=>flatten(S.configs[p.id].values).map(f=>({...f,platform:p.short,id:p.id})));
function helpField(f){const x=S.help.experiments?.[f.path]||S.help[f.key];return x&&typeof x==='object'?x:{}}
function getType(id,path){let schema=S.configs[id].schema;const root=schema;for(const key of path.split('.')){if(schema?.$ref)schema=root.$defs[schema.$ref.split('/').pop()];schema=schema?.properties?.[key]}if(schema?.$ref)schema=root.$defs[schema.$ref.split('/').pop()];return schema?.enum?'enum':schema?.type||schema?.anyOf?.map(x=>x.type||x.$ref?.split('/').pop()).join(' | ')||'按类型定义'}
function renderParams(){
 const q=$('#paramSearch').value.toLowerCase().trim(),kind=$('#paramPlatform').value;
 const rows=fields.filter(f=>(!kind||kind===f.id)&&(!q||[f.path,f.platform,helpField(f).label||''].join(' ').toLowerCase().includes(q)));
 $('#paramCount').textContent=`${rows.length} / ${fields.length} 个解析后的参数叶节点；数组为一个字段。值来自本次 read-only 配置解析，不代表任何正在运行的任务。`;
 $('#paramValues').innerHTML=`<table><thead><tr><th>平台</th><th>完整参数路径</th><th>类型 / 单位</th><th>快照默认值</th><th>帮助说明</th></tr></thead><tbody>${rows.map(f=>{const help=helpField(f),raw=JSON.stringify(f.value);return `<tr><td>${f.platform}</td><td class="parampath">${h(f.path)}</td><td>${h(getType(f.id,f.path))}${help.unit?'<br><b>'+h(help.unit)+'</b>':''}</td><td class="paramval"><code>${h(raw.length>100?raw.slice(0,100)+'…（完整值见配置）':raw)}</code><br><button class="source" data-config="${f.id}">完整规范配置</button></td><td class="small">${h(help.description||help.label||'按类型与规范配置核对；不推断同名语义。')}</td></tr>`}).join('')}</tbody></table>`;
}
$('#paramPlatform').innerHTML='<option value="">全部平台</option>'+A.platforms.map(p=>`<option value="${p.id}">${p.short} · ${p.type}</option>`).join('');
$('#paramSearch').oninput=renderParams;$('#paramPlatform').onchange=renderParams;
$('#configTypes').innerHTML=A.platforms.map(p=>`<button data-config="${p.id}">${p.short} · ${S.configs[p.id].type}</button>`).join('');
function renderAlgorithms(){const q=$('#algoSearch').value.toLowerCase();const o=Object.fromEntries(Object.entries(S.algorithms).filter(([k,v])=>(k+' '+JSON.stringify(v)).toLowerCase().includes(q)));$('#algoValues').textContent=JSON.stringify(o,null,2);$('#algoCount').textContent=`${Object.keys(o).length} 项算法设置（含策略、容差、采样、限额和布局参数）；与工况默认值分开。`}
$('#algoSearch').oninput=renderAlgorithms;

function makeTree(){const root={children:{}};for(const entry of S.inventory){let cur=root;for(const part of entry.path.split('/')){cur.children[part]??={children:{}};cur=cur.children[part]}cur.file=entry}return root}
const tree=makeTree();
function treeHTML(node,prefix=''){return Object.entries(node.children).sort(([a,x],[b,y])=>Boolean(x.file)-Boolean(y.file)||a.localeCompare(b)).map(([name,child])=>{const path=prefix?prefix+'/'+name:name;
 if(!child.file){if(path==='web/vendor')return `<details><summary>${h(name)}/ <span class="role">${h(A.roles[path])} · ${S.inventory.filter(x=>x.path.startsWith(path+'/')).length} 文件</span></summary><p class="small muted">第三方库文件省略逐项源码；不计入 115 个 Python 模块。</p></details>`;return `<details ${['src','src/spad_lidar','config'].includes(path)?'open':''}><summary><strong>${h(name)}/</strong>${A.roles[path]?`<span class="role">${h(A.roles[path])}</span>`:''}</summary>${treeHTML(child,path)}</details>`}
 const known=S.sources[path],module=Object.values(S.modules).find(m=>m.path===path);
 return `<div class="treefile">${known?`<button data-srcpath="${h(path)}" data-line="1" data-end="1">${h(name)}</button>`:`<span>${h(name)}</span>`}<small>${Math.round(child.file.bytes/1024*10)/10} KB${module?' · '+module.symbols.length+' 定义':''}${!known?' · 仅目录':''}</small></div>`}).join('')}
$('#directoryTree').innerHTML=treeHTML(tree);
function renderFileSearch(){const q=$('#fileSearch').value.toLowerCase().trim();$('#directoryTree').hidden=!!q;$('#fileResults').hidden=!q;if(!q)return;const matches=S.inventory.filter(f=>f.path.toLowerCase().includes(q));$('#fileResults').innerHTML=`<div class="countbar">${matches.length} 个文件</div>`+matches.map(f=>`<div class="searchrow">${S.sources[f.path]?source({path:f.path,line:1,label:f.path}):`<span>${h(f.path)}</span>`}<small>${f.bytes} bytes</small></div>`).join('')}
$('#fileSearch').oninput=renderFileSearch;
$('#expandTree').onclick=()=>{$$('#directoryTree details').forEach(d=>d.open=true)};$('#collapseTree').onclick=()=>{$$('#directoryTree details').forEach(d=>d.open=false)};

const pathsByModule=Object.fromEntries(Object.entries(S.modules).map(([k,v])=>[k,v.path]));
const moduleNames=Object.keys(S.modules).sort();
$('#moduleSelect').innerHTML=moduleNames.map(m=>`<option value="${h(m)}">${h(m)}</option>`).join('');
let currentModule='spad_lidar.experiments.columns';
function renderDependencies(){
 const mod=S.modules[currentModule];$('#moduleSelect').value=currentModule;
 const incoming=S.edges.filter(e=>e.to===currentModule),outgoing=S.edges.filter(e=>e.from===currentModule);
 const unique=(arr,key)=>[...new Set(arr.map(e=>e[key]))];
 $('#moduleHeader').innerHTML=`<h3 class="mono">${h(currentModule)}</h3><div class="depstats"><span>导入它：<b>${unique(incoming,'from').length}</b> 个模块</span><span>它导入：<b>${unique(outgoing,'to').length}</b> 个模块</span><span>定义：<b>${mod.symbols.length}</b></span></div>${source({path:mod.path,line:1,label:'完整源码'})}`;
 function deps(rows,key){return rows.length?unique(rows,key).map(name=>{const refs=rows.filter(e=>e[key]===name);return `<button class="depitem" data-mod="${h(name)}">${h(name.replace('spad_lidar.',''))}<span class="muted"> · ${refs.map(e=>'L'+e.line).join(', ')}</span></button>`}).join(''):'<p class="small muted">本次静态图中没有可解析的项目内导入。</p>'}
 $('#incomingDeps').innerHTML=deps(incoming,'from');$('#outgoingDeps').innerHTML=deps(outgoing,'to');
 $('#moduleSymbols').innerHTML=mod.symbols.map(s=>source({path:mod.path,line:s.line,end:s.end,label:s.kind+' '+s.name})).join('');
 $('#moduleCalls').textContent=mod.calls.map(c=>`L${c.line}  ${c.name}(…)`).join('\n');
}
$('#moduleSelect').onchange=e=>{currentModule=e.target.value;renderDependencies()};
$('#moduleSearch').oninput=e=>{const q=e.target.value.toLowerCase();$('#moduleSelect').innerHTML=moduleNames.filter(m=>m.toLowerCase().includes(q)).map(m=>`<option value="${h(m)}">${h(m)}</option>`).join('');if($('#moduleSelect').options.length){currentModule=$('#moduleSelect').value;renderDependencies()}};
$('#cycles').innerHTML=ATLAS.cycles.map(c=>`<div class="scc"><b>${c.length} 个模块的静态互达组</b><div class="evidence">${c.map(m=>`<button class="depitem" data-mod="${h(m)}">${h(m.replace('spad_lidar.',''))}</button>`).join('')}</div></div>`).join('')||'<p class="muted">未发现静态互达组。</p>';

$('#proposals').innerHTML=A.proposals.map((p,i)=>`<article class="decision"><div class="decision-top"><div><span class="label">审查点 ${String(i+1).padStart(2,'0')} · ${h(p.scope)}</span><h3>${h(p.title)}</h3></div>${badge('adapter',p.tag)}</div><p><b>已核对现状：</b>${h(p.fact)}</p><p><b>建议：</b>${h(p.proposal)}</p><p><b>合并前的风险：</b>${h(p.risk)}</p><div class="checkline"><b>需保留的验证：</b>${h(p.check)}</div>${evidence(p.sources)}</article>`).join('');

const diagramNames={'shared-core':'共享核心与适配','job-states':'任务状态图','job-sequence':'提交与执行时序','job-result':'轮询与读回时序','config-flow':'参数数据流'};
let currentDiagram='shared-core';
$('#diagramButtons').innerHTML=Object.entries(diagramNames).map(([id,label])=>`<button data-diagram="${id}">${label}</button>`).join('');
function selectDiagram(id){currentDiagram=id;const doc=ATLAS.diagrams[id];if(!doc)throw Error('Missing embedded diagram '+id);$('#diagramFrame').srcdoc=new TextDecoder().decode(Uint8Array.from(atob(doc.base64),c=>c.charCodeAt(0)));$('#diagramTitle').textContent=diagramNames[id];$$('[data-diagram]').forEach(b=>b.classList.toggle('active',b.dataset.diagram===id));const spec=doc.spec;const nodes=spec.components||spec.states||spec.participants||spec.nodes;$('#diagramEvidence').innerHTML=nodes.map(n=>`<div class="evidence-item"><strong>${h(n.label)}</strong><span class="muted">源码依据：${n.sources?.length||0} 处</span>${evidence((n.sources||[]).map(r=>({...r,end:r.end_line})))}</div>`).join('');$('#diagramStatus').textContent='Archify：结构 / 源码引用 / 交付 / 真实浏览器检查均通过。'+(id==='job-states'?' 状态图包含 3 处已桥接的交叉线，可结合下方转移表核对。':'');$('#stateTable').hidden=id!=='job-states'}
$('#diagramButtons').onclick=e=>{const b=e.target.closest('[data-diagram]');if(b)selectDiagram(b.dataset.diagram)};
$('#diagramFull').onclick=()=>$('#diagramFrame').requestFullscreen().catch(()=>{});
$('#downloadDiagram').onclick=()=>download(currentDiagram+'.html',new TextDecoder().decode(Uint8Array.from(atob(ATLAS.diagrams[currentDiagram].base64),c=>c.charCodeAt(0))),'text/html');
$('#stateTable').innerHTML='<h3>状态转移的精确条件</h3><div class="scrolltable"><table><thead><tr><th>从 → 到</th><th>实际触发</th><th>限制</th></tr></thead><tbody>'+[
 ['入队 → queued','校验、资源/队列检查通过后写 request.json 与 SQLite','校验失败不产生任务状态'],['queued → running','worker 执行前未检查到取消','启动子进程与 HTTP 返回可并发'],['queued/running → cancelled','worker 在指定安全点检测到 cancel_requested','取消按钮先置标志；不是立即强杀'],['running → completed','计算返回、末次取消检查通过、result.json 写出','未完成数据不会标完成'],['queued/running → failed','worker 异常，或 future 回调报告执行失败','保留错误信息；不会自动重试'],['queued/running → interrupted','初始化管理器时确认原 owner_pid 已退出','不是核心 checkpoint 自动恢复']
 ].map(r=>'<tr>'+r.map(c=>`<td>${h(c)}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>';

$('#dirtyFiles').innerHTML=S.dirty.map(d=>`<div class="searchrow"><span class="mono">${h(d.status)} ${h(d.path)}</span>${S.sources['WORKTREE/'+d.path]?source({path:'WORKTREE/'+d.path,line:1,label:'当前未提交快照'}):'<span class="muted">仅状态记录</span>'}</div>`).join('');
$('#verificationList').innerHTML=ATLAS.receipts.map(r=>`<div class="panel flat validation"><strong>${h(diagramNames[r.id])}</strong><p class="small">${Object.entries(r.gates).map(([k,v])=>badge(v==='pass'?'shared':'separate',k+' · '+v)).join('')}</p><div class="small mono">候选 JSON：${r.specification.sha256}<br>HTML：${r.artifact.sha256}</div><button class="source" data-receipt="${r.id}">查看完整校验回执</button></div>`).join('');
$('#evidenceSummary').textContent=`固定提交 ${S.revision.slice(0,12)}；${S.inventory.length} 个已跟踪目录文件，${Object.keys(S.sources).length} 份文本快照（含明确标记的 WORKTREE），${Object.keys(S.modules).length} 个 Python 模块。配置解析 6 种类型全部成功。未运行物理仿真或重跑全部回归，不将既有测试文件等同本次已通过。`;

function navigate(id){if(!document.getElementById('page-'+id))id='overview';$$('.page').forEach(p=>p.hidden=p.id!=='page-'+id);$$('.navbtn').forEach(b=>{b.classList.toggle('active',b.dataset.page===id);if(b.dataset.page===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});history.replaceState(null,'','#'+id);window.scrollTo({top:0,behavior:'instant'});if(id==='diagrams'&&!$('#diagramFrame').srcdoc)selectDiagram(currentDiagram)}
$$('.navbtn').forEach(b=>b.onclick=()=>navigate(b.dataset.page));
function openSource(path,line=1,end=line){const snapshot=S.sources[path];if(!snapshot){$('#sourceTitle').textContent=path;$('#sourceMeta').textContent='此文件仅记录目录，不包含可展开的文本快照。';$('#sourceCode').textContent='';$('#sourceDialog').showModal();return}$('#sourceTitle').textContent=path;$('#sourceMeta').textContent=`${snapshot.basis} · ${snapshot.basis==='HEAD'?S.revision.slice(0,12):'未提交，不属于 HEAD'} · SHA-256 ${snapshot.sha256} · 高亮 L${line}–${end}`;showCode(snapshot.text,line,end)}
function showCode(text,line=1,end=line){$('#sourceCode').innerHTML=text.split('\n').map((t,i)=>`<div class="codeline ${i+1>=line&&i+1<=end?'hl':''}" data-code-line="${i+1}"><span>${i+1}</span><code>${h(t)}</code></div>`).join('');if(!$('#sourceDialog').open)$('#sourceDialog').showModal();requestAnimationFrame(()=>{const code=$('#sourceCode');const target=code.querySelector(`[data-code-line="${line}"]`);code.scrollTop=target?Math.max(0,target.offsetTop-code.offsetTop-60):0})}
function openConfig(id){$('#sourceTitle').textContent=`${id} · ${S.configs[id].type} · 已解析规范配置`;$('#sourceMeta').textContent='只读默认值快照；由现有 SimulationConfig 解析，未写入项目配置。';showCode(JSON.stringify(S.configs[id].values,null,2))}
$('#closeSource').onclick=()=>$('#sourceDialog').close();$('#sourceDialog').onclick=e=>{if(e.target===$('#sourceDialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}};
document.addEventListener('click',e=>{const s=e.target.closest('[data-srcpath]');if(s){openSource(s.dataset.srcpath,+s.dataset.line||1,+s.dataset.end||+s.dataset.line||1);return}const c=e.target.closest('[data-config]');if(c){openConfig(c.dataset.config);return}const m=e.target.closest('[data-mod]');if(m){currentModule=m.dataset.mod;$('#moduleSearch').value='';$('#moduleSelect').innerHTML=moduleNames.map(n=>`<option value="${h(n)}">${h(n)}</option>`).join('');renderDependencies();navigate('dependencies');return}const p=e.target.closest('[data-focusplatform]');if(p){selectedPlatforms=new Set([p.dataset.focusplatform]);$('#reuseSearch').value='';$('#reuseKind').value='';renderMatrix();navigate('reuse');return}const receipt=e.target.closest('[data-receipt]');if(receipt){const r=ATLAS.receipts.find(r=>r.id===receipt.dataset.receipt);$('#sourceTitle').textContent=diagramNames[r.id]+' · finalize 回执';$('#sourceMeta').textContent='Archify 自动门禁回执；截图检查另见本次网页验证记录。';showCode(JSON.stringify(r,null,2))}});
function download(name,text,type='application/json'){const blob=new Blob([text],{type:type+';charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('#downloadAnalysis').onclick=()=>download('spad-architecture-analysis-'+S.revision.slice(0,8)+'.json',JSON.stringify({revision:S.revision,generated:S.generated,analysis:A,proposal:ATLAS.proposal.summary,staticImports:S.edges,configs:S.configs},null,2));
$('#printReport').onclick=()=>window.print();$('#toggleTheme').onclick=()=>{document.body.classList.toggle('dark');$('#toggleTheme').textContent=document.body.classList.contains('dark')?'浅色':'深色'};
overview();renderMatrix();renderParams();renderAlgorithms();renderDependencies();navigate(location.hash.slice(1)||'overview');
window.atlasReady=true;

const PROP=ATLAS.proposal.summary;
let comparisonId='current';
function selectComparison(id){
 comparisonId=id;const d=ATLAS.proposal.diagrams[id];
 $('#comparisonFrame').srcdoc=new TextDecoder().decode(Uint8Array.from(atob(d.base64),c=>c.charCodeAt(0)));
 $$('[data-compare]').forEach(b=>{b.classList.toggle('active',b.dataset.compare===id);b.setAttribute('aria-pressed',String(b.dataset.compare===id))});
 $('#comparisonStatus').textContent=id==='current'?`当前实现 · 固定源码基线 ${PROP.basis.slice(0,12)}。现状图已核验源码引用与真实浏览器显示。`:'建议方案 · 尚未实施。图中的公共执行器、TrialPlan、新目录与整合工作台为讨论设计；图表校验通过不代表这些功能已经建立。';
 $('#comparisonStatus').classList.toggle('warn',id==='proposed');
 $('#comparisonEvidence').innerHTML=d.spec.components.map(n=>`<div class="evidence-item"><strong>${h(n.label)}</strong><span class="badge ${id==='current'?'shared':'adapter'}">${h(n.tag||'')}</span><p class="small">${h(n.sublabel||'')}</p>${id==='current'?`<span class="muted">源码依据：${n.sources?.length||0} 处</span>${evidence((n.sources||[]).map(r=>({...r,end:r.end_line})))}`:'<span class="muted">建议职责；无对应新实现的源码存在性声明。</span>'}</div>`).join('');
}
function renderProposalChanges(filter='all'){
 const changes=PROP.changes.filter(c=>filter==='all'||(filter==='merge'?['merge','reuse'].includes(c.kind):c.kind==='keep'));
 $('#proposalChanges').innerHTML='<table><thead><tr><th>领域</th><th>处理方式</th><th>当前架构</th><th>建议架构</th><th>必须保留的边界</th></tr></thead><tbody>'+changes.map(c=>`<tr><td><strong>${h(c.area)}</strong></td><td>${badge(c.kind==='keep'?'separate':c.kind==='reuse'?'shared':'adapter',c.action)}</td><td>${h(c.current)}</td><td>${h(c.proposed)}</td><td>${h(c.boundary)}</td></tr>`).join('')+'</tbody></table>';
 $$('[data-change]').forEach(b=>b.classList.toggle('active',b.dataset.change===filter));
}
$('#proposalDirectory').textContent=PROP.directory;
$('#proposalMapping').innerHTML='<table><thead><tr><th>当前文件 / 目录</th><th>建议职责位置（草案）</th><th>动作与限制</th></tr></thead><tbody>'+PROP.mapping.map(r=>'<tr>'+r.map((c,i)=>`<td class="${i===1?'parampath':''}">${h(c)}${i===1?'<br><span class="badge adapter">'+(r[0]===r[1]?'保持现有':'迁移草案')+'</span>':''}</td>`).join('')+'</tr>').join('')+'</tbody></table>';
$('#proposalPhases').innerHTML=PROP.phases.map(([name,text])=>`<div><h3>${h(name)}</h3><p class="muted small">${h(text)}</p></div>`).join('');
$('#comparisonFull').onclick=()=>$('#comparisonFrame').requestFullscreen().catch(()=>{});
$('#comparisonDownload').onclick=()=>download('spad-'+comparisonId+'-architecture.html',new TextDecoder().decode(Uint8Array.from(atob(ATLAS.proposal.diagrams[comparisonId].base64),c=>c.charCodeAt(0))),'text/html');
$('#comparisonReceipt').onclick=()=>{const r=ATLAS.proposal.diagrams[comparisonId].receipt;$('#sourceTitle').textContent=(comparisonId==='current'?'当前':'建议')+'架构图 · 校验回执';$('#sourceMeta').textContent='仅证明图表的自动校验与交付；建议图不代表重构实施。';showCode(JSON.stringify(r,null,2))};
$('#changeFilters').onclick=e=>{const b=e.target.closest('[data-change]');if(b)renderProposalChanges(b.dataset.change)};
document.addEventListener('click',e=>{const c=e.target.closest('[data-compare]');if(c)selectComparison(c.dataset.compare);const b=e.target.closest('[data-go]');if(b)navigate(b.dataset.go)});
const jump=document.createElement('div');jump.className='note';jump.innerHTML='<strong>新增：当前 / 建议架构对比。</strong> 明确合并复用与独立边界，附建议目录草案。 <button data-go="proposal">查看建议方案 →</button>';$('#page-overview').insertBefore(jump,$('#heroMetrics'));
selectComparison('current');renderProposalChanges();window.atlasProposalReady=true;
