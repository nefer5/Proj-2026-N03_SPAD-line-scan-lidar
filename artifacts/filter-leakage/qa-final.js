await page.setViewportSize({width:1720,height:1140});
// Reload proves that current fingerprinted assets and migrated config work.
await page.reload({waitUntil:'domcontentloaded'});
await expect(page.locator('#resultViewState')).toContainText('a14ee4ff9c794ffe84761a6539482808',{timeout:30000});
const rx=page.locator('[data-group="rx"]');if(!await rx.evaluate(e=>e.open))await rx.locator(':scope>summary').click();
const filter=page.locator('details.subdetails').filter({has:page.locator('#curve-filter')});
if(!await filter.evaluate(e=>e.open))await filter.locator(':scope>summary').click();
await expect(page.locator('#filterBasic_out_of_band_transmission')).toHaveValue('0.001');
await page.locator('#filterBasic_out_of_band_transmission').fill('0.0011');await page.locator('#filterBasic_out_of_band_transmission').press('Tab');
await page.locator('#filterBasic_out_of_band_transmission').fill('0.001');await page.locator('#filterBasic_out_of_band_transmission').press('Tab');
await page.waitForFunction(()=>previewData?.form_configuration.spectral_inputs.filter.basic.out_of_band_transmission===.001&&previewData?.parameter_figures.filter.note.includes('图中聚焦基础形状范围'),null,{timeout:30000});
const plot=await page.evaluate(()=>previewData.parameter_figures.filter.series[0].x);
assert(Math.max(...plot)<1200);
const sun=page.locator('#rangesAndFlow details').filter({hasText:'太阳：按明确波段积分并映射到像素'});
const other=page.locator('#rangesAndFlow details').filter({hasText:'其他环境光：独立输入谱的空间积分'});
for(const section of [sun,other])if(!await section.evaluate(e=>e.open))await section.locator(':scope>summary').click();
assert.equal(await page.locator('.katex-error').count(),0);
await sun.evaluate(e=>e.scrollIntoView({block:'start'}));
return await page.screenshot({fullPage:false});
