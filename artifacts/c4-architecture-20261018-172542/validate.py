from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
read=lambda f:json.loads((OUT/f).read_text(encoding='utf-8-sig'))
S=read('snapshot.json');build=read('build-receipt.json');checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'ok':bool(ok),'detail':detail})
    if not ok:raise AssertionError(name+': '+str(detail))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
check('self-contained report bytes',sha(OUT/'index.html')==build['reportSha256'])
for id,graph in build['graphs'].items():
    check('diagram '+id,sha(OUT/(id+'.html'))==graph['sha256'] and all(v=='pass' for v in graph['gates'].values()))
    for node in read(id+'.json')['components']:
        for r in node['sources']:
            f=S['sources'][r['path']]
            check('source '+r['path']+':'+str(r['line']),1<=r['line']<=r['end_line']<=f['lines'])
for viewport in ('desktop','narrow'):
    browser=read('browser-'+viewport+'.json')
    check('browser '+viewport,browser['success'] and browser['data']['result']['ok'])
protected={p:f for p,f in S['sources'].items() if p.startswith(('src/','web/','config/')) or p in ('run.py','pyproject.toml')}
changed=[p for p,f in protected.items() if sha(ROOT/p)!=f['sha256']]
check('source/frontend/config unchanged',not changed,changed)
check('expert source unchanged',sha(Path(S['expert']['path']))==S['expert']['sha256'])
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
check('no product commit',head==S['productHead'])
result={'ok':True,'workingTreeSnapshot':S['generated'],'productHead':head,'localProofRevision':S['proofRevision'],'productCommitCreated':False,'protectedFilesUnchanged':len(protected),'pages':4,'c4Levels':['C1','C2','C3'],'expertC4SectionConfirmed':True,'expertHostLoadingVerified':False,'desktopChecks':len(read('browser-desktop.json')['data']['result']['checks']),'narrowChecks':len(read('browser-narrow.json')['data']['result']['checks']),'graphGates':build['graphs'],'reportSha256':build['reportSha256'],'localSourceBundleSha256':sha(OUT/'source-proof.bundle'),'reviewedScreenshots':['c2-page-desktop.png','data-page-desktop.png','c1-visual/c1.visual-check.1440x900.light.png','c3-visual/c3.visual-check.1440x900.light.png','c4-final-narrow.png'],'checks':checks}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','graphGates')},ensure_ascii=False))
