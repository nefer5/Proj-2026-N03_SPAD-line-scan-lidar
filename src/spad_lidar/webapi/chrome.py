"""五个平台共用的服务端导航；只负责展示，不改变工况或任务。"""
from hashlib import sha256
from pathlib import Path

PLATFORMS = (
    ('spad', '/spad', 'SPAD 器件研究'),
    ('budget', '/system/budget', '系统预算'),
    ('a', '/', 'A 单角通道'),
    ('system', '/system', 'B 空间光学'),
    ('columns', '/system/scan', 'C 列级扫描'),
)


def workspace_chrome(html, kind, web: Path):
    current = 'columns' if kind == 'scan' else kind
    items = []
    for key, href, label in PLATFORMS:
        if key == current:
            items.append(f'<button type="button" class="platform-link is-current" data-platform="{key}" '
                         f'disabled aria-disabled="true" aria-current="page">{label}</button>')
        else:
            items.append(f'<a class="platform-link" data-platform="{key}" href="{href}">{label}</a>')
    header = ('<header class="workspace-header"><div class="workspace-brand">'
              '<strong>SPAD <span>LiDAR</span></strong><small>仿真工作台</small></div>'
              '<nav class="platform-nav" aria-label="五个仿真子平台">' + ''.join(items) + '</nav>'
              '<div class="workspace-header-tools" data-theme-host></div></header>')
    digest = sha256((web / 'shared/workspace.css').read_bytes()).hexdigest()
    script = sha256((web / 'shared/workspace.js').read_bytes()).hexdigest()
    html = html.replace('__PLATFORM_HEADER__', header)
    html = html.replace('</head>', f'<link rel="stylesheet" href="/static/shared/workspace.css?v={digest}">'
                        f'<script defer src="/static/shared/workspace.js?v={script}"></script></head>')
    return html
