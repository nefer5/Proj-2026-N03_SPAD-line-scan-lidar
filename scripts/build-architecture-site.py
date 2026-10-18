"""仅发布带时间的独立架构快照，不将整个仓库作为网站根目录。"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('artifacts/c4-architecture-20261018-172542/index.html')


class Dependencies(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        url = attrs.get('src') if tag in ('script', 'img') else (
            attrs.get('href') if tag == 'link' and attrs.get('rel') == 'stylesheet' else None)
        if url and not url.startswith('data:'):
            raise ValueError(f'网页出现未打包依赖：{tag} {url}')


def build(output):
    source = ROOT / SOURCE
    Dependencies().feed(source.read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output / 'index.html')
    (output / '.nojekyll').touch()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {
        'kind': 'historical-architecture-snapshot',
        'source': SOURCE.as_posix(),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'deployment_revision': revision,
        'scope': '2026-10-18架构分析快照；现行规范以仓库docs为准',
    }
    (output / 'publication.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'temp/github-pages/site')
    build(parser.parse_args().output)
