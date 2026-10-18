"""五个平台导航一致性、可访问状态和静态资源缓存协议。"""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest
from spad_lidar.api import app
from spad_lidar.webapi.chrome import PLATFORMS


class Navigation(HTMLParser):
    def __init__(self):
        super().__init__(); self.items = []; self.current = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'data-platform' in values:
            self.current = dict(tag=tag, attrs=values, text='')
            self.items.append(self.current)

    def handle_data(self, data):
        if self.current is not None: self.current['text'] += data

    def handle_endtag(self, tag):
        if self.current is not None and tag == self.current['tag']: self.current = None


@pytest.mark.parametrize('path,kind', [('/spad','spad'),('/system/budget','budget'),
    ('/','a'),('/debug','a'),('/system','system'),('/system/scan','columns'),
    ('/system/columns','columns'),('/system/scan/legacy','columns')])
def test_five_platforms_have_one_navigation_in_same_order(path, kind):
    response = TestClient(app).get(path)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    nav = Navigation(); nav.feed(response.text)
    assert [x['attrs']['data-platform'] for x in nav.items] == [x[0] for x in PLATFORMS]
    assert [x['text'] for x in nav.items] == [x[2] for x in PLATFORMS]
    for item, (key, href, _) in zip(nav.items, PLATFORMS):
        if key == kind:
            assert item['tag'] == 'button' and 'disabled' in item['attrs']
            assert item['attrs']['aria-current'] == 'page'
            assert item['attrs']['aria-disabled'] == 'true'
            assert 'href' not in item['attrs']
        else:
            assert item['tag'] == 'a' and item['attrs']['href'] == href
    assert response.text.count('data-theme-host') == 1
    assert '__PLATFORM_HEADER__' not in response.text
    for name in ('workspace.css','workspace.js'):
        digest = sha256((Path('web/shared') / name).read_bytes()).hexdigest()
        assert f'/static/shared/{name}?v={digest}' in response.text
    # 所有页面引用的展示资源均带内容指纹，包括本次新增公共样式。
    references = re.findall(r'(?:src|href)="(/static/[^"?#]+)([^"#]*)"', response.text)
    assert references and all(query.startswith('?v=') for _, query in references)


def test_a_secondary_views_are_preserved():
    html = TestClient(app).get('/').text
    assert 'id="modeLink"' in html and 'href="#photonBudgetPanel"' in html
    assert 'class="page-tools"' in html
