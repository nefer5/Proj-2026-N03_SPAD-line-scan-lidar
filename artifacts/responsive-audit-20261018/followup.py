from pathlib import Path
exec(Path(__file__).with_name('audit.py').read_text(encoding='utf-8').split("pages={'budget'")[0])

results=[]
def capture(name,w,h,dpr=1,selector=None):
    call('set','viewport',w,h,dpr)
    time.sleep(.35)
    js=f'document.querySelector({json.dumps(selector)}).scrollIntoView()' if selector else 'window.scrollTo(0,0)'
    call('eval','-b',base64.b64encode(js.encode()).decode())
    time.sleep(.15)
    d=evaluate(JS)
    d['case']=name
    d['alerts']=evaluate('JSON.stringify([...document.querySelectorAll("[role=alert]")].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.innerText))')
    call('screenshot',OUT/f'{name}.png')
    results.append(d)
    (OUT/'followup.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(name,'height',d['docHeight'],'alerts',d['alerts'],flush=True)

call('open','http://127.0.0.1:8016/system/budget')
call('wait','--load','networkidle')
capture('budget-detail-1280',1280,600,1.5,'#sceneVerticalCard')
capture('budget-detail-960',960,440,2,'#sceneVerticalCard')
call('open','http://127.0.0.1:8016/system')
call('wait','--load','networkidle')
capture('b-short-960',960,440,1,'.parameter-panel')
capture('b-851',851,600)
capture('b-850',850,600)
call('open','http://127.0.0.1:8016/system/columns')
call('wait','--load','networkidle')
call('eval','document.getElementById("loadDemo").click()')
call('wait','--load','networkidle')
capture('c-demo-1280',1280,600,1.5)
capture('c-demo-960',960,440,1,'#timeline')
call('open','http://127.0.0.1:8016/')
call('wait','--load','networkidle')
capture('a-1101',1101,600)
capture('a-1100',1100,600)
capture('a-results-960',960,440,1,'.results')
