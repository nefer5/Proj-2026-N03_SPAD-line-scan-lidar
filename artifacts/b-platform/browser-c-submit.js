await page.locator('#runPreview').click();await page.waitForFunction(()=>!!currentJob);
return {job:await page.evaluate(()=>currentJob),status:await page.locator('.job-state').innerText()};