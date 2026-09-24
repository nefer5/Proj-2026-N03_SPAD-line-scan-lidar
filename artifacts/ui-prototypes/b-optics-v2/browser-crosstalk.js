const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.getByLabel('角度H索引',{exact:true}).selectOption('15');
await page.getByLabel('角度V索引',{exact:true}).selectOption('7');
await expect(page.locator('#crosstalkAngle')).toContainText('H[15]');
const facts=await page.evaluate(()=>{
 const idx=selectedV*(data.optics.tx_h_edges_mrad.length-1)+selectedH,p=data.angle_psfs[idx],xe=data.x_edges_um,ye=data.y_edges_um;
 let total=0,x=0,y=0;p.forEach((row,v)=>row.forEach((n,h)=>{total+=n;x+=n*(xe[h]+xe[h+1])/2;y+=n*(ye[v]+ye[v+1])/2;}));
 const top=Number(document.querySelector('#anglePlot .cell[data-x="0"][data-y="8"]').getAttribute('y'));
 const bottom=Number(document.querySelector('#anglePlot .cell[data-x="0"][data-y="0"]').getAttribute('y'));
 return {h:data.optics.angular_h_centers_mrad[idx],v:data.optics.angular_v_centers_mrad[idx],x:x/total,y:y/total,positiveAtTop:top<bottom,strongest:data.crosstalk.strongest_channel[idx],matrixSize:data.crosstalk.matrix_db[idx].length,zeroReference:data.optics.angle_to_channel_fraction[idx].findIndex(v=>v===0),pickerOrder:[...document.querySelectorAll('#channelPicker button')].map(el=>el.dataset.channel)};
});
assert(facts.x<0&&facts.y<0&&facts.h>0&&facts.v>0);assert(facts.positiveAtTop);
await expect(page.locator('#crosstalkFormula .katex')).toBeVisible();
await page.getByLabel('串扰参考通道',{exact:true}).selectOption('1');
await expect(page.locator('.db-cell.reference')).toContainText('CH 1');
await expect(page.locator('.db-cell.reference strong')).toContainText('0');
if(facts.zeroReference>=0){await page.getByLabel('串扰参考通道',{exact:true}).selectOption(String(facts.zeroReference));await expect(page.locator('#crosstalkScale')).toContainText('未定义');}
await page.getByLabel('串扰参考通道',{exact:true}).selectOption('auto');
await page.locator('#crosstalkPanel').scrollIntoViewIfNeeded();
return {errors,facts,matrixCells:await page.locator('.db-table td').count(),reference:await page.locator('.db-cell.reference').innerText(),screenshot:await page.screenshot({fullPage:false})};