globalThis.scanErrors=[];page.on('pageerror',e=>globalThis.scanErrors.push(e.message));
await page.setViewportSize({width:1440,height:1050});
await page.goto('http://127.0.0.1:8014/system/scan',{waitUntil:'networkidle'});
await page.getByRole('button',{name:'预览轨迹与发数',exact:true}).click();
await expect(page.locator('#scanViewStatus')).toContainText('仅预览时序');
return {errors:globalThis.scanErrors,summary:await page.locator('#scanMetrics').innerText(),fields:await page.locator('#fields').innerText(),error:await page.locator('#error').innerText()};
