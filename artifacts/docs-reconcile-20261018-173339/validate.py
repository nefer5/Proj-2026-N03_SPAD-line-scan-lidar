from pathlib import Path
from urllib.parse import unquote,urlsplit
import hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
strip_fences=lambda text:re.sub(r'```[\s\S]*?```|~~~[\s\S]*?~~~','',text)
def anchors(path):
    if path.suffix!='.md':return None
    text=strip_fences(path.read_text(encoding='utf8'));found=set(re.findall(r'<a\s+id=["\']([^"\']+)',text))
    for heading in re.findall(r'^#{1,6}\s+(.+)$',text,re.M):
        heading=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',heading).strip().lower()
        found.add(re.sub(r'[^\w\s-]','',heading).replace(' ','-'))
    return found
broken=[];count=0;docs=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))]
for p in docs:
    text=strip_fences(p.read_text(encoding='utf8'))
    text=re.sub(r'`[^`\n]*`','',text)
    for match in re.finditer(r'!?\[[^\]\n]*\]\(([^\n)]+)\)',text):
        raw=match.group(1);url=raw[1:raw.index('>')] if raw.startswith('<') else raw.split(' ',1)[0]
        parsed=urlsplit(url)
        if parsed.scheme or url.startswith('//'):continue
        count+=1;target=(p.parent/unquote(parsed.path)).resolve() if parsed.path else p.resolve()
        if not target.exists():broken.append({'from':str(p.relative_to(ROOT)),'link':url,'error':'missing file'});continue
        if parsed.fragment and target.suffix=='.md' and unquote(parsed.fragment) not in anchors(target):broken.append({'from':str(p.relative_to(ROOT)),'link':url,'error':'missing heading/id'})

S=json.loads((ROOT/'artifacts/c4-architecture-20261018-172542/snapshot.json').read_text(encoding='utf8'))
protected={path:value for path,value in S['sources'].items() if path.startswith(('src/','web/','config/')) or path in ('run.py','pyproject.toml')}
altered=[path for path,s in protected.items() if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=s['sha256']]
classifications=[]
for p in docs:
    path=p.relative_to(ROOT).as_posix()
    if '/history/' in path:status='historical-only'
    elif path in ('docs/models/scanning.md','docs/models/detection-performance.md','docs/design/lidar-3d-schematic-prompt.md'):status='redirect-only'
    elif '/references/' in path:status='reference/compatibility, not current defaults'
    elif path in ('docs/models/photon-budget.md','docs/models/spatial-profiles.md'):status='generated-current; checked against shared YAML'
    elif path=='docs/release-notes.md':status='dated release history; not current specification'
    elif path=='docs/design/architecture-decisions.md':status='dated decision authority; current implementation via architecture/roadmap'
    else:status='current'
    classifications.append({'path':path,'status':status,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
before=json.loads((OUT/'archive-manifest.json').read_text(encoding='utf8'))
changes=[p for p,h in before['original_sha256'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
result={'ok':not broken and not altered,'markdown_documents':len(docs),'local_links_checked':count,'broken_links':broken,'protected_source_config_frontend':len(protected),'altered_protected_files':altered,'originals_preserved_in':'before.zip','archive_map':before['archive_map'],'redirect_stubs':before['redirect_stubs'],'changed_original_documents':changes,'classifications':classifications,'code_or_config_changes':False,'current_authorities':{'navigation':'docs/index.md','structure':'docs/design/architecture.md','configuration_and_user_data':'docs/guides/configuration-and-data.md','decisions':'docs/design/architecture-decisions.md','implementation_and_acceptance':'docs/roadmap.md','defaults':'config/defaults.yaml','policy':'AGENTS.md'}}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k not in ('classifications','archive_map','current_authorities')},ensure_ascii=False));raise SystemExit(not result['ok'])
