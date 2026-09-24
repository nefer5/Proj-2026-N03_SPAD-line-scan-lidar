from pathlib import Path
p=Path('web/prototypes/c-exposure/index.template.html');s=p.read_text(encoding='utf8').replace('双缓冲候选','双缓冲方案');p.write_text(s,encoding='utf8')
p=Path('web/prototypes/c-exposure/design.js');s=p.read_text(encoding='utf8').replace('候选双缓冲允许','本次选定双缓冲，允许');p.write_text(s,encoding='utf8')