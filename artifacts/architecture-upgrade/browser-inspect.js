await page.goto('http://127.0.0.1:8012/spad', {waitUntil:'networkidle'});
return {url:page.url(),text:await page.locator('body').innerText(),errors:await page.locator('#error').innerText()};
