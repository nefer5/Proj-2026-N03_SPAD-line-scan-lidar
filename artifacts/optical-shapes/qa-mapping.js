await page.goto('http://127.0.0.1:8016/system?job=90e9141e1ad34cf3b21a693788a1de41',{waitUntil:'domcontentloaded'});
await page.setViewportSize({width:1720,height:1140});
await page.waitForFunction(()=>document.body.dataset.ready==='true',null,{timeout:30000});
await expect(page.locator('canvas[data-hist]').first()).toBeAttached({timeout:30000});
const histHeight=await page.locator('canvas[data-hist]').first().evaluate(e=>e.getBoundingClientRect().height);
assert.equal(histHeight,360);
const layout=await page.locator('#mappingPanel').evaluate(root=>{
 const b=id=>{const r=root.querySelector(id).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}};
 return {angle:b('#anglePlot'),channels:b('#channelFractions'),psf:b('#psfPlot')};
});
assert(layout.channels.y>layout.angle.y);assert(layout.psf.x>layout.angle.x);
assert(layout.psf.h>layout.angle.h*1.8);
globalThis.shapeLayout={...layout,histHeight};
await page.locator('#mappingPanel').scrollIntoViewIfNeeded();
return await page.screenshot({fullPage:false});
