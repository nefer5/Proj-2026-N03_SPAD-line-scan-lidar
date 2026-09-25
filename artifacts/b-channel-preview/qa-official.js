const official=await context.newPage();let stored;
try{
 await official.goto('http://127.0.0.1:8016/system?job=eff344ee56f24799876b5df6a08fa3e2',{waitUntil:'networkidle'});await official.waitForFunction(()=>document.body.dataset.ready==='true');
 stored=await official.evaluate(()=>({draft:localStorage.getItem('spad-system-modular-v3'),open:localStorage.getItem('spad-system-modular-v3-open')}));
 const h=official.locator('[data-path="optics.channels_h"]');if(!await h.isVisible())await official.locator('[data-group="readout"]>summary').click();
 await expect(official.locator('#readoutLayoutSummary')).toContainText('16 × 32');await expect(official.locator('#readoutLayoutSummary')).toContainText('8 个通道');
 await h.fill('2');await h.press('Tab');await expect(official.locator('#readoutLayoutSummary')).toContainText('32 × 32');await expect(official.locator('#readoutLayoutSummary')).toContainText('16 个通道');await expect(official.locator('#readoutLayoutSummary')).toContainText('已采集结果仍使用：');await expect(official.locator('#arraySummary')).toContainText('16 × 32');
 const changed=await official.locator('#readoutLayoutSummary').innerText();
 await h.fill('0');await h.press('Tab');await expect(official.locator('#readoutLayoutSummary')).toContainText('输入未通过校验');
 await h.fill('1');await h.press('Tab');await expect(official.locator('#readoutLayoutSummary')).not.toContainText('输入未通过校验');
 await official.reload({waitUntil:'networkidle'});await official.waitForFunction(()=>document.body.dataset.ready==='true');await expect(official.locator('#readoutLayoutSummary')).toContainText('16 × 32');
 const hash=await official.locator('script[src*="/static/system.js"]').getAttribute('src');assert(/\?v=[a-f0-9]{64}$/.test(hash));
 const headers=(await official.request.get('http://127.0.0.1:8016/system')).headers();assert(headers['cache-control'].includes('no-store'));
 return {changed,restored:await official.locator('#readoutLayoutSummary').innerText(),hash,cache:headers['cache-control']};
}finally{if(stored)await official.evaluate(s=>{for(const [key,value] of [['spad-system-modular-v3',s.draft],['spad-system-modular-v3-open',s.open]]){if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);}},stored);await official.close();}