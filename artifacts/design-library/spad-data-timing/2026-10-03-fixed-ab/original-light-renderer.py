"""Three-slot resource-dependency illustration; no production configuration changes."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).parent
# Deliberately stressful illustration values, not simulation defaults.
example=dict(source='illustration only',mode='Range',buffer_roles='A acquisition; B DSP',fifo_blocks=1,output_block_bytes=1024,
             planned_slot_us=80,acquisition_us=80,copy_us=10,clear_a_us=5,dsp_us=100,pack_us=10,wire_us=160,
             a_release='A-to-B copy then A clear complete',b_release='DSP output committed to FIFO',fifo_release='whole block after TX completion')
a_free=0;b_free=0;copy_free=0;pack_free=0;wire_free=0;fifo_releases=[];rows=[]
for i in range(3):
    planned=i*example['planned_slot_us'];cap=max(planned,a_free);cap_end=cap+example['acquisition_us']
    copy=max(cap_end,b_free,copy_free);copy_end=copy+example['copy_us'];copy_free=copy_end
    clear_end=copy_end+example['clear_a_us'];a_free=clear_end
    compute=copy_end;compute_end=compute+example['dsp_us'];commit=compute_end
    while True:
        fifo_releases=[t for t in fifo_releases if t>commit]
        if len(fifo_releases)<example['fifo_blocks']:break
        commit=min(fifo_releases)
    pack=max(commit,pack_free);pack_end=pack+example['pack_us'];pack_free=pack_end
    tx=max(pack_end,wire_free);tx_end=tx+example['wire_us'];wire_free=tx_end
    fifo_releases.append(tx_end);b_free=commit
    rows.append(dict(slot=i,planned=planned,capture=[cap,cap_end],copy=[copy,copy_end],clear_a=[copy_end,clear_end],
        dsp=[compute,compute_end],output_wait=[compute_end,commit],fifo=[commit,tx_end],pack=[pack,pack_end],
        mipi=[tx,tx_end],b_release=commit,start_delay=cap-planned))
assert [r['capture'][0] for r in rows]==[0,95,205]
assert rows[1]['output_wait']==[300,360] and rows[2]['copy']==[360,370]
for i,r in enumerate(rows):
    assert r['copy'][0]>=r['capture'][1] and r['dsp'][0]>=r['copy'][1]
    assert r['clear_a'][0]==r['copy'][1] and r['fifo'][0]>=r['dsp'][1]
    if i:
        assert r['capture'][0]>=rows[i-1]['clear_a'][1]
        assert r['copy'][0]>=rows[i-1]['b_release']
        assert r['mipi'][0]>=rows[i-1]['mipi'][1]
events=sorted([(r['fifo'][0],1) for r in rows]+[(r['fifo'][1],-1) for r in rows]);used=peak=0
for _,change in events:used+=change;peak=max(peak,used);assert 0<=used<=example['fifo_blocks']
root.joinpath('example.json').write_text(json.dumps({'example':example,'slots':rows,'fifo_peak_blocks':peak},ensure_ascii=False,indent=2),encoding='utf-8')

W,H=1900,1320;img=Image.new('RGB',(W,H),'#f5f2ed');draw=ImageDraw.Draw(img);svg=[]
def text(x,y,s,n=18,color='#697f85',anchor=None):
    draw.text((x,y),str(s),font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n),fill=color,anchor=anchor)
    alignment='middle' if anchor and anchor.startswith('m') else 'end' if anchor and anchor.startswith('r') else 'start'
    svg.append(f'<text x="{x}" y="{y+n}" fill="{color}" font-size="{n}" text-anchor="{alignment}">{str(s).replace("&","&amp;").replace("<","&lt;")}</text>')
def rect(x1,y1,x2,y2,fill,stroke=None):
    draw.rectangle((x1,y1,x2,y2),fill=fill,outline=stroke,width=1)
    svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="0.7"/>')
def line(x1,y1,x2,y2,color='#d9e0da',dashed=False):
    if dashed:
        if x1==x2:
            for y in range(int(min(y1,y2)),int(max(y1,y2)),9):draw.line((x1,y,x2,min(y+3,max(y1,y2))),fill=color,width=1)
        else:
            for x in range(int(min(x1,x2)),int(max(x1,x2)),9):draw.line((x,y1,min(x+3,max(x1,x2)),y2),fill=color,width=1)
    else:draw.line((x1,y1,x2,y2),fill=color,width=1)
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="0.7"'+(' stroke-dasharray="3 6"' if dashed else '')+'/>')

text(45,28,'HARDWARE / RESOURCE DEPENDENCIES',15,'#81998e')
text(45,66,'固定分工双缓冲 · A采集 / B处理',34,'#354d56')
text(45,121,'A采集 → 搬到B → 清空A再采下一列；B中的DSP与A采集重叠。三个slot，仅作架构依赖预览。',19,'#819389')
rect(1540,45,1854,88,'#ede8df');text(1560,54,'设计预览 · 非当前工况结果',19,'#937e61')
stats=[('缓冲分工','A采集 / B处理','角色固定，不轮换'),('输出FIFO','1 KiB','本例只容纳一列结果'),('S2采集推迟','45 μs','计划160 → 实际205'),('DSP输出等待','60 μs','S1和S2均等待FIFO释放')]
for i,(k,v,note) in enumerate(stats):
    x=45+i*455;rect(x,180,x+431,292,'#fbf9f6','#e0ddd6');text(x+17,192,k,17,'#819189');text(x+17,219,v,29,'#465f65');text(x+17,261,note,15,'#8e9c95')
rect(45,322,1463,1180,'#fbf9f6','#e0ddd6');rect(1483,322,1854,1180,'#fbf9f6','#e0ddd6')
text(66,341,'一个代表芯片 · 固定角色A/B + 有限FIFO',23,'#47636a')
text(939,348,'时间轴一致；实线为依赖，虚线为等待',16,'#8a9b93')
left,right=253,1418;X=lambda t:left+t/720*(right-left);Y=lambda lane:452+lane*65
names=['缓存 A · 采集','A 清空 / 复位','A → B 搬移','缓存 B · DSP','B 输出等待','输出 FIFO 占位','MIPI 打包','MIPI 发送']
for t in range(0,701,50):
    line(X(t),423,X(t),965,dashed=True)
    if t%100==0:text(X(t),982,t,16,'#8da199','ma')
for j,name in enumerate(names):text(65,Y(j)-2,name,19,'#58727b');line(left,Y(j)+32,right,Y(j)+32,'#e8ebe5')
colors=['#c38378','#74a99c','#55aaa1','#9788bc','#d1aa58','#82a88f','#ceaa5a','#69a18b']
for r in rows:
    i=r['slot'];cap=r['capture'];y=Y(0)
    rect(X(cap[1]),y-8,X(r['copy'][1]),y+26,'#e6e6e0')
    if r['copy'][1]-cap[1]>45:text((X(cap[1])+X(r['copy'][1]))/2,y,'等待 / 搬移',15,'#929b93','ma')
    rect(X(cap[0]),y-8,X(cap[1]),y+26,colors[0] if i==0 else '#e6d5cf');text((X(cap[0])+X(cap[1]))/2,y,f'S{i}',18,'#425b63','ma')
    rect(X(r['copy'][0]),Y(3)-8,X(r['b_release']),Y(3)+26,'#e6e6e0')
    for lane,key in [(1,'clear_a'),(2,'copy'),(3,'dsp'),(4,'output_wait'),(5,'fifo'),(6,'pack'),(7,'mipi')]:
        aa,bb=r[key];y=Y(lane)
        if bb==aa:continue
        rect(X(aa),y-8,X(bb),y+26,colors[lane] if i==0 else ['#e6d5cf','#d8e8e1','#d5eae5','#e2dbee','#f1e6cd','#dce9de','#f0e5c9','#d8e9de'][lane])
        if bb-aa>24:text((X(aa)+X(bb))/2,y,('FIFO满' if key=='output_wait' else f'S{i}'),17,'#5c727a','ma')
    # A data-ready to actual copy: the horizontal portion is a real wait.
    line(X(cap[1]),Y(0)+26,X(cap[1]),Y(2)-17,'#a9bbae')
    if r['copy'][0]>cap[1]:line(X(cap[1]),Y(2)-17,X(r['copy'][0]),Y(2)-17,'#b7b9ab',True)
    line(X(r['copy'][0]),Y(2)-17,X(r['copy'][0]),Y(2)-8,'#a9bbae')
    # The same copy completion releases A to clearing and B to processing.
    line(X(r['copy'][1]),Y(1)-8,X(r['copy'][1]),Y(3)-8,'#91ad9f')
    if i<2:line(X(r['clear_a'][1]),Y(0)-8,X(r['clear_a'][1]),Y(1)+26,'#91ad9f')
    for stamp,la,lb in [(r['fifo'][0],4,5),(r['pack'][1],6,7)]:line(X(stamp),Y(la)+26,X(stamp),Y(lb)-8,'#91ad9f')
line(X(190),Y(2)-22,X(190),Y(5)+27,'#638d7c');text(X(190)+8,399,'B释放 → 搬移S1',16,'#638d7c')
for stamp in [360,530]:line(X(stamp),Y(2)-8,X(stamp),Y(7)+27,'#78998a')
text(X(360)+8,1030,'FIFO释放 → B结果交付 / 后续搬移',16,'#6d9282')
line(X(160),Y(0)-17,X(205),Y(0)-17,'#c1a664',True)
text(X(160)-7,Y(0)-44,'S2延后45 μs',15,'#ad9666')
text(1270,1083,'时间 / μs',17,'#8a9b94')
text(68,1129,'浅灰 = 缓存数据保留；黄色 = FIFO满导致B仍被占用。A等待B可写才搬移，搬移/清空后才采下一列。',17,'#87988f')

text(1503,343,'已确认的模式与约束',22,'#496b60')
side=[('Range','每点完整字节数由用户填写'),('全 Hist','旁路DSP，输出片内累计计数'),('Echo','回波数 × 窗口宽度：上限预算'),('优选架构','固定A采集 / B处理，可配其他方式'),('资源阻塞','FIFO满时背压；不默认丢数据')]
for j,(k,v) in enumerate(side):text(1503,397+j*65,k,18,'#728d7d');text(1503,425+j*65,v,16,'#8a9b91')
line(1503,737,1834,737,'#e5e7e0')
text(1503,759,'本图的演示条件',21,'#617f70')
text(1503,802,'目标列周期 80 μs；采集 80 μs\nA→B搬移 10 μs；A清空 5 μs\nDSP处理 100 μs\n打包 10 μs；MIPI发送 160 μs\n一列完整结果块 1 KiB\nFIFO保留整块直至发送完成',17,'#8a9991')
text(1503,1004,'保守释放规则：\n结果进入FIFO后才释放缓存B。\nB就是DSP整列工作缓存。\nA在搬移结束并清空后复用。\n搬移期间A/B均占用，不并行改写。\n所有耗时仅为示意，后续可配置。',16,'#8d9993')
text(45,1216,'仅更新独立预览。正式网页与真实芯片参数未改变；发送160 μs为人工设定的慢链路场景，不作为CSI-2/D-PHY带宽结论。',17,'#8a9991')
img.save(root/'preview.png')
root.joinpath('preview.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="1320" viewBox="0 0 1900 1320"><rect width="1900" height="1320" fill="#f5f2ed"/><g font-family="Microsoft YaHei,Segoe UI,sans-serif">'+''.join(svg)+'</g></svg>',encoding='utf-8')
print(json.dumps({'capture_starts':[r['capture'][0] for r in rows],'fifo_waits':[r['output_wait'][1]-r['output_wait'][0] for r in rows],'fifo_peak_blocks':peak,'last_tx_end_us':rows[-1]['mipi'][1]}))
