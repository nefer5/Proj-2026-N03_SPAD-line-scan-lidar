const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewportSize({width:1536,height:1120});
await page.goto('http://127.0.0.1:8016/system?job=2df4628cf5524ab39fdef12de95cc607',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await expect(page.locator('#noiseReferenceLabel')).toHaveText('理想噪声基线');await expect(page.locator('#statisticsNote')).toContainText('10 次含噪统计');await expect(page.locator('#statisticsNote')).toContainText('无额外采集');await expect(page.locator('[data-series="error"]')).toBeEnabled();
await page.locator('#channelInput').fill('3,4');await page.locator('#applyChannels').click();
await expect(page.locator('#histogramPlots')).toContainText('未计读出损失');
const oldBin=+(await page.locator('#replayBin').inputValue());await page.locator('#replayBin').fill(String(oldBin*2));
const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/replay')&&r.request().method()==='POST'),page.locator('#replayRecords').click()]);const replay=await response.json();assert.equal(replay.noise_reference.counts_per_bin[3],71.69978580305524);
await expect(page.locator('#replayState')).toContainText('已重放');
await page.evaluate(()=>{globalThis.exportProbe={original:URL.createObjectURL};URL.createObjectURL=function(blob){globalThis.exportProbe.blob=blob;return globalThis.exportProbe.original.call(URL,blob);};});
let csv;try{await page.locator('#exportHistogram').click();csv=await page.evaluate(async()=>await globalThis.exportProbe.blob.text());}finally{await page.evaluate(()=>{URL.createObjectURL=globalThis.exportProbe.original;delete globalThis.exportProbe;});}
const lines=csv.trim().split('\n');assert(lines[0].includes('ideal_noise_reference_counts_per_bin'));assert.equal(+lines[1].split(',')[4],replay.noise_reference.counts_per_bin[3]);
await page.locator('#histogramPlots').scrollIntoViewIfNeeded();await page.evaluate(()=>scrollBy(0,150));
const shot=await page.screenshot({fullPage:false});
await page.goto('http://127.0.0.1:8016/system?job=eff344ee56f24799876b5df6a08fa3e2',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await expect(page.locator('#noiseReferenceLabel')).toHaveText('纯噪声输出均值');await expect(page.locator('#statisticsNote')).toContainText('24 次关激光');await expect(page.locator('#noiseReferenceExplanation')).toContainText('独立重复采集');
await page.goto('http://127.0.0.1:8016/system?job=2df4628cf5524ab39fdef12de95cc607',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');await page.locator('#channelInput').fill('3,4');await page.locator('#applyChannels').click();
await page.setViewportSize({width:390,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.setViewportSize({width:1536,height:1120});await page.locator('#histogramPlots').scrollIntoViewIfNeeded();
assert.equal(errors.length,0,errors.join('\n'));return {errors,binPs:replay.noise_reference.bin_ps,noiseLevel:replay.noise_reference.counts_per_bin[3],csvHeader:lines[0],csvRows:lines.length-1,historicalPreserved:true,screenshot:shot};