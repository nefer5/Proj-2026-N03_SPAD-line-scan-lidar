"""Review-only Excalidraw proposal. Preserve existing board elements."""
import json, math, time, uuid, urllib.request
from pathlib import Path

URL='http://127.0.0.1:4173/api/boards/5586b159-c9c2-4abb-a09c-4ae63dc76fad/scene'
data=json.load(urllib.request.urlopen(URL)); scene=data['scene']
Path(__file__).parent.joinpath('before.excalidraw').write_text(json.dumps(scene,ensure_ascii=False),encoding='utf-8')
old=[e for e in scene['elements'] if not e.get('isDeleted')]
ox=max((e['x']+e['width'] for e in old),default=0)+160; oy=100
new=[]
def item(kind,x,y,w,h,color='#cbd5e1',bg='transparent',sw=1):
    e=dict(id=uuid.uuid4().hex,type=kind,x=ox+x,y=oy+y,width=w,height=h,angle=0,strokeColor=color,backgroundColor=bg,fillStyle='solid',strokeWidth=sw,strokeStyle='solid',roughness=0,opacity=100,groupIds=[],frameId=None,roundness=None,seed=1,version=1,versionNonce=1,isDeleted=False,boundElements=[],updated=int(time.time()*1000),link=None,locked=False)
    new.append(e);return e
def box(x,y,w,h,c,bg='transparent',sw=1):return item('rectangle',x,y,w,h,c,bg,sw)
def text(x,y,s,size=20,c='#cbd5e1'):
    e=item('text',x,y,max(len(z) for z in s.split('\n'))*size*.63,len(s.split('\n'))*size*1.35,c)
    e.update(text=s,originalText=s,fontSize=size,fontFamily=2,textAlign='left',verticalAlign='top',containerId=None,autoResize=True,lineHeight=1.35);return e
def line(x1,y1,x2,y2,c='#475569',sw=1,dash=False):
    e=item('line',min(x1,x2),min(y1,y2),abs(x2-x1),abs(y2-y1),c,sw=sw)
    e['points']=[[x1-min(x1,x2),y1-min(y1,y2)],[x2-min(x1,x2),y2-min(y1,y2)]]
    e.update(startBinding=None,endBinding=None,startArrowhead=None,endArrowhead=None)
    if dash:e['strokeStyle']='dashed'
    return e
red='#f38b96';blue='#7db6ec';green='#5ee3b7';gray='#94a3b8'
box(0,0,1640,1040,'#334155','#101b26',2)
text(32,24,'设计审核稿 · 单通道角域与 SPAD 实际探测尺寸',30,'#e2e8f0')
text(32,76,'替换「V角分布与整列接收包络」；整机全视场保留在主3D图。数值使用当前截图对应工况。',19,gray)
for x,w in [(30,545),(595,600),(1215,395)]:box(x,130,w,690,'#334155','#0b131c')
text(50,150,'01 角域对照',24);text(50,187,'H/V 同比例 · 单位 mrad',17,gray)
# Angular plot: all angles on one physical scale.
cx,cy,sc=305,488,27
for v in [-8.73,-4,0,4,8.73]:
    y=cy-v*sc;line(105,y,510,y,'#233142');text(44,y-10,f'{v:g}',16,gray)
line(105,236,105,745,gray);line(105,745,510,745,gray)
text(50,220,'+V / mrad ↑',17,gray);text(390,781,'+H / mrad →',17,gray)
for h in [-4,-2,0,2,4]:
    x=cx+h*sc;line(x,745,x,753,gray);text(x-8,757,str(h),16,gray)
box(cx-2*sc,cy-8.72665*sc,4*sc,17.4533*sc,blue,'#172939',2)
box(cx-1.5*sc,cy-8.72665*sc,3*sc,17.4533*sc,red,'#39242e',2)
box(cx-2*sc,cy-2*sc,4*sc,4*sc,green,'transparent',3)
for i in range(1,4):
    line(cx-2*sc+i*sc,cy-2*sc,cx-2*sc+i*sc,cy+2*sc,green)
    line(cx-2*sc,cy-2*sc+i*sc,cx+2*sc,cy-2*sc+i*sc,green)
text(414,445,'SPAD 尺寸\n对应角域\nH 4 × V 4',16,green)
text(615,150,'02 实际像面 · 截获关系',24)
text(615,188,'像面单位 μm · 所有框线采用同一尺寸比例',17,gray)
# Image plane geometry: focal length 20 mm; detector 80 x 80 um.
px,py,scale=855,486,1.35
line(704,236,704,740,gray);line(704,740,1070,740,gray)
text(627,220,'Y / μm ↑',17,gray);text(990,778,'X / μm →',17,gray)
for v in [-175,-40,0,40,175]:
    y=py-v*scale;line(704,y,1070,y,'#233142');text(639,y-10,str(v),16,gray)
for h in [-80,-40,0,40,80]:
    x=px+h*scale;line(x,740,x,748,gray);text(x-13,751,str(h),16,gray)
box(px-40*scale,py-174.537*scale,80*scale,349.074*scale,blue,'#172939',2)
box(px-30*scale,py-174.537*scale,60*scale,349.074*scale,red,'#39242e',2)
box(px-40*scale,py-40*scale,80*scale,80*scale,green,'transparent',3)
for i in range(1,4):
    line(px-40*scale+i*20*scale,py-40*scale,px-40*scale+i*20*scale,py+40*scale,green)
    line(px-40*scale,py-40*scale+i*20*scale,px+40*scale,py-40*scale+i*20*scale,green)
text(938,296,'Tx 几何像范围\nH 60 × V 349.07 μm',17,red)
text(938,437,'通道探测边界\nH 80 × V 80 μm',17,green)
text(938,581,'配置 Rx 角域\n对应像面范围',17,blue)
line(909,432,1238,331,green,1,True);line(909,540,1238,568,green,1,True)
text(1235,150,'03 SPAD cell 放大',24)
text(1235,190,'每小格 = 1 cell 的完整像元面积',16,gray)
gx,gy,cell=1250,315,75
box(gx,gy,cell*4,cell*4,green,'#122f2a',4)
for i in range(1,4):
    line(gx+i*cell,gy,gx+i*cell,gy+4*cell,green)
    line(gx,gy+i*cell,gx+4*cell,gy+i*cell,green)
text(1250,269,'当前 binning：H 4 × V 4 = 16 cells',18,green)
text(1260,636,'cell pitch：H/V 20 μm\n粗框：一个角通道的 binning 分组\n完整分组尺寸：H 80 × V 80 μm',18)
text(1235,734,'网格不代表 FF = 100%；\nPDE / FF 在候选雪崩阶段应用。',17,gray)
text(32,843,'图例：红 = Tx 几何像范围    蓝 = 配置 Rx 接收角域    绿 = SPAD 完整像元边界 / binning',20)
text(32,891,'截获诊断：滤光后 477.45 → 落入探测面 101.62 光子    |    空间截获率 21.28%',24,green)
text(32,936,'矩形表达几何边界；实际截获率由 Python 的 PSF 积分计算，不用矩形面积比替代。',18,gray)
text(32,974,'交互建议：点选三种框线显示参数来源；hover cell 显示索引；binning 改变时更新网格与粗框。',18,gray)
scene['elements'].extend(new)
payload=json.dumps({'scene':scene,'baseRevision':data['revision']},ensure_ascii=False).encode()
req=urllib.request.Request(URL,payload,{'Content-Type':'application/json'},method='PUT')
result=json.load(urllib.request.urlopen(req))
Path(__file__).parent.joinpath('proposal.excalidraw').write_text(json.dumps({'type':'excalidraw','version':2,'source':'AgentCanvas','elements':new,'appState':{'viewBackgroundColor':'#ffffff'},'files':{}},ensure_ascii=False),encoding='utf-8')
print(json.dumps({'revision':result.get('revision'),'added':len(new),'bounds':[ox,oy,1640,1040]},ensure_ascii=False))
