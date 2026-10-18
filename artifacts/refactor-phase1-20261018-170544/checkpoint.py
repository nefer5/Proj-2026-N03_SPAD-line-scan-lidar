"""Preserve the current dirty checkout without Git resets, moves, or commits."""
from pathlib import Path
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
files=[]
for directory in ('src','config','web','docs','tests','scripts','tools','examples'):
    for p in (ROOT/directory).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc',):files.append(p)
files += [ROOT/name for name in ('AGENTS.md','README.md','run.py','start-dev.cmd','pyproject.toml','package.json','package-lock.json') if (ROOT/name).is_file()]
manifest={}
with zipfile.ZipFile(OUT/'before.zip','x',zipfile.ZIP_DEFLATED) as archive:
    for p in files:
        name=p.relative_to(ROOT).as_posix();data=p.read_bytes()
        archive.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
state={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True),
       'files':manifest,'restore':'before.zip contains exact original bytes, including existing uncommitted frontend/launcher edits. Restore individual reviewed paths only; do not overwrite later changes.'}
(OUT/'before-manifest.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'before.patch').write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=ROOT))
print(json.dumps({'files':len(manifest),'head':state['head'],'archive':str(OUT/'before.zip')},ensure_ascii=False))
