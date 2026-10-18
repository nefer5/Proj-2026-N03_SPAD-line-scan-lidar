/* SVG使用用户坐标，窄卡片不能把文字随整张图缩到无法阅读。 */
(() => {
  let pending = false;
  function fitFigures() {
    pending = false;
    for (const svg of document.querySelectorAll('main svg[viewBox]')) {
      // 三维HUD等叠层由组件自己定位，不能套用普通图表的流式尺寸。
      if (svg.dataset.figureLayout === 'fixed-overlay' ||
          ['absolute', 'fixed'].includes(getComputedStyle(svg).position)) continue;
      const text = [...svg.querySelectorAll('text')];
      const width = svg.viewBox.baseVal.width;
      if (!width || !text.length || !svg.getBoundingClientRect().width) continue;
      const font = Math.min(...text.map(node => parseFloat(getComputedStyle(node).fontSize)).filter(Number.isFinite));
      if (!font || !Number.isFinite(font)) continue;
      // 12px为科学图标注的实际显示下限；仅改变绘图可视区，不改变坐标。
      const minimum = Math.ceil(width * 12 / font);
      let host = svg.parentElement;
      if (!host.classList.contains('scientific-figure-scroll')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'scientific-figure-scroll';
        wrapper.tabIndex = 0;
        wrapper.setAttribute('role', 'region');
        wrapper.setAttribute('aria-label', svg.getAttribute('aria-label') || '科学图形，窄窗口可横向滚动');
        host.insertBefore(wrapper, svg); wrapper.append(svg); host = wrapper;
      }
      const value = minimum + 'px';
      if (svg.style.minWidth !== value) svg.style.minWidth = value;
    }
  }
  function schedule() {
    if (!pending) { pending = true; requestAnimationFrame(fitFigures); }
  }
  document.addEventListener('DOMContentLoaded', () => {
    new MutationObserver(records => {
      if (records.some(record => !record.target.closest?.('[data-figure-layout="fixed-overlay"]'))) schedule();
    }).observe(document.querySelector('main'), {childList:true, subtree:true});
    window.addEventListener('resize', schedule);
    schedule();
  });
})();
