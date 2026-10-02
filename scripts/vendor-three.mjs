// Local ES modules for the existing FastAPI static server; no CDN/build server.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const pkg=path.join(root,'node_modules','three');
const metadata=JSON.parse(await readFile(path.join(pkg,'package.json'),'utf8'));
const files={};
for(const [source,target] of [
  ['build/three.module.js','three.module.js'],
  ['build/three.core.js','three.core.js'],
  ['examples/jsm/controls/OrbitControls.js','OrbitControls.js'],
  ['LICENSE','LICENSE']
]) files[target]=await readFile(path.join(pkg,source));
files['check.html']=Buffer.from(`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Three.js 本地依赖自检</title>
<style>body{margin:0;background:#101b27;color:#e5edf6;font:16px sans-serif}h1,p{margin:20px}canvas{display:block;max-width:100%}</style>
<h1>Three.js 本地依赖自检</h1><p id="status">正在加载本地模块…</p>
<script type="importmap">{"imports":{"three":"./three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from './OrbitControls.js';
const status=document.querySelector('#status');
try {
 const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setSize(720,400);renderer.setClearColor(0x101b27);document.body.append(renderer.domElement);
 const scene=new THREE.Scene();const camera=new THREE.PerspectiveCamera(45,720/400,.1,100);camera.position.set(3,2,4);
 const cube=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshNormalMaterial());scene.add(cube,new THREE.AxesHelper(2));
 const controls=new OrbitControls(camera,renderer.domElement);controls.update();
 const render=()=>renderer.render(scene,camera);controls.addEventListener('change',render);render();
 status.textContent='已验证：Three.js r'+THREE.REVISION+' / WebGL2 / OrbitControls（可拖动旋转、滚轮缩放）';document.body.dataset.status='passed';
} catch(error) {status.textContent='WebGL验证失败：'+error.message;document.body.dataset.status='failed';}
</script></html>`);
const hash=createHash('sha256');
for(const name of Object.keys(files).sort()) hash.update(name).update('\0').update(files[name]);
const digest=hash.digest('hex');
const base=path.join(root,'web','vendor','three');const dest=path.join(base,digest);
await mkdir(dest,{recursive:true});
for(const [name,bytes] of Object.entries(files)) await writeFile(path.join(dest,name),bytes);
const prefix='/static/vendor/three/'+digest+'/';
const manifest={package:'three',version:metadata.version,license:metadata.license,sha256:digest,
 imports:{three:prefix+'three.module.js','three/addons/controls/OrbitControls.js':prefix+'OrbitControls.js'},
 check_url:prefix+'check.html',
 files:Object.fromEntries(Object.entries(files).map(([name,bytes])=>[name,{bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}]))};
await writeFile(path.join(base,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Three.js '+metadata.version+' ready: '+prefix);
