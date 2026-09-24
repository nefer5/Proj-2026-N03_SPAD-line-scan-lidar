const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.setViewportSize({width:1440,height:1000});await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
await page.getByRole('button',{name:'全部展开',exact:true}).click();
await page.locator('#pdeCurveMode').selectOption('manual');await page.locator('#pdeCurvePoints').fill('900,0.2\n910,0.2');await page.locator('#pdeApplyCurve').click();
await page.waitForFunction(()=>previewData.form_configuration.spectral_inputs.pde.mode==='manual'&&previewData.form_configuration.spectral_inputs.pde.manual_points.length===2);
const modes=await page.evaluate(()=>({mode:previewData.form_configuration.spectral_inputs.pde.mode,csv:previewData.form_configuration.spectral_inputs.pde.csv_points.length,manual:previewData.form_configuration.spectral_inputs.pde.manual_points.length}));
assert.equal(modes.manual,2);assert(modes.csv>2);
await page.locator('#importConfiguration').setInputFiles('E:/Proj-2026-N03_SPAD线扫lidar建模/artifacts/b-platform/config-import.json');
await page.waitForFunction(()=>previewData.form_configuration.optics.range_m===110);
await page.locator('#importOpticalData').setInputFiles('E:/Proj-2026-N03_SPAD线扫lidar建模/artifacts/b-platform/optical-import.json');
await page.waitForFunction(()=>previewData.form_configuration.optics.rx_model==='dataset');
const imported=await page.evaluate(()=>({model:draft.optics.rx_model,version:draft.optics.dataset.schema_version,convention:draft.optics.dataset.coordinate_convention}));
await page.getByRole('button',{name:'恢复默认',exact:true}).click();await page.waitForFunction(()=>previewData.form_configuration.optics.rx_model==='gaussian_psf'&&previewData.form_configuration.optics.range_m===100);
const checks=[];
const scratch=await context.newPage();
try{
 for(const path of ['/spad','/system/scan']){await scratch.goto('http://127.0.0.1:8016'+path,{waitUntil:'networkidle'});await scratch.getByRole('button',{name:'全部折叠',exact:true}).click();assert.equal(await scratch.locator('.controls details[open]').count(),0);await scratch.getByRole('button',{name:'全部展开',exact:true}).click();checks.push({path,expanded:await scratch.locator('.controls details[open]').count()});}
 await scratch.goto('http://127.0.0.1:8016/',{waitUntil:'networkidle'});const aErrors=[];scratch.on('pageerror',e=>aErrors.push(String(e)));await scratch.getByRole('button',{name:'运行仿真',exact:true}).click();await scratch.waitForFunction(()=>typeof lastResult!=='undefined'&&!!lastResult);checks.push({path:'/',errors:aErrors,sharedRenderer:await scratch.evaluate(()=>typeof PhotonHistogram.draw==='function'),histogramWidth:await scratch.locator('#histZoom').getAttribute('width')});
}finally{await scratch.close();}
return {errors,modes,imported,checks};