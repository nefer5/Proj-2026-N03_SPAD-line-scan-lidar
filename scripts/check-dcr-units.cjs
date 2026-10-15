const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../web/shared/units.js'),'utf8'),context);
const u=context.LidarUnits;
for(const path of ['dcr_cps_per_spad','device.dcr_cps_per_spad','spad.dcr_cps_per_spad','system.spad.dcr_cps_per_spad']){
 assert.equal(u.display(4000000,path),4000);
 assert.equal(u.canonical(4000,path),4000000);
 assert.equal(u.canonical(1.25,path),1250);
 assert.equal(u.display(400000,path),400); // old stored cps remain cps
 assert.equal(u.unit(path,'cps'),'kHz');
 assert.throws(()=>u.canonical(1e308,path),/有限/);
}
assert.equal(u.display(6,'laser_shots'),6);
assert.equal(u.canonical(6,'laser_shots'),6);
console.log('DCR kHz display / canonical cps round-trip and legacy stored values passed.');
