const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.setViewportSize({width:1440,height:1050});
await page.goto('http://127.0.0.1:8015/static/prototypes/b-optics/index.html',{waitUntil:'networkidle'});
await page.waitForFunction(()=>document.body.dataset.ready==='true');
await page.getByRole('button',{name:'全部折叠',exact:true}).click();
await page.locator('[data-group="rx"]>summary').click();
await expect(page.getByRole('spinbutton',{name:'水平等效焦距 f_H',exact:true})).toHaveValue('20');
await expect(page.getByRole('spinbutton',{name:'垂直等效焦距 f_V',exact:true})).toHaveValue('20');
await page.locator('#parameterVizDetails>summary').click();
assert.equal(await page.getByRole('tab').count(),10);
for(const title of ['Tx 波形','滤光片','太阳光','环境光合成','PDE / FF','综合光谱响应','Tx 角分布','Rx H/V 映射','PSF 剖面','采集时序']){
 await page.getByRole('tab',{name:title,exact:true}).click();
 await expect(page.getByRole('tab',{name:title,exact:true})).toHaveAttribute('aria-selected','true');
}
await page.getByRole('tab',{name:'Rx H/V 映射',exact:true}).click();
await expect(page.locator('#parameterMappingFormula .katex')).toBeVisible();
await page.locator('#parameterVizPanel').scrollIntoViewIfNeeded();
const snapshot=await page.evaluate(()=>({defaults:{shots:base.timing.laser_shots,sun:base.optics.solar_enabled,other:base.optics.other_light_enabled},plotAxes:[...document.querySelectorAll('.heatmap svg')].map(s=>[...s.querySelectorAll('text')].map(t=>t.textContent).filter(t=>t.includes('↑'))),invalidRectangles:[...document.querySelectorAll('.heatmap rect')].filter(el=>Number(el.getAttribute('height'))<0).length,hasOldFocal:!!document.querySelector('[data-path="optics.focal_length_mm"]')}));
return {errors,snapshot,figureTabs:await page.getByRole('tab').allTextContents(),screenshot:await page.screenshot({fullPage:false})};