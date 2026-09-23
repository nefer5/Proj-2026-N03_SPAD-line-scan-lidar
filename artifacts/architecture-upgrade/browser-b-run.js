await page.goto('http://127.0.0.1:8012/system',{waitUntil:'networkidle'});
await expect(page.locator('[data-path="optics.tx_model"]')).toHaveValue('gaussian');
await page.getByRole('button',{name:'提交仿真',exact:true}).click();
await expect(page.locator('#resultStatus')).toContainText('B_full_spot_static',{timeout:30000});
await expect(page.locator('#error')).toBeHidden();
await expect(page.locator('.synthetic-note')).toContainText('构造光学样例');
await page.evaluate(()=>window.scrollTo(0,0));
return {errors:globalThis.labErrors,metrics:await page.locator('#metrics').innerText(),status:await page.locator('#resultStatus').innerText(),screenshot:await page.screenshot({fullPage:false})};
