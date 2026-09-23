const acceptedPromise=page.waitForResponse(r=>r.url().endsWith('/api/jobs')&&r.request().method()==='POST');
await page.getByRole('button',{name:'提交仿真',exact:true}).click();
const job=await (await acceptedPromise).json();
await expect(page.locator('#resultStatus')).toContainText('C_pulse_resolved_scan',{timeout:30000});
await expect(page.locator('#scanViewStatus')).toContainText('实际采集记录');
await expect(page.locator('#error')).toBeHidden();
await expect(page.locator('.katex-error')).toHaveCount(0);
await page.locator('#scanPanel').scrollIntoViewIfNeeded();
return {job:job.id,errors:globalThis.scanErrors,summary:await page.locator('#scanMetrics').innerText(),katexCount:await page.locator('#opticalResults .katex').count(),screenshot:await page.screenshot({fullPage:false})};
