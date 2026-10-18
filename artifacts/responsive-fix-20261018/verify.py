"""Browser verification of layout and state preservation; no model overrides."""
import base64
import json
import subprocess
import time
from pathlib import Path

OUT=Path(__file__).resolve().parent
CLI=r'C:\Users\admin\AppData\Roaming\npm\node_modules\agent-browser\bin\agent-browser-win32-x64.exe'
def call(*args):
    p=subprocess.run([CLI,'--session','spad-responsive-fix',*map(str,args)],capture_output=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError(p.stderr or p.stdout)
    return p.stdout.strip()
def js(source):
    raw=json.loads(call('eval','-b',base64.b64encode(source.encode()).decode()))
    return json.loads(raw) if isinstance(raw,str) else raw
def check(condition,message):
    if not condition: raise AssertionError(message)
def wait_for(source): call('wait','--fn',source)
def click(selector): call('click',selector)

results=[]
MEASURE='''JSON.stringify((()=>{
 const rect=e=>{if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {x:r.x,y:r.y,w:r.width,h:r.height,display:s.display,overflow:s.overflow,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,scrollTop:e.scrollTop}};
 const aside=document.querySelector('.parameter-panel,main>aside');
 const groups=document.querySelector('#parameterGroups,#parameters');
 const a=aside?.getBoundingClientRect(),g=groups?.getBoundingClientRect();
 return {w:innerWidth,h:innerHeight,dpr:devicePixelRatio,documentWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,
 view:document.querySelector('#aWorkspace')?.dataset.view,
 controls:rect(document.querySelector('.controls')),results:rect(document.querySelector('.results')),
 switcher:rect(document.querySelector('.a-workspace-switch')),aside:rect(aside),groups:rect(groups),
 visibleFormHeight:a&&g?Math.max(0,Math.min(innerHeight,a.bottom,g.bottom)-Math.max(0,a.top,g.top)):null,
 details:['sceneVerticalCard','sceneImageCard'].map(id=>{const e=document.getElementById(id);if(!e)return null;const t=e.querySelector('svg'),v=t?.viewBox.baseVal;return {id,card:rect(e),svg:rect(t),viewBoxWidth:v?.width}}),
 canvases:[...document.querySelectorAll('canvas')].filter(e=>e.clientWidth>0).map(e=>({id:e.id,w:e.clientWidth,buffer:e.width})),
 alerts:[...document.querySelectorAll('[role=alert],#errorBox')].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.innerText)};
})())'''
def capture(name,selector=None):
    if selector: js(f'document.querySelector({json.dumps(selector)}).scrollIntoView()')
    time.sleep(.25)
    d=js(MEASURE);d['case']=name
    check(d['documentWidth']<=d['clientWidth']+1,f'{name}: document overflow')
    call('screenshot',OUT/f'{name}.png')
    results.append(d)
    (OUT/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(name,'ok','visibleForm',d['visibleFormHeight'],flush=True)
    return d

sizes=[(1920,940,1),(1536,734,1.25),(1280,600,1.5),(960,440,2),(3440,1320,1)]
for name,path in [('budget','/system/budget'),('a','/'),('debug','/debug'),('b','/system'),('c','/system/columns')]:
    call('open','http://127.0.0.1:8016'+path)
    call('wait','--load','networkidle')
    if name in ['a','debug']:
        wait_for('document.getElementById("runButton").disabled===false && document.body.dataset.mode')
    if name=='c':
        # Explicit bounded UI scenario, not a change to application defaults.
        js('document.querySelector("[data-high=slot_count]").value="4"')
        click('#scopeTwo')
        wait_for('document.getElementById("draftState").innerText.includes("两列局部实验")')
        check(js('JSON.stringify(!document.querySelector("#runAcquisition").disabled)'),'C local preview unavailable')
    for w,h,dpr in sizes:
        call('set','viewport',w,h,dpr);time.sleep(.3)
        js('window.scrollTo(0,0)')
        d=capture(f'{name}-{w}')
        if name=='budget':
            detail=capture(f'{name}-details-{w}','#sceneVerticalCard')
            if w in [1280,960]:
                left,right=detail['details']
                check(abs(left['card']['x']-right['card']['x'])<2,'Budget details must stack')
                check(right['card']['y']>=left['card']['y']+left['card']['h']-2,'Budget detail overlap')
                check(left['svg']['w']>=619,'Detector labels shrank below planned size')
        if name in ['b','c'] and h<=700:
            check(d['groups']['overflow']=='visible',f'{name}: nested scrolling remains')
            js('document.querySelector(".parameter-panel,main>aside").scrollTop=260')
            js('window.scrollTo(0,scrollY+document.querySelector(".parameter-panel,main>aside").getBoundingClientRect().top-16)')
            scrolled=capture(f'{name}-editor-{w}')
            check(scrolled['visibleFormHeight']>=h-65,f'{name}: form not gaining viewport height')
            js('document.querySelector(".parameter-panel,main>aside").scrollTop=0')
    if name in ['a','debug']:
        # Desktop and scaled 1080P keep their left parameter sidebar.
        for w in [1920,1536,1280,960,761]:
            call('set','viewport',w,600,1);time.sleep(.2)
            check(js('JSON.stringify(document.querySelector("#aParameters").getBoundingClientRect().height>0&&document.querySelector("#aResults").getBoundingClientRect().height>0&&getComputedStyle(document.querySelector(".a-workspace-switch")).display==="none")'),'A desktop sidebar not preserved')
        call('set','viewport',760,600,1);time.sleep(.3)
        js('window.auditResultRef=lastResult;window.auditRange=JSON.stringify(histogramView.range);window.auditConfig=JSON.stringify(collectConfig());window.auditPosts=0;window.auditFetch=fetch;window.fetch=(...a)=>{if(a[0]==="/api/jobs"&&a[1]?.method==="POST")auditPosts++;return auditFetch(...a)}')
        click('[data-a-view="parameters"]')
        check(js('JSON.stringify(document.querySelector("#aResults").getBoundingClientRect().height===0)'),'A results not hidden')
        # Keyboard activation uses the native button, with input values retained.
        js('document.querySelector("[data-a-view=results]").focus()')
        call('press','Enter');time.sleep(.3)
        check(js('JSON.stringify(lastResult===auditResultRef&&JSON.stringify(histogramView.range)===auditRange&&JSON.stringify(collectConfig())===auditConfig&&auditPosts===0)'),'A view switch changed acquisition or parameters')
        capture(f'{name}-switch-results')
        check(js('JSON.stringify(document.querySelector("#pulseChart").width>0)'),'A chart not redrawn')
        call('set','viewport',761,600,1);time.sleep(.25)
        check(js('JSON.stringify(document.querySelector("#aParameters").getBoundingClientRect().height>0&&document.querySelector("#aResults").getBoundingClientRect().height>0)'),'A desktop columns not restored')
        call('set','viewport',760,600,1);time.sleep(.25)
        capture(f'{name}-breakpoint-760')
        call('reload');call('wait','--load','networkidle')
        wait_for('document.getElementById("runButton").disabled===false && document.body.dataset.mode')
        check(js('JSON.stringify(document.querySelector("#aWorkspace").dataset.view==="results")'),'A ordinary reload did not initialize result view')
    errors=call('errors')
    (OUT/f'{name}-browser-errors.txt').write_text(errors,encoding='utf-8')
    check(not errors,f'{name}: browser errors: {errors}')

print('All layout, sidebar scroll and A state-preservation assertions passed.',flush=True)
