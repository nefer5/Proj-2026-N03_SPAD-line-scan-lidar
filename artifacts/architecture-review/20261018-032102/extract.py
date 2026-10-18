"""Read-only repository snapshot and AST inventory for the architecture atlas."""
from pathlib import Path
import ast, hashlib, io, json, subprocess, sys, tarfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)
revision=git('rev-parse','HEAD').decode().strip()
origin=git('remote','get-url','origin').decode().strip()
status=git('status','--porcelain=v1','-uall').decode('utf8')
archive=git('archive','HEAD','src','config','web','docs','tests','scripts','tools','examples','data/synthetic','data/reference/README.md','AGENTS.md','.gitignore','README.md','pyproject.toml','run.py','start-dev.cmd','package.json')
sources={}; inventory=[]; modules={}
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    for member in tar.getmembers():
        if not member.isfile():continue
        path=member.name
        if '/vendor/' in path or '/prototypes/' in path:continue
        if not path.endswith(('.py','.js','.md','.yaml','.toml','.cmd','.json','.html','.css')):continue
        data=tar.extractfile(member).read()
        try:text=data.decode('utf8')
        except UnicodeDecodeError:continue
        sources[path]={'text':text,'sha256':hashlib.sha256(data).hexdigest(),'lines':len(text.splitlines()),'basis':'HEAD'}
        if path.startswith('src/spad_lidar/') and path.endswith('.py'):
            module=path[4:-3].replace('/','.')
            if module.endswith('.__init__'):module=module[:-9]
            package=module.split('.') if path.endswith('__init__.py') else module.split('.')[:-1]
            tree=ast.parse(text,filename=path)
            symbols=[]; imports=[]; calls=[]
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    symbols.append({'name':node.name,'kind':'class' if isinstance(node,ast.ClassDef) else 'function','line':node.lineno,'end':node.end_lineno})
                if isinstance(node,ast.ImportFrom):
                    base=package[:len(package)-node.level+1] if node.level else []
                    target='.'.join(base+([node.module] if node.module else []))
                    imports.append({'target':target,'names':[a.name for a in node.names],'line':node.lineno,'scope':'static import; execution may be conditional'})
                elif isinstance(node,ast.Import):
                    for alias in node.names:imports.append({'target':alias.name,'names':[],'line':node.lineno,'scope':'static import'})
                elif isinstance(node,ast.Call):
                    try:name=ast.unparse(node.func)
                    except Exception:continue
                    calls.append({'name':name,'line':node.lineno})
            modules[module]={'path':path,'symbols':symbols,'imports':imports,'calls':calls}

# Complete tracked directory inventory without reading opaque binary assets.
for record in git('ls-tree','-r','--long','HEAD').decode('utf8').splitlines():
    metadata,path=record.split('\t',1)
    size=metadata.split()[-1]
    inventory.append({'path':path,'bytes':int(size) if size.isdigit() else 0})
# Map only statically resolvable repository imports. A declaration is not a runtime trace.
edges=[]
for name,info in modules.items():
    for imp in info['imports']:
        targets=[]
        if imp['target'] in modules:targets.append(imp['target'])
        for sym in imp['names']:
            expanded=imp['target']+'.'+sym
            if expanded in modules:targets.append(expanded)
        for target in set(targets):
            if target!=name:edges.append({'from':name,'to':target,'line':imp['line'],'names':imp['names']})

# Canonical resolved defaults, using existing read-only configuration entry points.
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar import __version__
configs={}; config_errors={}
for kind in ['a','spad','system','columns','budget','scan']:
    try:
        cfg=SimulationConfig() if kind=='a' else SimulationConfig.for_experiment(kind,{})
        configs[kind]={'values':cfg.model_dump(),'schema':type(cfg).model_json_schema(),'type':type(cfg).__name__}
    except Exception as exc:config_errors[kind]=f'{type(exc).__name__}: {exc}'
algorithms=Algorithms.load().model_dump()
dirty=[]
for line in status.splitlines():
    path=line[3:]
    if path.startswith('artifacts/architecture-review/20261018-032102'):continue
    dirty.append({'status':line[:2],'path':path})
    actual=ROOT/path
    if actual.is_file() and actual.suffix in ('.py','.md','.cmd') and actual.stat().st_size<180000:
        sources['WORKTREE/'+path]={'text':actual.read_text(encoding='utf8'),'sha256':hashlib.sha256(actual.read_bytes()).hexdigest(),'lines':len(actual.read_text(encoding='utf8').splitlines()),'basis':'WORKTREE / uncommitted'}
snapshot={'revision':revision,'origin':origin,'version':__version__,'generated':datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),'dirty':dirty,'inventory':inventory,'sources':sources,'modules':modules,'edges':edges,'configs':configs,'configErrors':config_errors,'algorithms':algorithms,'help':read_yaml('parameter-help.yaml'),'defaults':read_yaml('defaults.yaml')}
(OUT/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print(json.dumps({'revision':revision,'files':len(inventory),'sourceSnapshots':len(sources),'pythonModules':len(modules),'staticEdges':len(edges),'configTypes':{k:v['type'] for k,v in configs.items()},'configErrors':config_errors,'dirty':dirty},ensure_ascii=False))
