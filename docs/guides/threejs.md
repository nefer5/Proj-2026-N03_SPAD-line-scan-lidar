# Three.js 项目依赖

已安装并固定 `three@0.186.1`，MIT许可证。按[Three.js官方安装方式](https://threejs.org/manual/pages/installation.html)使用npm包；网页继续由现有FastAPI服务提供，不额外引入开发服务器。

## 位置与恢复

- npm声明及锁文件：根目录 `package.json` / `package-lock.json`。
- 开发安装位置：`node_modules/three/`，Git忽略，不提交安装目录。
- 离线网页资源：`web/vendor/three/<内容SHA256>/`，包含核心ES模块、OrbitControls、LICENSE和独立渲染自检页。
- 当前资源入口：`web/vendor/three/manifest.json`。`imports`可直接作为页面import map的内容，`check_url`为本地自检地址。

在项目根目录执行 `npm ci` 恢复锁定版本，postinstall自动运行 `npm run vendor:three` 同步本地静态资源。也可单独运行后者。同步脚本为 `scripts/vendor-three.mjs`；目录指纹覆盖所复制文件与自检页，模块间的相对引用也落在同一指纹目录中。新版本生成新目录，不自动删除旧资源。

## 使用边界

新三维页面使用 `type="module"` 和上述import map，随后可导入 `three` 和 `three/addons/controls/OrbitControls.js`。新增其他addons时须同步其完整依赖，不直接引用CDN。

Three.js仅负责三维显示与交互；光子预算、扫描几何和物理数值仍由Python公共核心计算。本次只安装并验证绘图库，尚未把现有点云或光路图替换为三维视图。

## 验证

2026-09-28：npm安装完成，Node导入核心与OrbitControls成功；Codex内置浏览器实际显示立方体与坐标轴，WebGL2渲染通过。截图见[渲染证据](../../artifacts/three-install/webgl.png)。
