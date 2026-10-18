"""数值展示不能降低未编辑参数的计算精度。"""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_compact_display_retains_raw_input_precision():
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 执行前端精度回归")
    source = Path(__file__).resolve().parents[1] / "web/shared/units.js"
    script = r'''
const assert=require("node:assert/strict");
const listeners={};global.document={addEventListener:(event,fn)=>listeners[event]=fn};
require(process.argv[1]);
const N=global.LidarNumbers;
assert.equal(N.input(660.3028307242),"660.3");
assert.equal(N.input(673.9535500684),"673.95");
assert.equal(N.input(.000001234567),"1.23e-6");
assert.equal(N.input(1200),"1200");
assert.equal(N.input(0),"0");
const el={value:"",title:"时间 / ns"};
N.setInput(el,660.3028307242);
assert.equal(N.readInput(el),660.3028307242);
listeners.blur({target:el});assert.equal(N.readInput(el),660.3028307242);
el.value="660.3";listeners.input({target:el});assert.equal(N.readInput(el),660.3);
el.value="660.3456789";listeners.input({target:el});listeners.change({target:el});
assert.equal(N.readInput(el),660.3456789);listeners.blur({target:el});
assert.equal(el.value,"660.35");assert.equal(N.readInput(el),660.3456789);
el.value="";listeners.input({target:el});assert.ok(Number.isNaN(N.readInput(el)));
N.setInput(el,null);assert.equal(el.value,"");assert.equal(N.readInput(el),null);
N.setInput(el,10.12345678);el.value="11.2345678";assert.equal(N.readInput(el),11.2345678);
assert.equal(BudgetNumbers.input(.000001234567),"1.23e-6");
'''
    subprocess.run([node, "-e", script, str(source)], check=True, capture_output=True, text=True)
