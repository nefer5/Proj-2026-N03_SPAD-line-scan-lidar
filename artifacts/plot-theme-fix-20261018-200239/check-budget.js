(async () => {
  const assert = (ok, why) => { if (!ok) throw Error(why); };
  const hud = document.querySelector('#sceneWorldAxes'), host = document.querySelector('#sceneViewport');
  const writes = [], fetch = window.fetch;
  window.fetch = function(url, options) {
    if (options?.method && options.method !== 'GET') writes.push(String(url));
    return fetch.apply(this, arguments);
  };
  const theme = document.documentElement.dataset.auditTheme;
  if (document.documentElement.dataset.theme !== theme) document.querySelector('#themeToggle').click();
  const views = [];
  for (const scope of ['overview','local']) {
    document.querySelector(`[data-scene-scope="${scope}"]`).click();
    for (const name of ['perspective','front','top','side','detector']) {
    document.querySelector(`[data-scene-view="${name}"]`).click();
    await new Promise(resolve => setTimeout(resolve, 100));
    const h = hud.getBoundingClientRect(), viewport = host.getBoundingClientRect();
    assert(hud.parentElement === host, '三维坐标HUD被通用图表包装');
    assert(!hud.closest('.scientific-figure-scroll'), 'HUD错误进入可滚动图表');
    assert(h.width <= 150 && h.height <= 132, '三维坐标HUD异常放大');
    assert(h.left >= viewport.left && h.right <= viewport.right && h.top >= viewport.top && h.bottom <= viewport.bottom, '坐标HUD超出视图区');
    assert(hud.querySelectorAll('[data-axis-name]').length === 3, '世界坐标缺失');
    for (const label of hud.querySelectorAll('text')) {
      const r = label.getBoundingClientRect();
      assert(r.left >= h.left - 1 && r.right <= h.right + 1 && r.top >= h.top - 1 && r.bottom <= h.bottom + 1, 'HUD文字裁切：'+label.textContent);
    }
    views.push({scope,view:name,width:h.width,height:h.height});
    }
  }
  document.querySelector('[data-scene-view="perspective"]').click();
  document.querySelector('#scenePlay').click();
  await new Promise(resolve => setTimeout(resolve, 250));
  document.querySelector('#scenePlay').click();
  document.querySelector('[data-scene-scope="overview"]').click();
  document.querySelector('[data-scene-view="perspective"]').click();
  window.fetch = fetch;
  assert(writes.length === 0, '主题、镜头或动画触发预算计算');
  assert(document.documentElement.scrollWidth <= innerWidth + 1, '页面横向溢出');
  return {theme,viewport:[innerWidth,innerHeight],views,animation:true,writes};
})();
