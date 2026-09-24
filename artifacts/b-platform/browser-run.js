const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.getByRole('button',{name:/提交仿真/,exact:false}).click();
await page.waitForFunction(()=>typeof currentJob==='string'&&currentJob.length>0);
return {job:await page.evaluate(()=>currentJob),errors,status:await page.locator('.job-state').innerText()};