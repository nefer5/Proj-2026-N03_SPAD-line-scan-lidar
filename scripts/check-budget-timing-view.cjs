/* Viewport arithmetic only: no hardware calculations or duplicate fixtures. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({document:{addEventListener(){}},BudgetNumbers:{format:String}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../web/budget-pipeline.js'),'utf8'),context);
const View=context.BudgetPipelineViews.TimelineViewport,view=new View();
view.ensure('a',1000);view.zoom(.5,.3);
assert.equal(view.lo,150);assert.equal(view.hi,650);
assert.equal(view.lo+(view.hi-view.lo)*.3,300); // cursor anchor remains the same time
view.pan(-10000);assert.equal(view.lo,0);assert.equal(view.hi,500);
view.pan(10000);assert.equal(view.lo,500);assert.equal(view.hi,1000);
for(let i=0;i<30;i++)view.zoom(.5,.5);
assert.ok(Math.abs(view.hi-view.lo-1000/128)<1e-10);
view.ensure('a',1000);assert.ok(view.hi-view.lo<1000); // same result retains view
view.ensure('b',1000);assert.equal(view.lo,0);assert.equal(view.hi,1000); // new config resets it
view.set(0,1000);assert.equal(view.hi,1000);
assert.throws(()=>view.ensure('c',NaN),/时间范围/);
console.log('Timing viewport anchors, pan limits, zoom limits and result reset verified.');
