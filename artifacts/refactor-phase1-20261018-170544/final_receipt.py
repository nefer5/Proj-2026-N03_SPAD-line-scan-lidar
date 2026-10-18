from pathlib import Path
import hashlib,json,subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
read=lambda name:json.loads((OUT/name).read_text(encoding='utf8'))
preservation=read('preservation.json');numerics=read('numerical-comparison.json')
assert preservation['ok'] and numerics['ok']
before=read('before-manifest.json')['files']
new_files=[]
for directory in ('src','tests'):
    new_files.extend(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*.py') if p.relative_to(ROOT).as_posix() not in before)
result={'status':'self-verified; user/manual acceptance not implied','phase':'backend shared layers / phase 1','generated':datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),
 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'scope':['shared domain field definitions with compatibility exports','optical projection independent of experiment/display layer','periodic record adapter above unchanged SPAD engine','explicit TrialPlan and lazy ordered repetition for A/B/C','pure background-bin numeric helpers'],
 'preservation':preservation,'numerical_equivalence':numerics,
 'tests':{'before':{'command':'python -m pytest -q --disable-warnings --maxfail=1','passed':431,'seconds':111.78},
          'after_existing_suite':{'command':'python -m pytest -q --disable-warnings --maxfail=1','passed':431,'seconds':121.08,'note':'collection occurred before new boundary-test file was added'},
          'new_boundaries':{'command':'python -m pytest -q tests/test_refactor_boundaries.py --disable-warnings','passed':13},'distinct_tests_passed':444},
 'new_files':sorted(new_files),'new_file_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(new_files)},
 'rollback':{'archive':'before.zip','archive_sha256':hashlib.sha256((OUT/'before.zip').read_bytes()).hexdigest(),'manifest':'before-manifest.json','warning':'Restore only reviewed individual paths. Existing uncommitted 1080P and launcher edits are included; do not reset to HEAD or overwrite later work.'},
 'deferred':['three-workbench frontend redesign; preserve current 1080P changes','C inter-column reset and duration','A/B physical equivalence changes','C/budget transport algorithm merge','C/budget full config composition migration and whole R03/R04 audit'],
 'deployment':'No intentional running-service restart, package install, Git commit or push. Existing reload service may reload edited Python; application-level deployment was not separately asserted.'}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'distinct_tests_passed':444,'exact_numeric_and_schema_cases':len(numerics['cases']),'preserved_frontend':preservation['all_existing_frontend_bytes_unchanged'],'new_files':sorted(new_files),'receipt':str(OUT/'validation.json')},ensure_ascii=False))
