(async () => {
  const desired = document.documentElement.dataset.auditTheme;
  const original = window.fetch;
  const writes = [];
  window.fetch = function(url, options) {
    if (options?.method && options.method.toUpperCase() !== 'GET') writes.push(String(url));
    return original.apply(this, arguments);
  };
  if (document.documentElement.dataset.theme !== desired) document.querySelector('#themeToggle').click();
  await new Promise(resolve => setTimeout(resolve, 250));
  window.fetch = original;
  const expected = ['spad','budget','a','system','columns'];
  const nav = [...document.querySelectorAll('.platform-nav .platform-link')];
  const current = nav.filter(node => node.disabled);
  const assert = (value, message) => { if (!value) throw Error(message); };
  assert(nav.map(x => x.dataset.platform).join() === expected.join(), '入口顺序错误');
  assert(current.length === 1 && current[0].getAttribute('aria-current') === 'page', '当前入口状态错误');
  assert(nav.filter(x => x.tagName === 'A').length === 4, '可跳转入口数量错误');
  assert(nav.every(x => getComputedStyle(x).borderRadius === '0px'), '导航仍有圆角');
  assert(document.querySelectorAll('#themeToggle').length === 1, '主题按钮重复或缺失');
  assert(document.documentElement.scrollWidth <= innerWidth + 1, '整页横向溢出');
  assert(writes.length === 0, '切换主题/重绘触发了计算请求：' + writes.join());
  const controls = [...document.querySelectorAll('main input[type=number],main select')]
    .filter(x => x.getBoundingClientRect().width > 0);
  assert(controls.every(x => parseFloat(getComputedStyle(x).fontSize) >= 14), '可见输入字号小于14px');
  const tooSmall = [...document.querySelectorAll('main svg text')].filter(t => {
    if (!t.getBoundingClientRect().width) return false;
    const matrix = t.getScreenCTM();
    if (!matrix) return false;
    return parseFloat(getComputedStyle(t).fontSize) * Math.hypot(matrix.a, matrix.b) < 11.8;
  });
  assert(tooSmall.length === 0, 'SVG实际标注仍过小：' + tooSmall.slice(0,3).map(x=>x.textContent).join());
  const smallText = [];
  const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const parent = walker.currentNode.parentElement;
    if (!walker.currentNode.textContent.trim() || parent.closest('svg,.katex,script,style')) continue;
    if (!parent.getBoundingClientRect().width || !parent.getBoundingClientRect().height) continue;
    const size = parseFloat(getComputedStyle(parent).fontSize);
    if (size < 12.8) smallText.push({text:walker.currentNode.textContent.trim().slice(0,40),size});
  }
  return {path:location.pathname, viewport:[innerWidth,innerHeight],theme:desired,
    navigation:nav.map(x=>({text:x.textContent,current:!!x.disabled})),
    inputCount:controls.length,minInputFont:Math.min(...controls.map(x=>parseFloat(getComputedStyle(x).fontSize))),
    horizontalOverflow:false,svgTooSmall:tooSmall.length,smallText:smallText.slice(0,12),writes};
})();
