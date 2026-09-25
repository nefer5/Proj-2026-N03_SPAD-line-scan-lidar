await page.goto('http://127.0.0.1:8016/static/prototypes/slot-readout/index.html',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await expect(page.locator('#statisticsPolicy')).toContainText('已经接入');
assert.equal(await page.locator('#statisticsPolicy tbody tr').count(),4);
await page.locator('#collapseAll').click();assert.equal(await page.locator('details[open]').count(),0);await page.locator('#expandAll').click();assert.equal(await page.locator('details[open]').count(),3);
await page.setViewportSize({width:390,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await page.setViewportSize({width:1536,height:1120});await page.locator('#statisticsPolicy').scrollIntoViewIfNeeded();
return {title:await page.title(),screenshot:await page.screenshot({fullPage:true})};