const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.setViewportSize({width:1536,height:1100});
await page.goto('http://127.0.0.1:8016/static/prototypes/c-exposure/index.html',{waitUntil:'networkidle'});
await page.waitForFunction(()=>document.body.dataset.ready==='true');
const state=await page.evaluate(()=>({title:document.title,columns:document.querySelectorAll('#columnSelect option').length,rows:document.querySelectorAll('#rowSelect option').length,hRoutes:document.querySelectorAll('#hRoute option').length,overflow:document.documentElement.scrollWidth>innerWidth,assets:[...document.querySelectorAll('link[rel="stylesheet"],script[src]')].map(x=>x.href||x.src)}));
const defaults=await context.request.get('http://127.0.0.1:8016/api/experiments/scan');const d=await defaults.json();
return {state,errors,defaults:{cache:defaults.headers()['cache-control'],spad:d.defaults?.spad,formSpad:d.form_defaults?.spad},screenshot:await page.screenshot({fullPage:false})};