await page.setViewportSize({width:1720,height:1140});
const blocks=await page.locator('.crosstalk-layout>div').evaluateAll(nodes=>nodes.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})));
assert(blocks[1].w/blocks[0].w>2.6);
await page.locator('#crosstalkReference').selectOption('4');
await expect(page.locator('#crosstalkSpatial .reference')).toHaveAttribute('data-reference-channel','4');
await page.locator('#crosstalkPanel').scrollIntoViewIfNeeded();
globalThis.crosstalkLayout=blocks;
return await page.screenshot({fullPage:false});
