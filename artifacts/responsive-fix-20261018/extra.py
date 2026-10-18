from pathlib import Path
exec(Path(__file__).with_name('verify.py').read_text(encoding='utf-8').split('results=[]')[0])
checks=[]
for name,path in [('a','/'),('budget','/system/budget'),('b','/system'),('c','/system/columns')]:
    call('set','viewport',1280,600,1.5)
    call('open','http://127.0.0.1:8016'+path);call('wait','--load','networkidle')
    if name=='a':
        wait_for('!document.getElementById("runButton").disabled && document.body.dataset.mode')
        # Regression for the menu row adjusted after visual inspection.
        d=js('JSON.stringify({button:document.getElementById("runButton").getBoundingClientRect().toJSON(),cancel:document.getElementById("cancelAJob").getBoundingClientRect().toJSON()})')
        check(d['button']['width']>200 and d['cancel']['y']>d['button']['y'],'A action layout')
        call('screenshot',OUT/'a-final-1280.png')
        call('set','viewport',960,440,2);time.sleep(.3)
        call('screenshot',OUT/'a-final-960.png')
        call('set','viewport',760,600,1);time.sleep(.3)
        click('[data-a-view="parameters"]')
        call('fill','[data-key="range_m"]','101')
        time.sleep(.7)
        click('#runButton')
        wait_for('!document.getElementById("runButton").disabled')
        check(js('JSON.stringify(document.getElementById("aWorkspace").dataset.view==="results"&&lastResult.configuration.simulation.range_m===101)'),'A run did not switch to matching result')
        call('set','viewport',1280,600,1.5);time.sleep(.3)
    if name in ['b','c']:
        if name=='c':
            js('document.querySelector("[data-high=slot_count]").value="4"');click('#scopeTwo')
            wait_for('!document.getElementById("runAcquisition").disabled')
        # Actions at either end remain reachable in the single scroll owner.
        js('window.scrollTo(0,scrollY+document.querySelector(".parameter-panel,main>aside").getBoundingClientRect().top-16);document.querySelector(".parameter-panel,main>aside").scrollTop=1000000')
        check(js('JSON.stringify((()=>{const e=document.querySelector("#exportDraft,#exportConfig"),r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})())'),'Sidebar export action unreachable')
        js('document.querySelector(".parameter-panel,main>aside").scrollTop=0')
    if js('JSON.stringify(document.documentElement.dataset.theme)')!='light':
        js('document.getElementById("themeToggle").focus()');call('press','Enter');time.sleep(.3)
    check(js('JSON.stringify(document.documentElement.dataset.theme==="light")'),'Light theme not applied')
    call('screenshot',OUT/f'{name}-light-1280.png')
    js('document.getElementById("themeToggle").focus()');call('press','Enter')
    call('reload');call('wait','--load','networkidle')
    check(js('JSON.stringify(document.documentElement.scrollWidth<=document.documentElement.clientWidth+1)'),'Reload overflow')
    errors=call('errors');check(not errors,errors)
    checks.append({'page':name,'light_theme':True,'ordinary_reload':True,'console_errors':errors})
(OUT/'extra.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print('Final A action layout/run, sidebar export reachability, themes and ordinary reload passed.')
