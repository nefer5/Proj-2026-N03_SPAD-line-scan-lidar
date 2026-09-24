const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.setViewportSize({width:1440,height:1000});
await page.goto('http://127.0.0.1:8016/system',{waitUntil:'networkidle'});
return {errors,ready:await page.locator('body').getAttribute('data-ready'),error:await page.locator('#loadingError').innerText(),groups:await page.locator('.parameter-group').count(),headings:await page.locator('h2').allTextContents(),response:await page.locator('#resultViewState').innerText()};