const errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
await page.goto('http://127.0.0.1:8016/static/prototypes/c-exposure/index.html',{waitUntil:'networkidle'});
await page.waitForFunction(()=>document.body.dataset.ready==='true');
await page.getByRole('tab',{name:/时间资源与读出带宽/}).click();await expect(page.locator('#planningWorkspace')).toBeVisible();
await page.getByRole('button',{name:'双缓冲候选',exact:true}).click();await expect(page.locator('#pipelineDiagram')).toContainText('缓冲 B');
await page.getByRole('button',{name:'时间直方图',exact:true}).click();await expect(page.getByLabel('每计数位宽 / bit',{exact:true})).toBeVisible();
await page.getByRole('button',{name:'原始时间戳',exact:true}).click();await expect(page.getByLabel('每条事件记录 / byte',{exact:true})).toHaveValue('');
await page.getByLabel('接口净速率 / Mbit·s⁻¹',{exact:true}).fill('1000');await expect(page.locator('.budget-result')).toContainText('不能给出可信');
await page.getByRole('button',{name:'点云结果',exact:true}).click();assert.equal(await page.getByLabel('接口净速率 / Mbit·s⁻¹',{exact:true}).inputValue(),'1000');
await page.getByRole('button',{name:'恢复参考',exact:true}).click();assert.equal(await page.getByLabel('接口净速率 / Mbit·s⁻¹',{exact:true}).inputValue(),'');
await page.setViewportSize({width:390,height:844});
const mobilePlanning=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));assert(mobilePlanning.width<=mobilePlanning.viewport);
await page.getByRole('tab',{name:/曝光策略与跨列影响/}).click();const mobileExposure=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));assert(mobileExposure.width<=mobileExposure.viewport);
await page.setViewportSize({width:1536,height:1100});await page.getByRole('tab',{name:/时间资源与读出带宽/}).click();
await page.locator('#planningWorkspace').evaluate(el=>el.scrollIntoView({block:'start'}));
const probe={};for(const kind of ['system','scan']){const r=await context.request.get('http://127.0.0.1:8016/api/experiments/'+kind);const d=await r.json();probe[kind]={H:d.defaults.spad.channels_h,V:d.defaults.spad.channels_v,cache:r.headers()['cache-control']};}
assert.equal(posts.length,0);assert.equal(errors.length,0);
return {errors,posts,probe,mobilePlanning,mobileExposure,checks:'planning tabs, output formats, blank unknown fields, draft retention and reset, mobile overflow passed',screenshot:await page.screenshot({fullPage:false})};