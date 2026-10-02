"""Three-slot resource-dependency illustration; no production configuration changes."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).parent
# Deliberately stressful illustration values, not simulation defaults.
example=dict(source='illustration only',mode='Range',banks=2,fifo_blocks=1,output_block_bytes=1024,
             planned_slot_us=80,acquisition_us=80,hist_access_us=10,dsp_us=100,pack_us=10,wire_us=160,
             bank_release='DSP output committed to FIFO',fifo_release='whole block after TX completion')
bank_free=[0,0];capture_free=0;dsp_free=0;access_free=0;pack_free=0;wire_free=0;fifo_releases=[];rows=[]
for i in range(3):
    bank=i%2;planned=i*example['planned_slot_us']
    cap=max(planned,capture_free,bank_free[bank]);cap_end=cap+example['acquisition_us'];capture_free=cap_end
    # No extra complete-column DSP input bank: reading waits for this engine.
    access=max(cap_end,access_free,dsp_free);access_end=access+example['hist_access_us'];access_free=access_end
    compute=access_end;compute_end=compute+example['dsp_us']
    commit=compute_end
    while True:
        fifo_releases=[t for t in fifo_releases if t>commit]
        if len(fifo_releases)<example['fifo_blocks']:break
        commit=min(fifo_releases)
    pack=max(commit,pack_free);pack_end=pack+example['pack_us'];pack_free=pack_end
    tx=max(pack_end,wire_free);tx_end=tx+example['wire_us'];wire_free=tx_end
    fifo_releases.append(tx_end);bank_free[bank]=commit;dsp_free=commit
    rows.append(dict(slot=i,bank='AB'[bank],planned=planned,capture=[cap,cap_end],hist=[access,access_end],
        dsp=[compute,compute_end],output_wait=[compute_end,commit],fifo=[commit,tx_end],pack=[pack,pack_end],
        mipi=[tx,tx_end],bank_release=commit,start_delay=cap-planned))
assert rows[2]['capture'][0]==190 and rows[1]['output_wait']==[300,360] and rows[2]['output_wait']==[470,530]
assert rows[2]['mipi'][1]==700
for i,r in enumerate(rows):
    assert r['hist'][0]>=r['capture'][1] and r['dsp'][0]>=r['hist'][1]
    assert r['fifo'][0]>=r['dsp'][1] and r['mipi'][0]>=r['pack'][1]
    if i>=2:assert r['capture'][0]>=rows[i-2]['bank_release']
    if i:assert r['hist'][0]>=rows[i-1]['bank_release'] and r['mipi'][0]>=rows[i-1]['mipi'][1]
events=sorted([(r['fifo'][0],1) for r in rows]+[(r['fifo'][1],-1) for r in rows])
used=peak=0
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
text(45,66,'双缓冲乒乓 · 三个 slot 的时间依赖',34,'#354d56')
text(45,121,'优选：片内 Hist + 片内 DSP + Range 输出；正交依赖线说明 bank 复用与有限 FIFO 背压。',19,'#819389')
rect(1540,45,1854,88,'#ede8df');text(1560,54,'设计预览 · 非当前工况结果',19,'#937e61')
stats=[('Hist缓冲','A / B','两个 bank'),('输出FIFO','1 KiB','本例只容纳一列结果'),('S2采集推迟','30 μs','计划160 → 实际190'),('DSP输出等待','60 μs','S1和S2均等待FIFO释放')]
for i,(k,v,note) in enumerate(stats):
    x=45+i*455;rect(x,180,x+431,292,'#fbf9f6','#e0ddd6');text(x+17,192,k,17,'#819189');text(x+17,219,v,29,'#465f65');text(x+17,261,note,15,'#8e9c95')
rect(45,322,1463,1180,'#fbf9f6','#e0ddd6');rect(1483,322,1854,1180,'#fbf9f6','#e0ddd6')
text(66,341,'一个代表芯片 · 保守整列处理模型',23,'#47636a')
text(939,348,'时间轴一致；实线为依赖，虚线为等待',16,'#8a9b93')
left,right=253,1418;X=lambda t:left+t/720*(right-left);Y=lambda lane:452+lane*65
names=['Bank A · 采集','Bank B · 采集','Hist 访问/搬移','DSP 计算','DSP 输出等待','输出 FIFO 占位','MIPI 打包','MIPI 发送']
for t in range(0,701,50):
    line(X(t),423,X(t),965,dashed=True)
    if t%100==0:text(X(t),982,t,16,'#8da199','ma')
for j,name in enumerate(names):text(65,Y(j)-2,name,19,'#58727b');line(left,Y(j)+32,right,Y(j)+32,'#e8ebe5')
colors=['#c38378','#74a99c','#55aaa1','#9788bc','#d1aa58','#82a88f','#ceaa5a','#69a18b']
for r in rows:
    i=r['slot'];bank_lane=0 if r['bank']=='A' else 1;cap=r['capture'];y=Y(bank_lane)
    rect(X(cap[1]),y-8,X(r['bank_release']),y+26,'#e6e6e0')
    if r['bank_release']-cap[1]>45:text((X(cap[1])+X(r['bank_release']))/2,y,'Hist 保留',15,'#929b93','ma')
    rect(X(cap[0]),y-8,X(cap[1]),y+26,colors[bank_lane]);text((X(cap[0])+X(cap[1]))/2,y,f'S{i}',18,'#425b63','ma')
    for lane,key in [(2,'hist'),(3,'dsp'),(4,'output_wait'),(5,'fifo'),(6,'pack'),(7,'mipi')]:
        a,b=r[key];y=Y(lane)
        if b==a:continue
        rect(X(a),y-8,X(b),y+26,colors[lane] if i==0 else ['#e6d5cf','#d8e8e1','#d5eae5','#e2dbee','#f1e6cd','#dce9de','#f0e5c9','#d8e9de'][lane])
        if b-a>24:text((X(a)+X(b))/2,y,('FIFO满' if key=='output_wait' else f'S{i}'),17,'#5c727a','ma')
    # Capture complete -> Hist data ready, then wait for the DSP input resource.
    ya=Y(bank_lane)+26;yh=Y(2)-8
    line(X(cap[1]),ya,X(cap[1]),yh-9,'#acbdb3')
    if r['hist'][0]>cap[1]:line(X(cap[1]),yh-9,X(r['hist'][0]),yh-9,'#b7b9ab',True)
    line(X(r['hist'][0]),yh-9,X(r['hist'][0]),yh,'#acbdb3')
    # Adjacent stages sharing a handoff timestamp get a vertical connector.
    for time,lane_a,lane_b in [(r['hist'][1],2,3),(r['fifo'][0],4,5),(r['pack'][1],6,7)]:
        line(X(time),Y(lane_a)+26,X(time),Y(lane_b)-8,'#91ad9f')

# Long-range resource-release dependencies. These are not decorative tick lines.
line(X(190),Y(0)-22,X(190),Y(5)+27,'#638d7c');text(X(190)+8,399,'A释放 → S2采集',16,'#638d7c')
for time in [360,530]:
    line(X(time),Y(2)-8,X(time),Y(7)+27,'#78998a')
text(X(360)+8,1030,'FIFO释放 → DSP交付 / 下一任务读入',16,'#6d9282')
line(X(160),Y(0)-17,X(190),Y(0)-17,'#c1a664',True)
text(X(160)-7,Y(0)-44,'S2等待30 μs',15,'#ad9666')
text(1270,1083,'时间 / μs',17,'#8a9b94')
text(68,1129,'浅灰 = Hist bank 保留；黄色 = DSP结果等待。MIPI发送完成释放FIFO占位，背压沿依赖向前传播。',17,'#87988f')

text(1503,343,'已确认的模式与约束',22,'#496b60')
side=[('Range','每点完整字节数由用户填写'),('全 Hist','旁路DSP，输出片内累计计数'),('Echo','回波数 × 窗口宽度：上限预算'),('采集架构','单 / 双缓冲可选，优选双缓冲'),('资源阻塞','FIFO满时背压；不默认丢数据')]
for j,(k,v) in enumerate(side):text(1503,397+j*65,k,18,'#728d7d');text(1503,425+j*65,v,16,'#8a9b91')
line(1503,737,1834,737,'#e5e7e0')
text(1503,759,'本图的演示条件',21,'#617f70')
text(1503,802,'目标列周期 80 μs；采集 80 μs\nHist访问 10 μs；DSP 100 μs\n打包 10 μs；MIPI发送 160 μs\n一列完整结果块 1 KiB\nFIFO保留整块直至发送完成',17,'#8a9991')
text(1503,970,'保守释放规则：\n结果进入FIFO后才释放Hist bank。\n本例无独立DSP整列输入缓存。\n复位耗时取0，仅为依赖演示。\n后续可配置释放事件及复位时间。',16,'#8d9993')
text(45,1216,'仅更新独立预览。正式网页与真实芯片参数未改变；发送160 μs为人工设定的慢链路场景，不作为CSI-2/D-PHY带宽结论。',17,'#8a9991')
img.save(root/'preview.png')
root.joinpath('preview.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="1320" viewBox="0 0 1900 1320"><rect width="1900" height="1320" fill="#f5f2ed"/><g font-family="Microsoft YaHei,Segoe UI,sans-serif">'+''.join(svg)+'</g></svg>',encoding='utf-8')
print(json.dumps({'capture_starts':[r['capture'][0] for r in rows],'fifo_waits':[r['output_wait'][1]-r['output_wait'][0] for r in rows],'fifo_peak_blocks':peak,'last_tx_end_us':rows[-1]['mipi'][1]}))
