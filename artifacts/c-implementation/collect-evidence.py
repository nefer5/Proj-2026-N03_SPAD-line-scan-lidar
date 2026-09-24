import json,hashlib,urllib.request
from pathlib import Path
jobs={'quiet_full_frame':'5662e32a033f4325b9f427a1f84e18be','bright_two_columns':'c3b040fee32b4b65a605e60ace16997e'}
out={}
for name,job in jobs.items():
    view=json.load(urllib.request.urlopen(f'http://127.0.0.1:8016/api/columns/jobs/{job}/view'))
    state=json.load(urllib.request.urlopen(f'http://127.0.0.1:8016/api/jobs/{job}'))
    path=Path(state['result_path'])
    out[name]={'job_id':job,'url':f'http://127.0.0.1:8016/system/scan?job={job}','status':state['status'],
        'configuration':view['configuration']['experiment'],'provenance':view['provenance'],
        'summary':view['summary'],'records':view['audit']['final_records'],'statistics':view['statistics'],
        'transport_summary':view['transport'].get('summary'),'result_path':str(path),
        'result_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'result_bytes':path.stat().st_size}
Path('artifacts/c-implementation/verified-jobs.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({name:{'job_id':r['job_id'],'status':r['status'],'records':r['records'],'bytes':r['result_bytes']} for name,r in out.items()},ensure_ascii=False))