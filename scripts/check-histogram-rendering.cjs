/* Display regression checks: integer tick positions and stable shared scales. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const sandbox={window:{devicePixelRatio:1}};
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/shared/histogram-window.js'),'utf8'),sandbox);
const plot=sandbox.PhotonHistogram;
for(const required of [0,.01,.9,1,2.3,6.9,54.1,216.9,249.5,10987,1e8]){
 const axis=plot.countAxis(required);
 assert(axis.max>=required);
 assert(axis.ticks.every(Number.isInteger));
 assert(axis.ticks.length>=2&&axis.ticks.length<=6);
 assert.equal(axis.ticks[0],0);assert.equal(axis.ticks.at(-1),axis.max);
 assert.equal(plot.countAxis(axis.max).max,axis.max);
}
const data={histogram:{time_ns:[.5,1.5,2.5,3.5],edges_ns:[0,1,2,3,4],counts:[[1,20,2,100],[10,0,0,1]]}};
const layers={observed:true};
const a=plot.scales(data,[0,1],[0,1],layers,true),b=plot.scales(data,[0,1],[3,4],layers,true);
assert.equal(a[0].max,a[1].max);assert.equal(a[0].max,b[0].max);
const local=plot.scales(data,[0,1],[0,1],layers,false);
assert(local[0].max<local[1].max);assert(local[0].max<a[0].max);
assert.equal(plot.scales(data,[0],[0,1],layers,true)[0].max,a[0].max);
const labels=[],bars=[];
const context={scale(){},clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},save(){},rect(){},clip(){},restore(){},
 fillRect(...v){bars.push(v)},fillText(text,x,y){if(x<43)labels.push({text,y})}};
const canvas={width:0,height:0,dataset:{},getBoundingClientRect:()=>({width:600,height:240}),getContext:()=>context};
plot.draw(canvas,data,0,[0,1],2.3,layers);
assert.deepEqual(labels.map(x=>x.text),['0','1','2','3']);
assert.equal(canvas.dataset.yMax,'3');
assert.equal(canvas.dataset.yTicks,'[0,1,2,3]');
// The count=1 bar reaches the actual tick=1 coordinate, not a rounded fractional label.
assert(Math.abs(bars[0][1]-(labels[1].y-3))<1e-10);
console.log('Integer grid positions, bar alignment, shared full-gate scales and local scaling passed.');
