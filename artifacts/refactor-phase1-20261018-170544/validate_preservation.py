"""Verify the precise refactor delta against the dirty-checkout checkpoint."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
before=json.loads((OUT/'before-manifest.json').read_text(encoding='utf8'))
changed=[];missing=[]
for path,digest in before['files'].items():
    p=ROOT/path
    if not p.is_file():missing.append(path)
    elif hashlib.sha256(p.read_bytes()).hexdigest()!=digest:changed.append(path)
protected=lambda p:p.startswith(('web/','config/','src/spad_lidar/spad/','src/spad_lidar/runtime/','tests/')) or p in ('run.py','start-dev.cmd','README.md','pyproject.toml','src/spad_lidar/api.py','docs/design/ui-design-guidelines.md','docs/index.md')
violations=[p for p in changed+missing if protected(p)]
result={'ok':not violations and not missing,'head_at_start':before['head'],'baseline':'dirty working checkout including existing 1080P/launcher changes','protected_files':sum(protected(p) for p in before['files']),'all_existing_frontend_bytes_unchanged':not any(p.startswith('web/') for p in changed+missing),'all_yaml_bytes_unchanged':not any(p.startswith('config/') for p in changed+missing),'state_core_and_launcher_unchanged':not any(p.startswith(('src/spad_lidar/spad/','src/spad_lidar/runtime/')) for p in changed+missing),'changed_since_checkpoint':changed,'missing':missing,'violations':violations}
(OUT/'preservation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False));raise SystemExit(not result['ok'])
