/* Presentation only. Runs before page scripts to avoid a wrong-theme flash. */
(() => {
  const key = 'spad-lidar-theme';
  const root = document.documentElement;
  let theme = 'dark';
  const cache = new Map();
  try { if (localStorage.getItem(key) === 'light') theme = 'light'; } catch {}
  root.dataset.theme = theme;
  let button;
  function updateButton() {
    if (!button) return;
    button.textContent = theme === 'dark' ? '☀ 浅色' : '☾ 深色';
    button.setAttribute('aria-label', theme === 'dark' ? '切换到浅色配色' : '切换到深色配色');
    button.setAttribute('aria-pressed', String(theme === 'light'));
    button.title = theme === 'dark' ? '当前深色，切换到浅色' : '当前浅色，切换到深色';
  }
  function apply(next, persist) {
    theme = next === 'light' ? 'light' : 'dark';
    root.dataset.theme = theme;
    cache.clear();
    updateButton();
    if (persist) { try { localStorage.setItem(key, theme); } catch { button.title += '（浏览器禁止保存偏好）'; } }
    window.dispatchEvent(new CustomEvent('lidar-theme-change', {detail: {theme}}));
    // Existing renderers already repaint on resize, without running a simulation.
    window.dispatchEvent(new Event('resize'));
  }
  globalThis.LidarTheme = {
    color(value) {
      if (theme !== 'light' || typeof value !== 'string') return value;
      let hex = value.toLowerCase();
      if (hex === 'white') hex = '#ffffff';
      if (hex === 'black') hex = '#000000';
      if (/^#[0-9a-f]{3}$/.test(hex)) hex = '#' + [...hex.slice(1)].map(c => c+c).join('');
      if (!/^#[0-9a-f]{6}([0-9a-f]{2})?$/.test(hex)) return value;
      if (!cache.has(hex)) {
        const mapped = getComputedStyle(root).getPropertyValue('--theme-color-' + hex.slice(1,7)).trim();
        cache.set(hex, mapped ? mapped + hex.slice(7) : value);
      }
      return cache.get(hex);
    }
  };
  document.addEventListener('DOMContentLoaded', () => {
    button = document.createElement('button');
    button.type = 'button'; button.id = 'themeToggle'; button.className = 'theme-toggle';
    button.addEventListener('click', () => apply(theme === 'dark' ? 'light' : 'dark', true));
    const host = document.querySelector('body > header nav') || document.querySelector('body > header');
    (host || document.body).append(button);
    updateButton();
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.newValue, false);
  });
})();
