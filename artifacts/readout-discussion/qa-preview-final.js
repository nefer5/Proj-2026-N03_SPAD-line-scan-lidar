const preview=await context.newPage();try{
await preview.goto('http://127.0.0.1:8016/static/prototypes/slot-readout/index.html',{waitUntil:'networkidle'});await preview.waitForFunction(()=>document.body.dataset.ready==='true');
await expect(preview.locator('#statisticsPolicy')).toContainText('默认共10次');await expect(preview.locator('#statisticsPolicy')).toContainText('每通道一个标量');
await preview.setViewportSize({width:1536,height:1120});
return {screenshot:await preview.screenshot({fullPage:true})};
}finally{await preview.close();}