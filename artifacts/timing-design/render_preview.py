"""Non-executable image preview; no browser or production page required."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).parent;doc=json.loads((root/'example.json').read_text(encoding='utf-8'));p=doc['schedule']
img=Image.new('RGB',(1800,1110),'#f5f2ed');d=ImageDraw.Draw(img)
def font(n):return ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
def text(x,y,s,n=20,color='#667d83',anchor=None):d.text((x,y),str(s),font=font(n),fill=color,anchor=anchor)
def rect(box,color,border=None,r=8):d.rounded_rectangle(box,radius=r,fill=color,outline=border,width=1)
def dash(x1,y1,x2,y2,color='#d7dfdb',length=3,gap=6):
 if x1==x2:
  for y in range(int(y1),int(y2),length+gap):d.line((x1,y,x2,min(y+length,y2)),fill=color,width=1)
 else:
  for x in range(int(x1),int(x2),length+gap):d.line((x,y1,min(x+length,x2),y2),fill=color,width=1)
text(52,32,'HARDWARE / DATA EXPORT TIMING',16,'#819a94')
text(52,66,'SPAD 数据链时序',35,'#354b53')
text(52,118,'参数来自配置面板；图中不增加调参控件。用阶段、重叠、等待和帧末拖尾解释数据流。',19,'#87938f')
rect((1430,42,1748,85),'#eee8dc');text(1450,54,'独立设计预览 · 待审核',20,'#907c60')
text(1300,109,'示例沿用图2条件，非当前工况结果',18,'#929b96')
stats=[('每列周期','100','μs'),('首列发送完成','223','μs'),('帧末发送完成','100.12','ms'),('帧末拖尾','123','μs')]
for i,(label,value,unit) in enumerate(stats):
 x=52+i*430;rect((x,175,x+409,282),'#fbf9f6','#e2dfd8');text(x+21,191,label,18,'#85948e');text(x+21,225,value,34,'#475e62');text(x+205,241,unit,18,'#809089')
rect((52,307,1418,1038),'#fbf9f6','#e2dfd8',12);rect((1440,307,1748,1038),'#fbf9f6','#e2dfd8',12)
text(77,329,'相邻 slot · 整列交接流水线',25,'#405860');text(964,337,'1000 slot/帧 · 200通道 · 10 Hz',18,'#739187')
text(78,383,'整帧 / 100 ms 预算',17,'#81908b')
rect((79,421,1388,434),'#e7e8e1',r=4);rect((79,421,1386,434),'#c2d0c7',r=4);d.line((1388,414,1388,442),fill='#729c83',width=1)
text(78,447,'0 ms',15,'#8b9992');text(1388,447,'100 ms + 123 μs 发出完成',17,'#759389','ra')
names=['采集 / 多发','Hist 搬移','DSP 输入延迟','DSP 处理','MIPI 打包','MIPI 发送']
colors=['#c98278','#3eaaa0','#aeaaa6','#9786c1','#d5aa55','#71a58a']
light=['#efd7d1','#d6ece7','#e9e6e1','#e5def0','#f0e6cb','#dceadf']
X=lambda us:270+us/550*1108
Y=lambda row:525+row*58
for t in range(0,551,50):
 x=X(t);dash(x,493,x,851)
 if t%100==0:text(x,866,t,16,'#91a09a','ma')
for i,name in enumerate(names):
 text(78,Y(i)-6,name,20,'#5e7481');d.line((270,Y(i)+26,1378,Y(i)+26),fill='#e5e9e4',width=1)
for col in range(4):
 start=col*100;left=X(start);right=X(start+82);dash(left,493,left,851,'#b4c2b9',3,5);text(left+7,481,f'slot {col}',17,'#809d90')
 rect((left,Y(0)-7,right,Y(0)+25),colors[0] if col==0 else light[0],r=4)
 text((left+right)/2,Y(0)+1,f'S{col}',18,'#4d6069','ma')
 for shot in range(4):
  xx=X(start+shot*82/4);d.line((xx,Y(0)-10,xx,Y(0)+27),fill='#b4655c',width=1)
for i,stage in enumerate(p['stages']):
 for row in stage['rows']:
  if row['column']>3:continue
  left=X(row['start_ns']/1000);right=X(row['end_ns']/1000);y=Y(i+1)
  rect((left,y-7,right,y+25),colors[i+1] if row['column']==0 else light[i+1],r=min(4,(right-left)/2))
  if right-left>32:text((left+right)/2,y+1,f'S{row["column"]}',18,'#4d6268','ma')
text(1234,906,'帧内时间 / μs',17,'#82948d')
xx=78
for name,col in zip(names,colors):
 rect((xx,935,xx+11,946),col,r=2);text(xx+19,929,name,15,'#82918f');xx+=222 if '延迟' in name else 194
rect((77,975,1390,1006),'#edf2eb',r=5)
text(90,980,'整帧等待峰值：搬移 0 列 · DSP 0 列 · 打包 0 列 · MIPI 0 列',16,'#718777');text(1195,980,'拖尾 123 μs',16,'#718777')
text(1460,330,'配置面板参数',22,'#48675f');text(1460,366,'这里只列演示条件',17,'#929b95')
params=[('列采集','82 μs'),('每列发射','4 次'),('整列移交','slot 结束'),('Hist搬移','15 μs'),('输入延迟','4 μs'),('DSP占用','66 μs'),('MIPI打包','5 μs'),('MIPI发送','33 μs')]
for i,(name,value) in enumerate(params):
 y=411+i*47;text(1460,y,name,18,'#8a9690');text(1580,y,value,18,'#5e7e70');d.line((1460,y+33,1728,y+33),fill='#e8e7e0',width=1)
text(1460,818,'整列交接；采集缓冲独立。\n搬移、DSP、打包各一个资源。\n阶段可同时服务不同列。\n演示使用无限队列，不丢数据。',17,'#87938d')
text(53,1059,'审核重点：阶段层次、相邻列重叠、精细线条、等待/拖尾信息。确认后才接入真实配置与后端计算。',18,'#89978f')
img.save(root/'preview.png')
print('Offline preview rendered:',img.size)
