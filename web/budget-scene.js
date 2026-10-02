import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

const $=id=>document.getElementById(id);
const fmt=v=>BudgetNumbers.format(v);
const panel=$('schematicPanel'),host=$('sceneViewport');
let renderer,scene,camera,controls,root,packet,model,selected='tx',stale=false,playing=false,visible=true,frame=0,phase=0,lastTime=0,lastStage=-1;
let perspectiveCamera,orthographicCamera;
let pickables=[],labels=[],materials=[],palette={},view='perspective',channel=0,channelGroup=null,scope='overview';
const positions={perspective:[8,5,-12],front:[0,0,-16],top:[0,22,1],side:[-22,0,2],detector:[12,0,0]};
const lookAt={perspective:[0,0,1.5],front:[0,0,6],top:[0,0,3],side:[0,0,3],detector:[4.2,0,0]};
function fail(error){$('sceneError').hidden=false;$('sceneError').textContent='三维显示不可用：'+(error.message||error)+'。预算表和参数仍可正常使用。';$('sceneState').textContent='三维显示不可用';}
function themeColor(name,fallback){return getComputedStyle(document.documentElement).getPropertyValue(name).trim()||fallback;}
function setPalette(){palette={source:themeColor('--tx-color','#e58386'),tx:themeColor('--tx-color','#e58386'),rx:themeColor('--rx-color','#7baff0'),detector:themeColor('--blue','#78aafa'),target:themeColor('--fov-color','#68b5a2'),scan:themeColor('--text','#e2ebf2')};if(renderer)renderer.setClearColor(themeColor('--bg','#0b1118'));}
function material(id,opacity=1){const m=new THREE.MeshBasicMaterial({color:palette[id],transparent:opacity<1,opacity,side:THREE.DoubleSide,depthWrite:opacity===1});m.userData={id,baseOpacity:opacity};materials.push(m);return m;}
function mesh(geometry,mat,id,position){const o=new THREE.Mesh(geometry,mat);o.userData.component=id;if(position)o.position.fromArray(position);root.add(o);pickables.push(o);return o;}
function line(points,id,opacity=1){const m=new THREE.LineBasicMaterial({color:palette[id],transparent:true,opacity});m.userData={id,baseOpacity:opacity};materials.push(m);const o=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p))),m);o.userData.component=id;root.add(o);pickables.push(o);return o;}
function label(id,text,position){const el=document.createElement('button');el.type='button';el.textContent=text;el.setAttribute('aria-label','选择'+text);el.onclick=()=>choose(id,true);$('sceneLabels').append(el);labels.push({id,el,position:new THREE.Vector3(...position)});}
function axisLabel(text,position,color,family,origin,direction){const el=document.createElement('span');el.className='scene-axis-label '+family;el.textContent=text;el.dataset.axisName=text;el.style.color=color;el.setAttribute('aria-label',(family==='angle'?'角方向':'世界坐标')+text);$('sceneLabels').append(el);labels.push({id:'axis',fixed:true,text,origin,direction,el,position:new THREE.Vector3(...position)});}
function directionArrow(origin,direction,length,color,text,family){const start=new THREE.Vector3(...origin),dir=new THREE.Vector3(...direction).normalize();const arrow=new THREE.ArrowHelper(dir,start,length,new THREE.Color(color),.17,.085);arrow.line.material.depthTest=false;arrow.cone.material.depthTest=false;arrow.renderOrder=20;arrow.line.renderOrder=20;arrow.cone.renderOrder=20;root.add(arrow);axisLabel(text,start.clone().addScaledVector(dir,length+.22).toArray(),color,family,start,dir);}
function coordinateArrows(){
 const xcolor=themeColor('--orange','#f4b46d'),ycolor=themeColor('--cyan','#59d9cc');
 // Field H is the opposite of Zemax X; V follows Zemax Y, for every camera.
 const field=[-2.2,-2.5,4.1];directionArrow(field,[-1,0,0],1.5,xcolor,'+H','angle');directionArrow(field,[0,1,0],1.5,ycolor,'+V','angle');
}
function worldAxesHud(){
 const hud=$('sceneWorldAxes');if(!hud)return false;const q=camera.quaternion.clone().invert(),cx=66,cy=68,length=33;let out=false;
 let drawing='<text x="66" y="15" text-anchor="middle" class="axis-hud-caption">XYZ 世界方向</text>';
 for(const [name,vector,color]of [['X',[1,0,0],themeColor('--orange','#f4b46d')],['Y',[0,1,0],themeColor('--cyan','#59d9cc')],['Z',[0,0,1],themeColor('--blue','#78aafa')]]){
  const d=new THREE.Vector3(...vector).applyQuaternion(q),dx=d.x*length,dy=-d.y*length,span=Math.hypot(dx,dy),x=cx+dx,y=cy+dy;let symbol='';
  if(span<7){out=true;symbol=d.z>0?' ⊙':' ⊗';drawing+=`<circle cx="${cx}" cy="${cy}" r="4" fill="none" stroke="${color}"/>`+(d.z>0?`<circle cx="${cx}" cy="${cy}" r="1.3" fill="${color}"/>`:`<path d="M${cx-2} ${cy-2}l4 4M${cx+2} ${cy-2}l-4 4" stroke="${color}"/>`);}
  else{const ux=dx/span,uy=dy/span;drawing+=`<path d="M${cx} ${cy}L${x} ${y}" stroke="${color}"/><path d="M${x} ${y}L${x-ux*6-uy*2.5} ${y-uy*6+ux*2.5}L${x-ux*6+uy*2.5} ${y-uy*6-ux*2.5}Z" fill="${color}"/>`;}
  const tx=span<7?cx+21:cx+dx*(1+10/span),ty=span<7?cy+18:cy+dy*(1+10/span)+3;
  drawing+=`<text x="${tx}" y="${ty}" fill="${color}" text-anchor="middle" class="axis-hud-label" data-axis-name="+${name}">+${name}${symbol}</text>`;
 }
 hud.innerHTML=drawing;return out;
}
function vcselChip(){
 const origin=model.source_position,at=(x,y,z)=>[origin[0]+x,origin[1]+y,origin[2]+z];
 const substrate=material('source',.96);substrate.color.copy(new THREE.Color(palette.detector).lerp(new THREE.Color(themeColor('--bg','#0b1118')),.62));
 const body=mesh(new THREE.BoxGeometry(.92,1.76,.055),substrate,'source',origin);
 const rim=new THREE.LineBasicMaterial({color:new THREE.Color(palette.source).lerp(new THREE.Color(themeColor('--text','#e2ebf2')),.35),transparent:true,opacity:.9});rim.userData={id:'source',baseOpacity:.9};materials.push(rim);
 const edge=new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry),rim);edge.position.fromArray(origin);edge.userData.component='source';root.add(edge);
 const die=material('source',.82);die.color.copy(new THREE.Color(palette.source).lerp(new THREE.Color(themeColor('--bg','#0b1118')),.7));
 mesh(new THREE.BoxGeometry(.58,1.47,.013),die,'source',at(0,0,.034));
 mesh(new THREE.BoxGeometry(.15,1.34,.007),material('source',.7),'source',at(0,0,.045));
 const emitter=material('source',1);emitter.color.copy(new THREE.Color(palette.source).lerp(new THREE.Color(themeColor('--text','#e2ebf2')),.64));
 const dots=new THREE.CircleGeometry(.036,16);for(let i=0;i<12;i++)mesh(dots,emitter,'source',at(0,-.615+i*1.23/11,.052));
 const contacts=material('source',1);contacts.color.set(themeColor('--orange','#f4b46d'));const pad=new THREE.BoxGeometry(.13,.085,.014);
 for(let i=0;i<6;i++)for(const x of [-.29,.29])mesh(pad,contacts,'source',at(x,-.61+i*1.22/5,-.034));
 label('source','VCSEL芯片 · 线阵',at(0,1.15,0));
}
function quad(points,id,opacity){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points.flat(),3));g.setIndex([0,1,2,0,2,3]);return mesh(g,material(id,opacity),id);}
function cone(points,id){for(let i=0;i<4;i++){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute([...model.origin,...points[i],...points[(i+1)%4]],3));mesh(g,material(id,.035),id);line([model.origin,points[i]],id,.5);}line([...points,points[0]],id,.95);}
function ramp(value,id){const base=new THREE.Color(palette[id]);const bg=new THREE.Color(themeColor('--bg','#0b1118'));return bg.lerp(base,.12+.88*value);}
function heatmap(){for(const cell of model.tx_cells){const obj=quad(cell.vertices,'tx',.92);obj.material.color.copy(ramp(cell.relative_density,'tx'));obj.material.userData.relative=cell.relative_density;obj.userData.fraction=cell.fraction;obj.userData.power=cell.power_w;obj.renderOrder=2;}}
function detector(){const pos=model.detector_position;const [w,h]=model.detector_size;const plate=mesh(new THREE.BoxGeometry(.13,h+.15,w+.15),material('detector',.3),'detector',pos);plate.position.x-=.12;
 if(model.detector_cells.length){const mat=material('detector',1);mat.userData.instances=true;mat.color.set(0xffffff);const inst=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,.045),mat,model.detector_cells.length);const transform=new THREE.Object3D();transform.rotation.y=Math.PI/2;model.detector_cells.forEach((c,i)=>{transform.position.fromArray(c.center);transform.scale.set(c.size[0]*.91,c.size[1]*.91,1);transform.updateMatrix();inst.setMatrixAt(i,transform.matrix);inst.setColorAt(i,ramp(c.relative_energy,'detector'));});inst.instanceMatrix.needsUpdate=true;inst.instanceColor.needsUpdate=true;inst.userData.component='detector';root.add(inst);pickables.push(inst);}
 label('detector','SPAD · 独立放大',[pos[0],pos[1]+h/2+.45,pos[2]]);
}
function disposeRoot(){if(!root)return;const gs=new Set(),ms=new Set();root.traverse(o=>{if(o.geometry)gs.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>ms.add(m));});gs.forEach(g=>g.dispose());ms.forEach(m=>m.dispose());scene.remove(root);$('sceneLabels').replaceChildren();labels=[];pickables=[];materials=[];}
function rebuild(){disposeRoot();root=new THREE.Group();scene.add(root);setPalette();
 if(scope==='local'){line(model.scan_fan.boundary,'scan',.5);label('scan','HFOV扇区参考 · 独立缩放',[0,-3.4,2]);}
 const grid=new THREE.GridHelper(16,16,new THREE.Color(palette.target),new THREE.Color(palette.target));grid.position.set(0,-3.3,3);grid.material.transparent=true;grid.material.opacity=.13;root.add(grid);
 if(scope==='local')mesh(new THREE.PlaneGeometry(9,9),material('target',.025),'target',[0,0,8.03]);
 if(scope==='overview')buildWholeField();else{cone(model.rx_corners,'rx');cone(model.tx_corners,'tx');heatmap();}
 // Exploded device glyphs, deliberately distinct from calibrated ray geometry.
 vcselChip();
 const mirror=mesh(new THREE.BoxGeometry(1,.8,.09),material('scan',.7),'scan',model.origin);mirror.rotation.y=.55;
 label('scan','转镜 / 角度原点',[0,-.95,0]);
 const pupilGeometry=model.pupil_shape==='rectangle'?new THREE.PlaneGeometry(...model.pupil_size):new THREE.CircleGeometry(.5,48);
 const pupil=mesh(pupilGeometry,material('rx',.5),'rx',model.pupil_position);
 pupil.rotation.y=Math.PI/2;
 if(model.pupil_shape!=='rectangle')pupil.scale.set(...model.pupil_size,1);
 label('rx','Rx入瞳 · 展开示意',[2.2,1.05,0]);
 detector();
 line([model.source_position,model.origin],'source',.5);line([model.origin,model.pupil_position,model.detector_position],'rx',.5);
 label('tx',scope==='overview'?'整帧视场 · HFOV × VFOV':'Tx整列 / 单通道角域',scope==='overview'?[0,3.6,8]:[model.tx_corners[2][0],model.tx_corners[2][1]+.5,8]);
 label('target','目标参考面',scope==='overview'?[0,-3.6,8]:[model.rx_corners[0][0],model.rx_corners[0][1]-.7,8]);
 coordinateArrows();
 packet=mesh(new THREE.SphereGeometry(.1,12,8),new THREE.MeshBasicMaterial({color:palette.tx}),'source');packet.visible=false;pickables.pop();
 applyVisibility();paintSelection();updateChannel();render();
}
function buildWholeField(){for(const vertices of model.views.surface){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setIndex([0,1,2,0,2,3]);mesh(g,material('target',.06),'target');}for(const points of model.views.lines)line(points,'target',.25);}
function selectionLine(points,color,opacity=1){const g=new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p)));channelGroup.add(new THREE.Line(g,new THREE.LineBasicMaterial({color,transparent:true,opacity})));}
function selectionFace(points,color,opacity=.25){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points.flat(),3));g.setIndex([0,1,2,0,2,3]);channelGroup.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({color,transparent:true,opacity,side:THREE.DoubleSide,depthWrite:false})));}
function updateChannel(){if(!root||!model?.channel_regions)return;if(channelGroup){root.remove(channelGroup);channelGroup.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});}channelGroup=new THREE.Group();root.add(channelGroup);const c=model.channel_regions[channel],slot=Number($('sceneSlot').value),column=model.views.column_regions[slot];
 if(scope==='local'){for(const [id,points]of [['tx',c.tx_corners],['rx',c.rx_corners]]){if(!$(id==='tx'?'sceneShowTx':'sceneShowRx').checked)continue;selectionLine([...points,points[0]],palette[id]);selectionFace(points,palette[id]);}if(model.scan_fan.columns[slot])selectionLine([model.scan_fan.origin,model.scan_fan.columns[slot].point],palette.scan);}
 else{selectionLine(model.views.channels[channel].full_band,palette.target,1);if(column)for(const id of ['tx','rx']){if(!$(id==='tx'?'sceneShowTx':'sceneShowRx').checked)continue;const points=column[id+'_corners'];selectionLine([...points,points[0]],palette[id]);selectionFace(points,palette[id],.35);selectionLine([model.origin,points[0]],palette[id],.5);selectionLine([model.origin,points[3]],palette[id],.5);}}
 if(c.detector_corners)selectionLine([...c.detector_corners,c.detector_corners[0]],palette.detector);
 $('sceneSelectionNote').textContent='V'+channel+' / '+model.channel_regions.length+' · 列 '+slot+' / '+model.slot_count+(model.scan_fan.columns[slot]?' · H中心 '+fmt(model.scan_fan.columns[slot].h_mrad)+' mrad':'')+' · '+(scope==='overview'?'整帧视场':'局部放大');$('sceneCenterAnglesDeg').textContent='等价中心角：'+(model.scan_fan.columns[slot]?'H '+fmt(model.scan_fan.columns[slot].h_deg)+' / ':'')+'V '+fmt(model.views.channels[channel].v_center_deg)+' deg';renderDetails();render();}
function svg(body,label){return '<svg viewBox="0 0 332 172" role="img" aria-label="'+label+'">'+body+'</svg>';}
function renderDetails(){const d=model.views,c=d.channels[channel],p=d.local,column=d.column_regions[Number($('sceneSlot').value)];
 let full='<rect x="34" y="24" width="264" height="116" class="detail-frame"/>';
 for(const row of d.chart.channels)full+=`<rect x="34" y="${row.y}" width="264" height="${row.height}" class="detail-row" data-channel="${row.index}" role="button" tabindex="0" aria-label="选择V${row.index}角通道"/>`;
 for(const col of d.chart.columns)full+=`<path d="M${col.x} 24V140" class="detail-grid"/>`;
 full+=`<rect x="34" y="${c.full_chart_y}" width="264" height="${c.full_chart_height}" class="detail-selected-row"/>`;
 if(column)full+=`<path d="M${column.chart_x} 24V140" class="detail-selected-column"/>`;
 full+=`<text x="34" y="158">−H</text><text x="245" y="158">+H →</text><text x="8" y="20">+V</text><text x="4" y="144">−V</text><text x="108" y="16">${fmt(d.hfov_deg)} × ${fmt(d.vfov_deg)} deg</text>`;
 for(let i=0;i<=4;i++){const hv=-d.hfov_deg/2+d.hfov_deg*i/4,vv=-d.vfov_deg/2+d.vfov_deg*i/4;full+=`<text x="${34+264*i/4}" y="168" text-anchor="middle">${fmt(hv)}</text><text x="30" y="${140-116*i/4+3}" text-anchor="end">${fmt(vv)}</text>`;}
 $('sceneFullChart').innerHTML=svg(full,'整机HFOV与VFOV、当前列和V通道');for(const e of $('sceneFullChart').querySelectorAll('[data-channel]')){e.onclick=()=>{channel=Number(e.dataset.channel);$('sceneChannel').value=String(channel);pause();updateChannel();};e.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();e.onclick();}};}
 const rect=(r,id)=>`<rect x="${r[0]}" y="${r[1]}" width="${r[2]}" height="${r[3]}" class="detail-domain ${id}"/>`;

 $('sceneMismatch').textContent=d.explanation;$('sceneMismatch').classList.toggle('different',!d.same_v_width);$('sceneFollowRx').disabled=d.rx_v_follows_tx;
 renderDetectorView(d.detector_view);
 const hp=d.h_profile;let hbody='<path d="M44 25V134H308" class="detail-axis"/><text x="8" y="43">1</text><text x="8" y="137">0</text><text x="44" y="18">相对Tx强度</text>';
 for(const tick of hp.ticks)hbody+=`<path d="M${tick.x} 134v5" class="detail-frame"/><text x="${tick.x}" y="151" text-anchor="middle">${fmt(tick.value)}</text>`;
 for(const r of hp.neighbors)hbody+=rect(r,'tx neighboring');hbody+=rect(hp.rx_rect,'rx dashed');hbody+=`<polyline points="${hp.tx_path.map(v=>v.join(',')).join(' ')}" class="detail-tx-line"/><path d="M${hp.step_bracket[0]} 173v8M${hp.step_bracket[0]} 177H${hp.step_bracket[1]}M${hp.step_bracket[1]} 173v8" class="detail-axis"/><text x="176" y="198" text-anchor="middle">ΔH列间距 ${fmt(hp.step_mrad)} mrad</text><text x="253" y="167">H / mrad →</text>`;
 $('sceneHorizontalChart').innerHTML=diagram(hbody,'Tx/Rx水平角宽与扫描列间距对照',210);$('sceneHorizontalNote').textContent='Tx H '+fmt(p.tx_h_mrad)+' / Rx H '+fmt(p.rx_h_mrad)+' mrad；Rx角宽 / ΔH = '+fmt(hp.rx_to_step_ratio)+'。淡框为相邻列Tx；角宽比不是独立分辨单元数。';
 renderImageMapping(d,c);

}
function renderDetectorView(d){
 if(!d){$('sceneDetectorChart').textContent='双坐标几何数据未加载，请重新计算或重启旧服务。';return;}
 const low=d.angle_limits_mrad[0],high=d.angle_limits_mrad[1],left=112,top=80,size=430,scale=size/(high-low),x=v=>left+(v-low)*scale,y=v=>top+(high-v)*scale;
 const label=(px,py,t,cl='',anchor='start')=>`<text x="${px}" y="${py}" class="${cl}" text-anchor="${anchor}">${t}</text>`;
 const box=(b,cl,title='')=>`<rect x="${x(b.h_min)}" y="${y(b.v_max)}" width="${(b.h_max-b.h_min)*scale}" height="${(b.v_max-b.v_min)*scale}" class="${cl}">${title?'<title>'+title+'</title>':''}</rect>`;
 let b='';for(const t of d.ticks){const xx=x(t.angle_mrad),yy=y(t.angle_mrad);b+=`<path d="M${xx} ${top}V${top+size}M${left} ${yy}H${left+size}" class="detector-grid"/>`+label(xx,top+size+23,fmt(t.angle_mrad),'detector-angle','middle')+label(left-12,yy+4,fmt(t.angle_mrad),'detector-angle','end')+label(xx,top-14,fmt(t.image_x_um),'detector-image','middle')+label(left+size+12,yy+4,fmt(t.image_y_um),'detector-image');}
 b+=box(d.rx_bounds,'detector-rx','配置Rx角域')+box(d.tx_bounds,'detector-tx','Tx归一化角域');
 for(const cell of d.cells)b+=box(cell,'detector-cell','cell H'+cell.h_index+' / V'+cell.v_index);
 b+=box(d.binning_bounds,'detector-binning','一个角通道的binning边界');
 b+=`<path d="M${left} ${top}V${top+size}H${left+size}" class="detail-axis"/>`+label(left+size/2,top+size+52,'角度 H / mrad','detector-angle','middle')+label(11,top+size/2,'角度 V','detector-angle')+label(11,top+size/2+19,'/ mrad','detector-angle')+label(left+size/2,24,'像面 X / μm'+(d.mapping_mode==='inverted'?'（倒置）':''),'detector-image','middle')+label(left+size+71,top+size/2-10,'像面 Y','detector-image')+label(left+size+71,top+size/2+10,'/ μm','detector-image');
 $('sceneDetectorChart').innerHTML=`<svg class="detector-diagram" viewBox="0 0 710 590" role="img" aria-label="来自后台计算的单通道Tx、Rx和SPAD cell/binning双坐标对照">${b}</svg>`;
 $('sceneDetectorFacts').innerHTML=`<span class="detector-tx-label">Tx H ${fmt(d.tx_h_mrad)} × V ${fmt(d.tx_v_mrad)} mrad<small>等价 H ${fmt(d.tx_h_deg)} × V ${fmt(d.tx_v_deg)} deg</small></span><span class="detector-rx-label">Rx H ${fmt(d.rx_h_mrad)} × V ${fmt(d.rx_v_mrad)} mrad<small>等价 H ${fmt(d.rx_h_deg)} × V ${fmt(d.rx_v_deg)} deg</small></span><span class="detector-cell-label">SPAD H ${d.binning_h} × V ${d.binning_v} cells<small>尺寸 ${fmt(d.detector_h_um)} × ${fmt(d.detector_v_um)} μm · pitch ${fmt(d.pixel_pitch_um)} μm</small><small>对应 H ${fmt(d.detector_h_mrad)} × V ${fmt(d.detector_v_mrad)} mrad</small></span>`;
 $('sceneDetectorNote').textContent=(d.capture_fraction===null?'无滤光后信号，截获率不定义。':'PSF空间截获率 '+fmt(d.capture_fraction*100)+'%。')+d.note+(d.cells_omitted?' cell数超过显示上限，仅显示binning外框；计算未降采样。':'');
}
function renderImageMapping(d,c){
 const n=model.channel_regions.length,left=100,lens=270,right=434,top=74,bottom=270,span=bottom-top,mid=(top+bottom)/2;
 const groupY=i=>bottom-(i+.5)*span/n,ty=groupY(channel),iy=groupY(c.detector_group);
 const label=(x,y,t,kind='',anchor='start')=>`<text x="${x}" y="${y}" class="${kind}" text-anchor="${anchor}">${t}</text>`;
 let body=label(left,27,'视场 V / deg','mapping-heading','middle')+label(lens,27,'Rx 成像','mapping-heading','middle')+label(right,27,'SPAD Y / μm','mapping-heading','middle');
 body+=`<path d="M${left} ${top}V${bottom}M${right} ${top}V${bottom}" class="detail-axis"/>`;
 for(let i=0;i<=4;i++){const y=bottom-span*i/4,v=-d.vfov_deg/2+d.vfov_deg*i/4,um=-d.detector_half_height_um+2*d.detector_half_height_um*i/4;body+=`<path d="M${left-5} ${y}H${right+5}" class="mapping-grid"/>`+label(left-12,y+4,fmt(v),'mapping-angle','end')+label(right+25,y+4,fmt(um),'mapping-image');}
 const inverted=model.imageMappingMode==='inverted';
 body+=`<path d="M${left} ${top}L${lens} ${mid}L${right} ${inverted?bottom:top}M${left} ${bottom}L${lens} ${mid}L${right} ${inverted?top:bottom}" class="ray-guide mapping-guide"/><ellipse cx="${lens}" cy="${mid}" rx="12" ry="86" class="detail-lens"/>`;
 for(const row of d.chart.channels){const y=bottom-(row.index+1)*span/n;body+=`<rect x="${right-9}" y="${y+span/n*.08}" width="18" height="${span/n*.84}" rx="1" class="detail-pixel"/>`;}
 body+=`<path d="M${left} ${ty}L${lens} ${mid}L${right} ${iy}" class="detail-ray mapping-selected-ray"/><circle cx="${left}" cy="${ty}" r="5" class="detail-dot"/><rect x="${right-13}" y="${iy-span/n*.42}" width="26" height="${Math.max(3,span/n*.84)}" rx="1" class="detail-selected-pixel"/>`;
 body+=`<rect x="67" y="300" width="190" height="34" rx="6" class="mapping-caption-box"/><rect x="285" y="300" width="230" height="34" rx="6" class="mapping-caption-box"/>`+label(162,322,'V'+channel+' · '+fmt(c.v_center_deg)+' deg','mapping-caption','middle')+label(400,322,'SPAD 分组 '+c.detector_group,'mapping-caption','middle');
 body+=label(lens,322,'→','mapping-heading','middle')+label(280,364,(inverted?'+V → −Y · 倒置映射':'+V → +Y · 同向映射')+'；两侧坐标分别缩放','mapping-note','middle');
 $('sceneImageChart').innerHTML=`<svg class="mapping-diagram" viewBox="0 0 560 385" role="img" aria-label="整条V视场的角度坐标为deg、SPAD像面为微米；当前通道与分组映射">${body}</svg>`;
}
function diagram(body,label,height){return '<svg viewBox="0 0 350 '+height+'" role="img" aria-label="'+label+'">'+body+'</svg>';}

function updateLabels(){const occupied=[];let normalAxis=false;for(const l of [...labels].sort((a,b)=>Number(Boolean(b.fixed))-Number(Boolean(a.fixed))||(b.id===selected)-(a.id===selected))){const p=l.position.clone().project(camera);l.el.hidden=p.z>1||p.z< -1||p.x< -1||p.x>1||p.y< -1||p.y>1;if(l.el.hidden)continue;if(l.fixed){const o=l.origin.clone().project(camera),short=Math.hypot((p.x-o.x)*host.clientWidth/2,(p.y-o.y)*host.clientHeight/2)<12;const toward=l.direction.dot(camera.position.clone().sub(l.origin))>0;l.el.textContent=l.text+(short?(toward?' ⊙':' ⊗'):'');l.el.title=short?(toward?'朝向观察者':'背离观察者'):'三维正方向';normalAxis||=short;}const w=l.el.offsetWidth,h=l.el.offsetHeight;const x=l.fixed?(p.x*.5+.5)*host.clientWidth:Math.max(w/2+8,Math.min(host.clientWidth-w/2-8,(p.x*.5+.5)*host.clientWidth));let y=l.fixed?(-p.y*.5+.5)*host.clientHeight:Math.max(h/2+8,Math.min(host.clientHeight-h/2-55,(-p.y*.5+.5)*host.clientHeight));for(let n=0;!l.fixed&&n<8;n++){if(!occupied.some(r=>Math.abs(r.x-x)<(r.w+w)/2+5&&Math.abs(r.y-y)<(r.h+h)/2+5))break;y-=h+7;if(y<h/2+8)y=host.clientHeight-h/2-60;}l.el.style.left=x+'px';l.el.style.top=y+'px';l.el.classList.toggle('selected',l.id===selected);occupied.push({x,y,w,h});}normalAxis=worldAxesHud()||normalAxis;panel.querySelector('.scene-compass').textContent='世界轴 X/Y/Z（Zemax） · +H = −X · +V = +Y · +Z 朝场景'+(normalAxis?' · ⊙朝向观察者 / ⊗背离观察者':'');}
function render(){if(!renderer||!visible)return;renderer.render(scene,camera);updateLabels();}
function resize(){if(!renderer)return;const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);if(camera.isOrthographicCamera){const span=Math.max(16,16/(w/h));camera.left=-span*w/h/2;camera.right=span*w/h/2;camera.top=span/2;camera.bottom=-span/2;}else camera.aspect=w/h;camera.updateProjectionMatrix();render();}
function applyVisibility(){if(!root)return;root.traverse(o=>{const id=o.userData.component;if(id==='tx')o.visible=$('sceneShowTx').checked;if(id==='rx')o.visible=$('sceneShowRx').checked;});}
function paintSelection(){for(const m of materials){const active=m.userData.id===selected;m.opacity=m.userData.baseOpacity*(active?1:.48);m.transparent=true;if(active&&m.userData.baseOpacity<.1)m.opacity=.13;}
 for(const b of $('sceneParts').children)b.setAttribute('aria-pressed',String(b.dataset.component===selected));render();}
function relatedInputs(component){return [...document.querySelectorAll('[data-path]')].filter(el=>component.paths.some(p=>el.dataset.path===p||el.dataset.path.startsWith(p+'.')));}
function focusInput(el){const d=el.closest('details');if(d)d.open=true;el.scrollIntoView({block:'nearest',behavior:'smooth'});el.focus({preventScroll:true});}
function choose(id,focusForm=false){if(!model)return;if(focusForm)pause();const c=model.components.find(c=>c.id===id);if(!c)return;selected=id;
 $('sceneStep').textContent=stale?'显示上次有效配置 · 当前表单待计算':'参数联动 · '+id.toUpperCase();$('sceneTitle').textContent=c.title;$('sceneDescription').textContent=c.description;
 $('sceneFacts').replaceChildren();for(const fact of c.facts){const row=document.createElement('div');row.className='scene-fact';const label=document.createElement('span');label.textContent=fact.label;const value=document.createElement('strong');value.textContent=fmt(fact.value)+' '+fact.unit;row.append(label,value);$('sceneFacts').append(row);}
 document.querySelectorAll('.scene-linked').forEach(e=>e.classList.remove('scene-linked'));const inputs=relatedInputs(c);for(const el of inputs)el.classList.add('scene-linked');$('sceneParamLinks').replaceChildren();for(const el of inputs.slice(0,5)){const b=document.createElement('button');b.type='button';b.textContent=el.getAttribute('aria-label');b.onclick=()=>focusInput(el);$('sceneParamLinks').append(b);}
 if(focusForm){document.querySelector('.scene-inspector').scrollTop=0;if(inputs[0])focusInput(inputs[0]);}paintSelection();
}
function pathSelected(path){if(!model)return;let best=null,length=-1;for(const c of model.components)for(const p of c.paths)if((path===p||path.startsWith(p+'.'))&&p.length>length){best=c.id;length=p.length;}if(best){pause();choose(best);}}
function viewAt(name){view=name;for(const b of document.querySelectorAll('[data-scene-view]'))b.setAttribute('aria-pressed',String(b.dataset.sceneView===name));camera=['front','top','side'].includes(name)?orthographicCamera:perspectiveCamera;controls.object=camera;resize();camera.up.set(0,name==='top'?0:1,name==='top'?1:0);camera.position.fromArray(positions[name]);controls.target.fromArray(lookAt[name]);if(camera.isPerspectiveCamera&&name==='perspective'){const factor=Math.max(1,1.25/camera.aspect);camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target);}controls.update();render();}
function pause(){playing=false;cancelAnimationFrame(frame);frame=0;if(packet)packet.visible=false;$('scenePlay').textContent='▶ 传播示意';$('scenePlay').setAttribute('aria-pressed','false');if(model)$('sceneAnimation').textContent=stale?'参数已改：等待有效计算后更新三维图':'拖动旋转 · 滚轮缩放 · 点击部件查看含义';render();}
function animate(now){if(!playing||!visible||document.hidden)return;const dt=lastTime?(now-lastTime)/1000:0;lastTime=now;phase=(phase+Math.min(dt,.1)/4.8)%1;
 const path=model.channel_regions[channel].animation_path;const segment=phase*(path.length-1),index=Math.floor(segment),t=segment-index;packet.visible=index<2||model.return_path_available;packet.position.fromArray(path[index]).lerp(new THREE.Vector3(...path[index+1]),t);packet.material.color.set(index<2?palette.tx:palette.rx);
 const stages=['光源输出 → 角度原点','照明沿Tx角域到达目标','目标回波 → 角度原点','Rx接收 → 入瞳','接收光 → SPAD探测面'];
 $('sceneAnimation').textContent='讲解动画 · '+stages[index]+(model.return_path_available?'':'（当前采样角无Tx/Rx重叠，不画回波）');
 if(index!==lastStage){lastStage=index;choose(['source','tx','rx','rx','detector'][index]);}
 render();frame=requestAnimationFrame(animate);
}
function togglePlay(){if(scope==='overview'&&!playing){scope='local';for(const b of document.querySelectorAll('[data-scene-scope]'))b.setAttribute('aria-pressed',String(b.dataset.sceneScope===scope));rebuild();choose(selected);}if(playing){pause();return;}if(!model||stale||!model.animation_allowed)return;playing=true;phase=0;lastTime=0;lastStage=-1;$('scenePlay').textContent='Ⅱ 暂停动画';$('scenePlay').setAttribute('aria-pressed','true');frame=requestAnimationFrame(animate);}
function update(payload){if(!payload?.schematic)return;try{pause();if(!model)channel=Math.floor(payload.schematic.channel_regions.length/2);model=payload.schematic;model.imageMappingMode=payload.mappingMode;channel=Math.min(channel,model.channel_regions.length-1);$('sceneChannel').replaceChildren();for(const c of model.channel_regions){const o=document.createElement('option');o.value=String(c.index);o.textContent='V'+c.index;$('sceneChannel').append(o);}$('sceneChannel').value=String(channel);$('sceneSlot').max=model.slot_count-1;if(!$('sceneSlot').value||Number($('sceneSlot').value)>=model.slot_count)$('sceneSlot').value=String(Math.floor(model.slot_count/2));stale=false;$('sceneAnimation').textContent='拖动旋转 · 滚轮缩放 · 点击部件查看含义';panel.classList.remove('scene-stale');$('sceneState').textContent='当前配置 · '+payload.fingerprint.slice(0,10);$('sceneScope').textContent=model.note;
 $('sceneScale').textContent=`角域横向放大 ${fmt(model.scale.angular_exaggeration)} 倍（相对纵深，H/V同比例）。${model.density_label}。${model.display_notes.join(' ')} 整帧视场使用柱面角坐标示意，V方向放大 ${fmt(model.views.vertical_exaggeration)} 倍；下方单通道图H/V同比例。`;
 $('sceneParts').replaceChildren();for(const c of model.components){const b=document.createElement('button');b.type='button';b.dataset.component=c.id;b.textContent=({source:'光源',tx:'Tx角域',rx:'Rx收光',detector:'SPAD',target:'目标',scan:'转镜'})[c.id];b.onclick=()=>choose(c.id,true);$('sceneParts').append(b);}
 rebuild();choose(selected);$('scenePlay').disabled=!model.animation_allowed;if(!model.animation_allowed)$('sceneAnimation').textContent='光源功率为0：保留角分布形状，关闭传播动画。';}catch(e){fail(e);}}
function markStale(){stale=true;pause();panel.classList.add('scene-stale');$('sceneState').textContent='参数已改 · 显示上次有效配置';$('scenePlay').disabled=true;if(model)choose(selected);}
try{
 setPalette();renderer=new THREE.WebGLRenderer({canvas:$('sceneCanvas'),antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));scene=new THREE.Scene();perspectiveCamera=new THREE.PerspectiveCamera(42,1,.1,150);orthographicCamera=new THREE.OrthographicCamera(-8,8,8,-8,.1,150);camera=perspectiveCamera;controls=new OrbitControls(camera,renderer.domElement);controls.minDistance=3;controls.maxDistance=45;controls.enableDamping=false;controls.addEventListener('change',render);viewAt(view);resize();
 let down;renderer.domElement.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});renderer.domElement.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;const rect=renderer.domElement.getBoundingClientRect();const ray=new THREE.Raycaster();ray.params.Line.threshold=.12;ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),camera);const hit=ray.intersectObjects(pickables).find(h=>h.object.visible);if(hit)choose(hit.object.userData.component,true);});
 renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();pause();fail('WebGL上下文丢失，请刷新页面恢复');});
 new ResizeObserver(resize).observe(host);new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){render();if(playing){lastTime=0;cancelAnimationFrame(frame);frame=requestAnimationFrame(animate);}}else cancelAnimationFrame(frame);}).observe(host);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelAnimationFrame(frame);else if(playing&&visible){lastTime=0;frame=requestAnimationFrame(animate);}});
 document.addEventListener('focusin',e=>{if(e.target.dataset?.path||e.target.dataset?.focusPath)pathSelected(e.target.dataset.path||e.target.dataset.focusPath);else{const curve=e.target.closest?.('[id^="curve-"]');if(curve)pathSelected('system.spectral_inputs.'+curve.id.slice(6));}});
 $('sceneChannel').onchange=()=>{channel=Number($('sceneChannel').value);pause();updateChannel();choose('detector');};$('sceneSlot').oninput=()=>{if(!Number.isInteger(Number($('sceneSlot').value))||Number($('sceneSlot').value)<0||Number($('sceneSlot').value)>=model.slot_count){$('sceneSlot').setCustomValidity('选择有效的点云列索引');return;}$('sceneSlot').setCustomValidity('');updateChannel();choose('scan');};for(const button of document.querySelectorAll('[data-detail-target]'))button.onclick=()=>{const inspector=document.querySelector('.scene-inspector'),target=$(button.dataset.detailTarget);target.scrollIntoView({block:'center',behavior:'smooth'});};$('sceneFollowRx').onclick=()=>document.getElementById('followRxV').click();for(const b of document.querySelectorAll('[data-scene-scope]'))b.onclick=()=>{scope=b.dataset.sceneScope;for(const other of document.querySelectorAll('[data-scene-scope]'))other.setAttribute('aria-pressed',String(other===b));pause();rebuild();choose(selected);viewAt('perspective');};$('scenePlay').onclick=togglePlay;$('sceneReset').onclick=()=>viewAt('perspective');for(const b of document.querySelectorAll('[data-scene-view]'))b.onclick=()=>viewAt(b.dataset.sceneView);for(const id of ['sceneShowTx','sceneShowRx'])$(id).onchange=()=>{applyVisibility();updateChannel();render();};
 window.addEventListener('lidar-theme-change',()=>{if(model){rebuild();choose(selected);}else setPalette();});
 window.addEventListener('budget-scene-update',e=>update(e.detail));window.addEventListener('budget-scene-stale',markStale);window.addEventListener('beforeunload',()=>{pause();disposeRoot();controls.dispose();renderer.dispose();});
 if(window.budgetScenePayload)update(window.budgetScenePayload);
}catch(e){fail(e);}
