// Regression for the reported stale-JS bug: enums must survive JSON serialization.
const fs=require("node:fs"), vm=require("node:vm"), assert=require("node:assert/strict");
const path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"../web/app.js"),"utf8");
const fields=[
  {tagName:"SELECT",dataset:{key:"pulse_shape"},value:"gaussian",options:[{value:"gaussian"},{value:"rectangular"}]},
  {tagName:"SELECT",dataset:{key:"rx_aperture_shape"},value:"circle",options:[{value:"circle"},{value:"ellipse"},{value:"rectangle"}]},
  {tagName:"INPUT",dataset:{key:"laser_shots"},value:"100"},
];
const context=vm.createContext({location:{pathname:"/"},document:{querySelectorAll:()=>fields}});
vm.runInContext(source.slice(0,source.indexOf("function fmt(")),context);
let result=JSON.parse(JSON.stringify(context.collectConfig()));
assert.equal(result.pulse_shape,"gaussian");
assert.equal(result.rx_aperture_shape,"circle");
assert.equal(result.laser_shots,100);
fields[0].value="rectangular";fields[1].value="ellipse";
result=JSON.parse(JSON.stringify(context.collectConfig()));
assert.equal(result.pulse_shape,"rectangular");
assert.equal(result.rx_aperture_shape,"ellipse");
fields[1].value="";
assert.throws(()=>context.collectConfig(),/选择有效选项/);
fields[1].value="circle";fields[2].value="NaN";
assert.throws(()=>context.collectConfig(),/整数/);
console.log("Form serialization regression passed: enums stay strings; invalid input rejected before POST.");
vm.runInContext(source.slice(source.indexOf("function parseFilterPoints("),source.indexOf("function syncFilterEditor(")),context);
const csv=context.parseFilterPoints("wavelength_nm,transmission\n930,0\n940,0.8\n950,0");
const manual=context.parseFilterPoints("930 0\n940\t0.8\n950 0");
assert.deepEqual(JSON.parse(JSON.stringify(csv)),JSON.parse(JSON.stringify(manual)));
for(const invalid of ["930,,0\n940,0.8","930,0\n940,Infinity","930,0"]) {
  assert.throws(()=>context.parseFilterPoints(invalid));
}
fields[2].value="100";vm.runInContext("filterDraftDirty=true",context);
assert.throws(()=>context.collectConfig(),/未应用/);
assert.equal(context.collectConfig(true).laser_shots,100);
console.log("Sparse-point parser and unapplied-edit checks passed.");
