"""Freeze current working bytes; build a separate temporary Git proof checkout."""
from pathlib import Path
import ast,hashlib,json,os,subprocess,tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
proof=Path(tempfile.gettempdir())/'spad-c4-evidence-20261018-172542'
proof.mkdir(exist_ok=False)
sources={};symbols={};inventory=[]
paths=[]
for folder in ('src','config','web'):
    for p in (ROOT/folder).rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or '/vendor/' in p.as_posix() or '/prototypes/' in p.as_posix():continue
        if p.suffix not in ('.py','.yaml','.js','.html','.css'):continue
        paths.append(p)
paths.extend(ROOT/p for p in ('run.py','AGENTS.md','pyproject.toml','docs/design/architecture.md','docs/roadmap.md'))
for p in paths:
    path=p.relative_to(ROOT).as_posix();raw=p.read_bytes();text=raw.decode('utf8');dest=proof/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    sources[path]={'text':text,'sha256':hashlib.sha256(raw).hexdigest(),'lines':len(text.splitlines())}
    inventory.append(path)
    if p.suffix=='.py':symbols[path]=[{'name':n.name,'line':n.lineno,'end_line':n.end_lineno} for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
def git(*args,input=None):return subprocess.check_output(['git','-C',str(proof),*args],input=input)
git('init','--quiet');git('config','core.autocrlf','false');git('config','core.safecrlf','false');git('remote','add','origin','https://snapshot.invalid/spad-lidar-c4-20261018-172542.git');git('add','--all');tree=git('write-tree').decode().strip()
env=os.environ.copy();env.update(GIT_AUTHOR_NAME='Architecture evidence',GIT_AUTHOR_EMAIL='evidence@local.invalid',GIT_COMMITTER_NAME='Architecture evidence',GIT_COMMITTER_EMAIL='evidence@local.invalid')
revision=subprocess.check_output(['git','-C',str(proof),'commit-tree',tree],input=b'Working-tree evidence snapshot; not a product commit\n',env=env).decode().strip()
git('update-ref','HEAD',revision)
expert=Path('C:/Users/admin/.agents/experts/software-architect/instructions.md');lines=expert.read_text(encoding='utf8').splitlines()
snapshot={'generated':datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),'productHead':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'productStatus':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),'basis':'current working tree after backend phase 1; includes uncommitted frontend/launcher changes','proofRoot':str(proof),'proofRevision':revision,'proofIdentity':'local://spad-lidar-c4-working-tree-20261018-172542','sources':sources,'symbols':symbols,'inventory':sorted(inventory),'expert':{'path':str(expert),'sha256':hashlib.sha256(expert.read_bytes()).hexdigest(),'line':159,'end_line':174,'excerpt':'\n'.join(lines[158:174]),'status':'C4 C1-C3 confirmed in user-center source; host loading not reverified'}}
(OUT/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print(json.dumps({'proofRoot':str(proof),'proofRevision':revision,'files':len(inventory),'generated':snapshot['generated']},ensure_ascii=False))
