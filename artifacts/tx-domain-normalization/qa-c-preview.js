const scratch=await context.newPage();
try{
 await scratch.setViewportSize({width:1600,height:1020});
 await scratch.goto('http://127.0.0.1:8016/system/scan',{waitUntil:'domcontentloaded'});
 const section=scratch.locator('#parameterVisuals');
 await section.locator('summary').click();
 await expect(scratch.locator('#figureSelect option[value="tx_profile"]')).toHaveCount(1,{timeout:30000});
 await scratch.locator('#figureSelect').selectOption('tx_profile');
 await expect(scratch.locator('#figureNote')).toContainText('角域内能量份额总和为 1',{timeout:30000});
 await expect(scratch.locator('#figureFacts')).toContainText('域内单发能量 · Tx前');
 await section.scrollIntoViewIfNeeded();
 return await scratch.screenshot({fullPage:false});
}finally{await scratch.close();}
