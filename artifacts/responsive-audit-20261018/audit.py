import base64
import json
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
CLI = r'C:\Users\admin\AppData\Roaming\npm\node_modules\agent-browser\bin\agent-browser-win32-x64.exe'

def call(*args):
    p = subprocess.run([CLI, '--session', 'spad-responsive-audit', *map(str,args)], capture_output=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(p.stderr or p.stdout)
    return p.stdout.strip()

def evaluate(js):
    raw = call('eval','-b',base64.b64encode(js.encode()).decode())
    result = json.loads(raw)
    return json.loads(result) if isinstance(result,str) else result

JS = r'''JSON.stringify((()=>{
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'};
 const box=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {tag:e.tagName,id:e.id,cls:String(e.className).slice(0,90),x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height),scrollW:e.scrollWidth,scrollH:e.scrollHeight,font:s.fontSize,overflow:s.overflow,position:s.position,grid:s.gridTemplateColumns}};
 const all=[...document.querySelectorAll('body *')].filter(visible);
 const layout=[...document.querySelectorAll('main,.workspace,aside,.controls,.parameter-panel,.parameter-groups,#parameters,.results,.content,.scene-viewport,.scene-inspector,.metric-grid,.metrics,.high-inputs,.energy-analysis-grid')].filter(visible).map(box);
 const overflow=all.filter(e=>{const r=e.getBoundingClientRect();return r.right>innerWidth+2||r.left< -2}).map(box);
 const clipped=all.filter(e=>e.scrollWidth>e.clientWidth+3&&['hidden','clip'].includes(getComputedStyle(e).overflowX)).slice(0,20).map(box);
 const svg=[...document.querySelectorAll('svg')].filter(visible).map(e=>{const b=box(e),t=e.querySelector('text'),vb=e.viewBox.baseVal;return {...b,viewBox:[vb.width,vb.height],textPx:t?Number.parseFloat(getComputedStyle(t).fontSize)*(vb.width?e.getBoundingClientRect().width/vb.width:1):null}});
 const canvas=[...document.querySelectorAll('canvas')].filter(visible).map(e=>({...box(e),buffer:[e.width,e.height]}));
 return {url:location.pathname,width:innerWidth,height:innerHeight,dpr:devicePixelRatio,docWidth:document.documentElement.scrollWidth,docHeight:document.documentElement.scrollHeight,layout,overflow:overflow.slice(0,25),clipped,svg,canvas,errors:[...document.querySelectorAll('#error,.loading-error,#loadError')].filter(visible).map(e=>e.innerText),buttons:[...document.querySelectorAll('button')].filter(visible).slice(0,12).map(e=>({text:e.innerText,disabled:e.disabled}))};
})())'''

pages={'budget':'/system/budget','b':'/system','c':'/system/columns','a':'/','debug':'/debug','spad':'/spad'}
sizes=[(1920,940,1),(1536,734,1.25),(1280,600,1.5),(2560,1000,1.5),(3440,1320,1),(960,440,2)]
results=[]
for name,path in pages.items():
    call('open','http://127.0.0.1:8016'+path)
    call('wait','--load','networkidle')
    for w,h,dpr in sizes:
        call('set','viewport',w,h,dpr)
        time.sleep(.3)
        call('eval','window.scrollTo(0,0)')
        data=evaluate(JS)
        data['page']=name
        call('screenshot',OUT/f'{name}-{w}.png')
        results.append(data)
        (OUT/'measurements.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,w,'actual',data['width'],data['height'],'doc',data['docWidth'],'overflows',len(data['overflow']),flush=True)
