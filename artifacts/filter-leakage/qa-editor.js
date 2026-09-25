await page.setViewportSize({width:1720,height:1140});
globalThis.leakErrors=[];page.on('pageerror',e=>globalThis.leakErrors.push(e.message));
await page.goto('http://127.0.0.1:8016/system?job=3440493ef4be44c98130ae74e1451805',{waitUntil:'domcontentloaded'});
await expect(page.locator('#resultViewState')).toContainText('3440493ef4be44c98130ae74e1451805',{timeout:30000});
const rx=page.locator('[data-group="rx"]');if(!await rx.evaluate(e=>e.open))await rx.locator(':scope>summary').click();
const filter=page.locator('details.subdetails').filter({has:page.locator('#curve-filter')});
if(!await filter.evaluate(e=>e.open))await filter.locator(':scope>summary').click();
await expect(page.locator('#filterBasic_out_of_band_transmission')).toHaveValue('0');
assert.equal(await page.locator('#pdeBasic_out_of_band_transmission').count(),0);
assert.equal(await page.locator('#otherBasic_out_of_band_transmission').count(),0);
const weights=await page.locator('details.subdetails>summary').evaluateAll(nodes=>nodes.map(e=>getComputedStyle(e).fontWeight));
assert(weights.every(w=>Number(w)>=650));
for(const shape of ['constant','gaussian','cosine_flat','rectangle']){
 await page.locator('#filterBasicShape').selectOption(shape);
 await expect(page.locator('#filterBasic_out_of_band_transmission')).toBeVisible();
}
await page.locator('#filterBasic_out_of_band_transmission').fill('0.001');
await page.locator('#filterBasic_out_of_band_transmission').press('Tab');
await page.waitForFunction(()=>previewData?.form_configuration.spectral_inputs.filter.basic.out_of_band_transmission===.001&&previewData?.form_configuration.spectral_inputs.filter.basic.shape==='rectangle',null,{timeout:30000});
globalThis.leakPreview=await page.evaluate(()=>({budget:previewData.optics.budget,domain:previewData.optics.spectral_integration.domain,storage:previewData.optics.spectral_integration.storage}));
assert.equal(globalThis.leakPreview.domain.band_nm[0],280);assert.equal(globalThis.leakPreview.domain.band_nm[1],4000);
await page.locator('#filterBasic_out_of_band_transmission').scrollIntoViewIfNeeded();
const visualization=page.locator('#parameterVizDetails');if(!await visualization.evaluate(e=>e.open))await visualization.locator(':scope>summary').click();
await page.getByRole('tab',{name:'滤光片',exact:true}).click();
await page.locator('#parameterVizPanel').scrollIntoViewIfNeeded();
return await page.screenshot({fullPage:false});
