const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await page.getByRole('button',{name:'全部折叠',exact:true}).click();await page.locator('[data-group="rx"]>summary').click();
const h=page.getByRole('spinbutton',{name:'水平等效焦距 f_H',exact:true}),v=page.getByRole('spinbutton',{name:'垂直等效焦距 f_V',exact:true});
await h.fill('30');await h.press('Tab');await expect(v).toHaveValue('20');await expect(page.locator('#staleBanner')).toBeVisible();
await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');await expect(h).toHaveValue('30');await expect(v).toHaveValue('20');
await page.getByRole('button',{name:'恢复默认',exact:true}).click();await expect(h).toHaveValue('20');
const versionCheck=await page.evaluate(()=>({current:base.timing.laser_shots,legacy:JSON.parse(localStorage.getItem('spad-b-ui-preview-v1')||'null')?.timing?.laser_shots,version:document.querySelector('.preview-badge b').textContent,assets:[...document.querySelectorAll('script[src],link[rel="stylesheet"]')].every(el=>(el.src||el.href).includes('?v='))}));
const widths=[];
for(const width of [1440,1024,768,390]){await page.setViewportSize({width,height:1000});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);widths.push(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth})));}
await page.locator('#parameterVizDetails>summary').click();await page.getByRole('tab',{name:'环境光合成',exact:true}).click();await page.locator('#parameterVizPanel').scrollIntoViewIfNeeded();
const screenshot=await page.screenshot({fullPage:false});
await page.setViewportSize({width:1440,height:1000});
await page.getByRole('tab',{name:'Tx 波形',exact:true}).click();
await page.evaluate(()=>window.scrollTo(0,0));
return {errors,versionCheck,widths,independentFocals:true,draftPersistence:true,screenshot};