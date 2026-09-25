const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.evaluate(()=>{globalThis.exportProbe={original:URL.createObjectURL};URL.createObjectURL=function(blob){globalThis.exportProbe.blob=blob;return globalThis.exportProbe.original.call(URL,blob);};});
let csv;
try{await page.locator('#exportHistogram').click();csv=await page.evaluate(async()=>globalThis.exportProbe.blob?await globalThis.exportProbe.blob.text():null);}finally{await page.evaluate(()=>{URL.createObjectURL=globalThis.exportProbe.original;delete globalThis.exportProbe;});}
assert(csv,'Export did not generate CSV');const rows=csv.trim().split('\n');const totals={};for(const row of rows.slice(1)){const fields=row.split(',');totals[fields[0]]=(totals[fields[0]]||0)+Number(fields[2]);}
assert.equal(rows.length,4097);assert.equal(totals['3'],4898);assert.equal(totals['4'],4845);
await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await page.locator('#channelInput').fill('3,4');await page.locator('#applyChannels').click();
await page.setViewportSize({width:390,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await page.locator('#channelLocator').scrollIntoViewIfNeeded();
const responsive=await page.locator('#channelLocator').evaluate(el=>({width:el.getBoundingClientRect().width,columns:getComputedStyle(el.querySelector('.cl-layout')).gridTemplateColumns}));
await page.setViewportSize({width:1536,height:1180});await page.locator('[data-map-channel="4"]').hover();
await page.evaluate(()=>scrollTo(0,document.querySelector('#histogramPanel').getBoundingClientRect().top+scrollY-15));await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
assert.equal(errors.length,0,errors.join('\n'));
return {errors,csv:{header:rows[0],rows:rows.length-1,totals},responsive,screenshot:await page.screenshot({fullPage:false})};