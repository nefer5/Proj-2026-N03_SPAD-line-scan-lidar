"""Standalone layout review based on the user's reference example, not live defaults."""
import importlib.util,json
from pathlib import Path
from types import SimpleNamespace as NS

root=Path(__file__).parent
spec=importlib.util.spec_from_file_location('preview_pipeline',root/'implementation-draft/readout_pipeline-source.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
example=dict(source='user reference image 2; layout demonstration only',slot_us=100,frame_ms=100,columns=1000,channels=200,
             acquisition_us=82,shots=4,hist_transfer_us=15,dsp_input_delay_us=4,dsp_processing_us=66,mipi_pack_us=5,mipi_wire_us=33,handoff='slot boundary')
e=NS(pipeline_mode='pipelined',ready_delay_us=example['slot_us']-example['acquisition_us'],
     hist_transfer_us=example['hist_transfer_us'],dsp_input_delay_us=example['dsp_input_delay_us'],
     dsp_processing_us=example['dsp_processing_us'],mipi_pack_us=example['mipi_pack_us'])
c=NS(electrical=e,targets=NS(slot_count=example['columns'],scan_time_utilization=1))
t=dict(slot_max_ns=example['slot_us']*1000,frame_period_ns=example['frame_ms']*1e6,frame_preview_indices=[0,1,2,3,999])
p=module.pipeline_schedule(c,t,example['acquisition_us']*1000,example['mipi_wire_us']*1000,4)
assert p['frame_completion_ns']==100123000 and p['frame_tail_ns']==123000
root.joinpath('example.json').write_text(json.dumps({'example':example,'schedule':p},ensure_ascii=False,indent=2),encoding='utf-8')
colors=['#c67c73','#3caaa0','#a6a29e','#9384bf','#d4aa57','#6ea98b']
names=['采集 / 多发','Hist 搬移','DSP 输入延迟','DSP 处理','MIPI 打包','MIPI 发送']
left,right,span=162,1158,550
X=lambda us:left+us/span*(right-left)
Y=lambda row:70+row*44
text=lambda x,y,value,cls='',anchor='start':f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{value}</text>'
svg=[]
for i in range(12):
 us=i*50;x=X(us);svg.append(f'<path d="M{x} 42V313" class="grid"/>')
 if i%2==0:svg.append(text(x,339,us,'tick','middle'))
for i,name in enumerate(names):
 svg.append(text(16,Y(i)+5,name,'lane-label'))
 svg.append(f'<path d="M{left} {Y(i)+16}H{right}" class="baseline"/>')
for col in range(4):
 start=col*100;end=start+82;x=X(start);width=X(end)-x
 svg.append(f'<path d="M{x} 40V313" class="slot-line"/>')
 svg.append(text(x+5,32,f'slot {col}','slot-name'))
 svg.append(f'<rect x="{x}" y="{Y(0)-12}" width="{width}" height="25" rx="4" fill="{colors[0]}" opacity="{.68 if col==0 else .27}"/>')
 svg.append(text(x+width/2,Y(0)+5,f'S{col}','block-label','middle'))
 for shot in range(4):
  xx=X(start+shot*82/4);svg.append(f'<path d="M{xx} {Y(0)-14}v29" class="pulse"/>')
for i,stage in enumerate(p['stages']):
 for row in stage['rows']:
  if row['column']>=4:continue
  start,end=row['start_ns']/1000,row['end_ns']/1000;x=X(start);width=X(end)-x
  svg.append(f'<rect x="{x}" y="{Y(i+1)-11}" width="{width}" height="23" rx="3" fill="{colors[i+1]}" opacity="{.82 if row["column"]==0 else .28}"><title>S{row["column"]} {stage["label"]} {start:g}–{end:g} μs</title></rect>')
  if width>24:svg.append(text(x+width/2,Y(i+1)+5,f'S{row["column"]}','block-label','middle'))
svg.append(text(right,364,'帧内时间 / μs','tick','end'))
legend=''.join(f'<span><i style="background:{color}"></i>{name}</span>' for color,name in zip(colors,names))
params=[('列采集窗口','82 μs'),('每列发射次数','4 次'),('移交时点','slot 结束'),('Hist整列搬移','15 μs'),('DSP输入延迟','4 μs'),('DSP资源占用','66 μs'),('MIPI打包','5 μs'),('MIPI发送','33 μs')]
param_html=''.join(f'<div><span>{k}</span><b>{v}</b></div>' for k,v in params)
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SPAD数据链时序 · 设计预览</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f2ed;color:#354650;font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}main{max-width:1440px;margin:auto;padding:35px 40px 50px}header{display:flex;justify-content:space-between;gap:20px;margin-bottom:24px}.eyebrow{font-size:11px;letter-spacing:1.5px;color:#7b9291}h1{font-size:25px;font-weight:550;letter-spacing:.4px;margin:6px 0}h2{font-size:16px;font-weight:550;margin:0}p{margin:6px 0}.muted{color:#899397;font-size:12px}.pill{display:inline-block;background:#ebe7df;padding:4px 12px;border-radius:20px;font-size:11px;color:#8f7450}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:21px 0}.stat{padding:14px 18px;border:1px solid #e2dfd8;border-radius:10px;background:#fbf9f6}.stat span{display:block;font-size:11px;color:#81908f}.stat b{font-size:24px;font-weight:450;color:#475d62}.stat small{font-size:12px;margin-left:5px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:18px;align-items:start}.card{border:1px solid #e2dfd8;border-radius:12px;background:#fbf9f6;padding:23px}.card-head{display:flex;justify-content:space-between;align-items:baseline;gap:15px;margin-bottom:17px}.frame-track{height:10px;position:relative;background:#e9e7e1;border-radius:4px;margin:20px 0 8px}.frame-track:before{content:"";position:absolute;width:99.87%;height:100%;background:#c3d0c8;border-radius:4px}.frame-track:after{content:"";position:absolute;right:0;top:-5px;width:1px;height:20px;background:#75a087}.frame-caption{display:flex;justify-content:space-between;color:#7f8f8c;font-size:11px}.diagram{display:block;width:100%;margin-top:14px}.diagram text{font-family:"Segoe UI","Microsoft YaHei",sans-serif;font-size:13px;fill:#687d83}.diagram .lane-label{font-size:12px;fill:#50636e}.diagram .tick,.diagram .slot-name{font-size:11px;fill:#92a09f}.grid{stroke:#d9dfdc;stroke-width:.65;stroke-dasharray:2 5}.baseline{stroke:#e6e9e6;stroke-width:.6;fill:none}.slot-line{stroke:#aab8b3;stroke-width:.7;stroke-dasharray:3 5;fill:none}.pulse{stroke:#a85852;stroke-width:.8;opacity:.7}.diagram .block-label{fill:#3d505a;font-size:11px}.legend{display:flex;gap:15px;flex-wrap:wrap;margin:0 0 18px 12px;font-size:11px;color:#75898c}.legend i{display:inline-block;width:8px;height:8px;margin-right:6px;border-radius:2px}.queue{padding:11px 14px;background:#f1f4f0;border-radius:7px;color:#71867e;font-size:12px}.trace{margin-top:16px;padding-top:15px;border-top:1px solid #e5e5df;font-size:11px;line-height:1.9;color:#79878b}.params{padding:18px}.params h2{font-size:14px}.params>div{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #eeeae4;font-size:11px;gap:10px}.params b{font-weight:500;white-space:nowrap;color:#53736e}.principles{font-size:11px;color:#83918f;line-height:1.85;margin-top:16px}.foot{margin-top:20px;font-size:11px;color:#83918f}.tag{font-size:11px;color:#66938b}
@media(max-width:1000px){.layout{grid-template-columns:1fr}.params{display:none}main{padding:25px 20px}.summary{grid-template-columns:repeat(2,1fr)}}
</style><main><header><div><div class="eyebrow">HARDWARE / DATA EXPORT TIMING</div><h1>SPAD 数据链时序</h1><p class="muted">从列采集到发送完成 · 参数来自侧栏配置 · 图内不增加调参控件</p></div><div><span class="pill">独立设计预览 · 待审核</span><p class="muted">演示条件沿用你给的图2，非当前工况结果</p></div></header>
<div class="summary"><div class="stat"><span>每列周期</span><b>100<small>μs</small></b></div><div class="stat"><span>首列发送完成</span><b>223<small>μs</small></b></div><div class="stat"><span>帧末发送完成</span><b>100.123<small>ms</small></b></div><div class="stat"><span>帧末拖尾</span><b>123<small>μs</small></b></div></div>
<div class="layout"><section class="card"><div class="card-head"><h2>相邻 slot · 整列交接流水线</h2><span class="tag">1000 slot / 帧 · 200 通道 · 10 Hz</span></div><p class="muted">整帧 / 100 ms 预算</p><div class="frame-track"></div><div class="frame-caption"><span>0 ms</span><span>100.123 ms 发出完成</span></div><svg class="diagram" viewBox="0 0 1180 384" role="img" aria-label="首四列的采集、搬移、DSP、打包及发送流水线">__SVG__</svg><div class="legend">__LEGEND__</div><div class="queue">等待峰值（整帧）：搬移 0 列 · DSP 0 列 · 打包 0 列 · MIPI 0 列 <span style="float:right">帧末拖尾 123 μs</span></div><div class="trace"><b>首列 S0</b>　采集 0–82 μs · 锁存交接 100 μs · 搬移 100–115 μs · DSP 119–185 μs · 打包 185–190 μs · 发送 190–223 μs<br>浅色为后续列，颜色区分阶段；细竖线表示发射事件。正式图会显示资源等待、未知耗时与帧截止判断。</div></section><aside class="card params"><h2>参数来源 · 左侧配置面板</h2><p class="muted">这里只列预览条件，无交互控件</p>__PARAMS__<p class="principles">整列交接；采集缓冲与后级独立。搬移、DSP和打包各占一个资源；各阶段可同时服务不同列。此演示采用无限等待队列，不丢数据。</p></aside></div><p class="foot">审核重点：阶段层次、相邻列重叠、细线与留白、等待/拖尾信息。深浅主题会沿用正式平台配色。审批后才接入真实配置及后端计算。</p></main></html>'''
html=html.replace('__SVG__',''.join(svg)).replace('__LEGEND__',legend).replace('__PARAMS__',param_html)
root.joinpath('preview.html').write_text(html,encoding='utf-8')
print('Standalone preview written; frame tail = 123 us. Production routes untouched.')
