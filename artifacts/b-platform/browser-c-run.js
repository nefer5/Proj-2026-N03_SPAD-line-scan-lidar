const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.setViewportSize({width:1440,height:1000});await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await page.getByRole('button',{name:'载入快速扫描示例',exact:true}).click();await page.waitForFunction(()=>previewData.resource_probe&&!previewData.resource_probe.blocked);
await page.getByRole('spinbutton',{name:'采集帧数',exact:true}).fill('2');await page.getByRole('spinbutton',{name:'采集帧数',exact:true}).press('Tab');await page.waitForFunction(()=>previewData.form_configuration.scan.frame_count===2);
await page.getByRole('button',{name:'提交仿真',exact:true}).click();await page.waitForFunction(()=>!!currentJob);
return {job:await page.evaluate(()=>currentJob),errors,previewFrames:await page.evaluate(()=>previewData.scan_preview.assigned_pulses_per_frame_bin.length),status:await page.locator('.job-state').innerText()};