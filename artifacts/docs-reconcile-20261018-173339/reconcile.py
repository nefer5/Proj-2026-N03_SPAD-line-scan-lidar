"""Authorized documentation-only reconciliation with reversible originals."""
from pathlib import Path
import hashlib,json,os,posixpath,re,zipfile
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
docs=ROOT/'docs';assert docs.resolve().is_relative_to(ROOT.resolve())
paths=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted(docs.rglob('*.md'))]
original={p.relative_to(ROOT).as_posix():p.read_bytes() for p in paths}
with zipfile.ZipFile(OUT/'before.zip','x',zipfile.ZIP_DEFLATED) as z:
    for path,data in original.items():z.writestr(path,data)
archive={
 'docs/models/scanning.md':'docs/history/legacy-periodic-scanning.md',
 'docs/models/detection-performance.md':'docs/references/legacy-detection-performance.md',
 'docs/design/lidar-3d-schematic-prompt.md':'docs/references/lidar-3d-schematic-prompt.md',
 'docs/design/architecture.md':'docs/history/architecture-before-c4-20261018.md',
 'docs/guides/debug-guide.md':'docs/history/debug-guide-through-v0.2.md',
 'docs/guides/histogram-display.md':'docs/history/histogram-guide-before-20261018.md',
 'docs/design/column-accumulation-design.md':'docs/history/column-accumulation-discussion-20260925.md',
 'README.md':'docs/history/readme-before-docs-reconcile-20261018.md'}
relocated=set(list(archive)[:3]);target_links={k:archive[k] for k in relocated}
LINK=re.compile(r'(!?\[[^\]\n]*\]\()([^\n)]*)(\))')
def rebase(text,origin,destination,retarget=True):
    def change(match):
        raw=match.group(2); angle=raw.startswith('<') and '>' in raw
        url=raw[1:raw.index('>')] if angle else raw.split(' ',1)[0]
        tail=raw[raw.index('>')+1:] if angle else raw[len(url):]
        if not url or url.startswith(('#','http:','https:','mailto:','data:','file:')):return match.group(0)
        split=urlsplit(url);target=posixpath.normpath(posixpath.join(posixpath.dirname(origin),unquote(split.path)))
        if retarget:target=target_links.get(target,target)
        new=posixpath.relpath(target,posixpath.dirname(destination) or '.')
        if split.query:new+='?'+split.query
        if split.fragment:new+='#'+split.fragment
        return match.group(1)+('<'+new+'>' if angle else new)+tail+match.group(3)
    return LINK.sub(change,text)
for old,new in archive.items():
    src=ROOT/old;dst=ROOT/new
    assert src.resolve().is_relative_to(ROOT.resolve()) and dst.resolve().is_relative_to(docs.resolve())
    assert src.is_file() and not dst.exists()
    dst.parent.mkdir(parents=True,exist_ok=True)
    body=rebase(original[old].decode('utf8'),old,new)
    reference=new.startswith('docs/references/')
    status='参考资料 / 历史兼容' if reference else '历史归档'
    banner=f'> **{status}，不是当前架构或默认配置的权威源。** 归类于2026-10-18，原位置：`{old}`。文中“当前”、默认值、端口和测试数量保留记录时的含义；现行入口见[文档目录](../index.md)和[当前架构](../design/architecture.md)。\n\n'
    if 'detection-performance' in new:banner+='> 常规A界面已停用检测/Pd/PFA；此文仅保留显式历史API与旧结果的算法口径，不代表当前默认启用。\n\n'
    dst.write_text(banner+body,encoding='utf8',newline='\n')
    if old in relocated:
        relative=posixpath.relpath(new,posixpath.dirname(old))
        src.write_text(f'# 兼容文档入口\n\n正文已归类至[原资料]({relative})。本文件仅保留旧链接跳转，不再维护规范正文。\n\n当前结构、参数和实现状态请从[文档目录](../index.md)进入。\n',encoding='utf8',newline='\n')

# Resolve relocated links everywhere in the maintained Markdown collection.
for p in [ROOT/'README.md',ROOT/'AGENTS.md',*docs.rglob('*.md')]:
    relative=p.relative_to(ROOT).as_posix();text=p.read_text(encoding='utf8');updated=rebase(text,relative,relative)
    if updated!=text:p.write_text(updated,encoding='utf8',newline='\n')

record={'original_sha256':{p:hashlib.sha256(b).hexdigest() for p,b in original.items()},'archive_map':archive,'redirect_stubs':sorted(relocated),'links_rebased':True,'deletions':False,'backup':'before.zip'}
(OUT/'archive-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'original_documents':len(original),'archived_or_reclassified':len(archive),'redirect_stubs':len(relocated)},ensure_ascii=False))
