"""Editable parameter-group review mockup, not a live simulation form."""
import json,time,uuid,urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[2]
audit=json.loads((root/'artifacts/budget-electrical-reference/current-audit.json').read_text(encoding='utf-8'))
c=audit['configuration']['experiment'];s=c['system'];rx=s['rx'];sp=s['spad'];tx=s['tx'];ac=s['acquisition']
u='http://127.0.0.1:4173/api/boards/5586b159-c9c2-4abb-a09c-4ae63dc76fad/scene'
d=json.load(urllib.request.urlopen(u));scene=d['scene'];active=[e for e in scene['elements'] if not e.get('isDeleted')]
ox=max(e['x']+e['width'] for e in active)+180;oy=100
out=[];fg='#dae4ed';muted='#9caebe';cyan='#59d5c9';linecol='#314454';panel='#13212d';inputbg='#0b151e';bg='#0b131b'
def shape(kind,x,y,w,h,col=linecol,fill='transparent',sw=1):
 e=dict(id=uuid.uuid4().hex,type=kind,x=ox+x,y=oy+y,width=w,height=h,angle=0,strokeColor=col,backgroundColor=fill,fillStyle='solid',strokeWidth=sw,strokeStyle='solid',roughness=0,opacity=100,groupIds=[],frameId=None,roundness=None,seed=1,version=1,versionNonce=1,isDeleted=False,boundElements=[],updated=int(time.time()*1000),link=None,locked=False);out.append(e);return e
def text(x,y,value,size=18,col=fg):
 value=str(value);w=max(sum(1.02 if ord(t)>255 else .65 for t in row) for row in value.split('\n'))*size+10
 e=shape('text',x,y,w,len(value.split('\n'))*size*1.3,col);e.update(text=value,originalText=value,fontSize=size,fontFamily=2,textAlign='left',verticalAlign='top',containerId=None,autoResize=True,lineHeight=1.3);return e
def box(x,y,w,h,col=linecol,fill=panel,sw=1):return shape('rectangle',x,y,w,h,col,fill,sw)
def val(x,y,w,label,value):
 text(x,y,label,15,muted);box(x,y+25,w,43,fill=inputbg);text(x+12,y+33,value,19)
def pair(x,y,w,title,unit,h,v,note=None,hlabel='H · 水平',vlabel='V · 垂直'):
 height=140 if note else 116;box(x,y,w,height);text(x+14,y+12,title,18,cyan);text(x+w-70,y+14,unit,15,muted)
 half=(w-42)/2;val(x+14,y+40,half,hlabel,h);val(x+28+half,y+40,half,vlabel,v)
 if note:text(x+14,y+115,note,14,muted)
 return height
def single(x,y,w,title,label,value,note=None):
 height=110 if note else 87;box(x,y,w,height);text(x+14,y+12,title,18,cyan);text(x+14,y+49,label,15,muted);box(x+w-137,y+38,123,38,fill=inputbg);text(x+w-125,y+45,value,19)
 if note:text(x+14,y+84,note,13,muted)
 return height
box(0,0,1630,1280,fill=bg,sw=2)
text(32,23,'参数面板分组 · 审核预览',30)
text(32,73,'同一物理量的成对参数放进一个分组框；左侧始终 H，右侧始终 V。独立量不插入 H/V 配对行。',18,muted)
text(32,108,'数值取现有审计快照，仅示范布局；本次不改网页、计算逻辑或工况默认值。',16,muted)

# Detailed Rx module, including shape-dependent geometry.
x,w=30,510;box(x,155,w,1087)
text(x+16,172,'▾ Rx 接收',24,cyan);text(x+16,207,'折叠摘要：角域 H × V · 入瞳 H × V · 焦距 H × V',15,muted)
y=245
pair(x+14,y,w-28,'单通道收光角域','mrad',c['rx_channel']['h_width_mrad'],'跟随 Tx',note='等价 deg 自动显示；V 可切换为独立输入')
y+=154
box(x+14,y,w-28,178);text(x+28,y+12,'入瞳几何',18,cyan);text(x+28,y+45,'形状',15,muted);box(x+101,y+37,w-129,36,fill=inputbg);text(x+113,y+43,'矩形孔径  ▾',18)
half=(w-70)/2;val(x+28,y+86,half,'H · 全宽 / mm',rx['rx_aperture_width_mm']);val(x+42+half,y+86,half,'V · 全高 / mm',rx['rx_aperture_height_mm'])
y+=192
pair(x+14,y,w-28,'成像焦距','mm',rx['focal_length_h_mm'],rx['focal_length_v_mm']);y+=130
pair(x+14,y,w-28,'PSF 标准差 σ','μm',rx['psf_sigma_h_um'],rx['psf_sigma_v_um']);y+=130
single(x+14,y,w-28,'接收效率','ηRx · 入瞳 → 未截断像面',rx['rx_efficiency'],note='不包含滤光、PSF 截断、PDE 或 FF');y+=124
pair(x+14,y,w-28,'接收 gate','ns',ac['gate_start_ns'],ac['gate_width_ns'],hlabel='起点 / 延迟',vlabel='持续时长');y+=130
text(x+28,y+5,'固定标定延迟 / ns',15,muted);box(x+w-150,y-3,122,35,fill=inputbg);text(x+w-138,y+3,ac['calibration_delay_ns'],18)

# Companion blocks establish the same grammar throughout the panel.
x,w=565,500
box(x,155,w,680);text(x+16,172,'▾ SPAD 与读出',24,cyan)
pair(x+14,218,w-28,'通道内空间 binning','cells',sp['H_binning'],sp['V_binning'],note='自动：H × V = '+str(sp['H_binning']*sp['V_binning'])+' cells / 角通道')
single(x+14,372,w-28,'像元几何','pixel pitch / μm',sp['pixel_pitch_um'],note='自动显示 binning 的 H × V 完整物理尺寸')
single(x+14,496,w-28,'填充因子','FF · 光敏区 / 完整像元',sp['fill_factor'])
pair(x+14,597,w-28,'时间响应','ns / ps',sp['spad_dead_time_ns'],sp['spad_jitter_fwhm_ps'],hlabel='SPAD 死时间 / ns',vlabel='器件抖动 FWHM / ps')
text(x+28,740,'数字读出：模式单独一行；\nTDC bin宽与TDC死时间归入时间参数组。',16,muted)

box(x,855,w,387);text(x+16,872,'▾ 系统目标',24,cyan)
pair(x+14,919,w-28,'系统视场','deg',c['targets']['hfov_deg'],c['geometry']['vfov_deg'])
pair(x+14,1049,w-28,'点云数量','/ frame',c['targets']['slot_count'],sp['channels_v'],note='自动：H/V 采样步距 · 单通道V全角',hlabel='列数 / slot',vlabel='线数 / V通道')

x,w=1090,510
box(x,155,w,380);text(x+16,172,'形状切换后的字段',24,cyan)
single(x+14,220,w-28,'圆形入瞳','只显示直径 D / mm',rx['rx_aperture_mm'])
pair(x+14,321,w-28,'矩形 / 椭圆入瞳','mm',rx['rx_aperture_width_mm'],rx['rx_aperture_height_mm'],hlabel='H · 全宽 / 全轴',vlabel='V · 全高 / 全轴')
text(x+28,453,'未使用的尺寸不占位；切换形状保留原输入。\n椭圆必须注明全轴尺寸，不能写成半轴。',16,muted)

box(x,555,w,435);text(x+16,572,'其余模块采用同一分组方式',24,cyan)
items=[('Tx','脉冲形状 + 脉宽；单通道角域 H / V；\n列内发数 + 发射间隔。'),('电学','拓扑：通道/chip + chip/link；\nlane 容量：lane数 + lane速率 + 净效率；\n输出格式变化时仅显示对应字宽/记录长度。'),('距离参考','扫描范围：最小距离 + 最大距离；\n采样点数另列，实测模式分开。')]
yy=625
for title,desc in items:
 text(x+28,yy,title,18,cyan);text(x+95,yy,desc,16);yy+=100 if title!='电学' else 129

box(x,1010,w,232);text(x+16,1027,'交互与层级',24,cyan)
text(x+28,1074,'• 模块折叠；保留成对值摘要。\n• 分组轻边框、统一间距，不再套一层折叠。\n• 输入在上，单位 / 派生值 / 帮助在组内。\n• 窄屏可竖排，但仍保留同一个分组框。\n• 悬停参数显示定义，点选联动对应示意图。',17,muted)
scene['elements'].extend(out)
req=urllib.request.Request(u,json.dumps({'scene':scene,'baseRevision':d['revision']},ensure_ascii=False).encode(),{'Content-Type':'application/json'},method='PUT');r=json.load(urllib.request.urlopen(req))
here=Path(__file__).parent
here.joinpath('preview.excalidraw').write_text(json.dumps({'type':'excalidraw','version':2,'source':'AgentCanvas','elements':out,'appState':{'viewBackgroundColor':'#ffffff'},'files':{}},ensure_ascii=False),encoding='utf-8')
print(json.dumps({'revision':r.get('revision'),'elements':len(out),'bounds':[ox,oy,1630,1280]},ensure_ascii=False))
