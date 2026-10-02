"""Review-only dual-coordinate board; no platform implementation changes."""
import json, math, time, uuid, urllib.request
from pathlib import Path
from types import SimpleNamespace
from spad_lidar.rx.spatial import image_center

base=Path(__file__).parent
snapshot=json.loads(base.parent.joinpath('budget-electrical-reference/snapshot.json').read_text(encoding='utf-8'))
c=snapshot['single_channel']['configuration'];rx=SimpleNamespace(**c['rx']);sp=c['spad'];tx=c['tx']
sign=-1 if rx.mapping_mode=='inverted' else 1
def inverse(p,f,offset):return 1000*math.atan((p-offset)/(sign*f*1000))
xe=[(i-sp['H_binning']/2)*sp['pixel_pitch_um'] for i in range(sp['H_binning']+1)]
ye=[(i-sp['V_binning']/2)*sp['pixel_pitch_um'] for i in range(sp['V_binning']+1)]
he=[inverse(p,rx.focal_length_h_mm,rx.rx_offset_x_um) for p in xe]
ve=[inverse(p,rx.focal_length_v_mm,rx.rx_offset_y_um) for p in ye]
for p,h in zip(xe,he):assert abs(float(image_center(rx,h,0)[0])-p)<1e-9
for p,v in zip(ye,ve):assert abs(float(image_center(rx,0,v)[1])-p)<1e-9
u='http://127.0.0.1:4173/api/boards/5586b159-c9c2-4abb-a09c-4ae63dc76fad/scene'
d=json.load(urllib.request.urlopen(u)); scene=d['scene']
# Preserve the user's edited first proposal; put the revised design underneath it.
ox=3050.9963100435825;oy=max(e['y']+e['height'] for e in scene['elements'] if not e.get('isDeleted') and e['x']>3000)+140
new=[]
def obj(t,x,y,w,h,col='#cbd5e1',bg='transparent',sw=1):
 e=dict(id=uuid.uuid4().hex,type=t,x=ox+x,y=oy+y,width=w,height=h,angle=0,strokeColor=col,backgroundColor=bg,fillStyle='solid',strokeWidth=sw,strokeStyle='solid',roughness=0,opacity=100,groupIds=[],frameId=None,roundness=None,seed=1,version=1,versionNonce=1,isDeleted=False,boundElements=[],updated=int(time.time()*1000),link=None,locked=False);new.append(e);return e
def text(x,y,s,size=18,col='#cbd5e1'):
 w=max(sum(1.02 if ord(z)>255 else .66 for z in row) for row in s.split('\n'))*size+10
 e=obj('text',x,y,w,len(s.split('\n'))*size*1.35,col);e.update(text=s,originalText=s,fontSize=size,fontFamily=2,textAlign='left',verticalAlign='top',containerId=None,autoResize=True,lineHeight=1.35);return e
def line(x1,y1,x2,y2,col='#334155',sw=1,dash=False):
 e=obj('line',min(x1,x2),min(y1,y2),abs(x2-x1),abs(y2-y1),col,sw=sw);e.update(points=[[x1-min(x1,x2),y1-min(y1,y2)],[x2-min(x1,x2),y2-min(y1,y2)]],startBinding=None,endBinding=None,startArrowhead=None,endArrowhead=None)
 if dash:e['strokeStyle']='dashed'
 return e
red='#f38b96';blue='#7db6ec';green='#5ee3b7';muted='#94a3b8'
obj('rectangle',0,0,1330,1140,'#334155','#101b26',2)
text(30,25,'审核稿 v2 · 单通道角域 / 实际探测尺寸',29,'#e2e8f0')
text(30,73,'合为一张双坐标图；cell 网格直接叠加；取消独立 SPAD 放大图。',20,muted)
text(30,113,'示例取截图对应工况；Rx角域、像元边界分别计算，框线不强制对齐。',18,muted)
L,T,S=142,235,640;scale=S/20
def X(h):return L+(h+10)*scale
def Y(v):return T+(10-v)*scale
for a in range(-10,11,2):
 line(X(a),T,X(a),T+S,'#344356',1,True)
 line(L,Y(a),L+S,Y(a),'#344356',1,True)
 text(X(a)-10,T+S+15,str(a),16)
 text(L-46,Y(a)-10,str(a),16)
 x,y=image_center(rx,a,a)
 text(X(a)-21,T-34,f'{float(x):.2f}',14,muted)
 text(L+S+12,Y(a)-10,f'{float(y):.2f}',14,muted)
obj('rectangle',L,T,S,S,'#94a3b8','transparent')
text(L-30,T-104,'主坐标：H/V · mrad',20)
text(L+200,T-76,'副坐标：像面 X · μm（倒置）',18,muted)
text(L-87,T-2,'V ↑',18);text(L+S-88,T+S+52,'H →',18)
text(L+S+6,T-62,'像面 Y / μm',16,muted)
def domain(h0,h1,v0,v1,col,fill,sw):
 return obj('rectangle',X(h0),Y(v1),(h1-h0)*scale,(v1-v0)*scale,col,fill,sw)
domain(rx.rx_angle_h_min_mrad,rx.rx_angle_h_max_mrad,rx.rx_angle_v_min_mrad,rx.rx_angle_v_max_mrad,blue,'#172939',2)
domain(tx['angle_h_min_mrad'],tx['angle_h_max_mrad'],tx['angle_v_min_mrad'],tx['angle_v_max_mrad'],red,'#39242e',2)
domain(min(he),max(he),min(ve),max(ve),green,'transparent',3)
for h in he[1:-1]:line(X(h),Y(max(ve)),X(h),Y(min(ve)),green,1)
for v in ve[1:-1]:line(X(min(he)),Y(v),X(max(he)),Y(v),green,1)
text(908,223,'边界与参数来源',23)
text(908,277,'Tx · 角域全宽',20,red)
text(908,313,'H 3.00 × V 17.45 mrad\n等价 H 0.17 × V 1.00 deg',18)
text(908,393,'Rx · 配置接收角域',20,blue)
text(908,429,'H 4.00 × V 17.45 mrad\n等价 H 0.23 × V 1.00 deg',18)
text(908,509,'SPAD · 实际 cell / binning',20,green)
text(908,547,'4 × 4 cells；pitch 20 μm\n分组 H 80 × V 80 μm\n对应 H 4.00 × V 4.00 mrad',18)
text(908,653,'绿色细实线：cell 边界\n绿色粗实线：binning 外框\n灰色等间距虚线：坐标网格',18,muted)
text(908,753,'本例 H 边界近似重合，\n是参数计算结果；\n改变焦距、偏移或 binning\n后各框独立变化。',18,muted)
text(30,949,'滤光后 477.45 → 探测面 101.62 光子    |    PSF 空间截获率 21.28%',24,green)
text(30,997,'网格按主角度坐标等间距；副坐标用精确 tan 映射，因此 μm 数值不严格等差。',18,muted)
text(30,1035,'倒置映射：X像 = −fH·tan(H) + X偏移；Y像 = −fV·tan(V) + Y偏移。像面轴不是ZMAX全局轴。',17,muted)
text(30,1073,'本图为几何边界对照；实际截获率仍由公共 Python 核心逐角域 / PSF 积分得到。',18,muted)
scene['elements'].extend(new)
req=urllib.request.Request(u,json.dumps({'scene':scene,'baseRevision':d['revision']},ensure_ascii=False).encode(),{'Content-Type':'application/json'},method='PUT')
out=json.load(urllib.request.urlopen(req))
base.joinpath('combined.excalidraw').write_text(json.dumps({'type':'excalidraw','version':2,'source':'AgentCanvas','elements':new,'appState':{'viewBackgroundColor':'#ffffff'},'files':{}},ensure_ascii=False),encoding='utf-8')
base.joinpath('combined-geometry.json').write_text(json.dumps({'source_config_sha256':snapshot['provenance']['configuration_sha256'],'pixel_x_edges_um':xe,'pixel_y_edges_um':ye,'equivalent_h_edges_mrad':he,'equivalent_v_edges_mrad':ve,'rx':c['rx'],'binning':[sp['H_binning'],sp['V_binning']],'verified':'forward/inverse image-center roundtrip < 1e-9 um'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'revision':out.get('revision'),'elements':len(new),'bounds':[ox,oy,1330,1140]}))
