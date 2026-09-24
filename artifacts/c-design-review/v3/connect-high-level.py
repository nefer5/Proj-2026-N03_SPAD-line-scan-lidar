from pathlib import Path
p=Path('web/prototypes/c-exposure/design.js');s=p.read_text(encoding='utf8')
s=s.replace("$('parameters').oninput=e=>{if(e.target.dataset.draft)setDraft(e.target.dataset.draft,e.target.value);};", "$('parameters').oninput=e=>{if(e.target.dataset.draft)setDraft(e.target.dataset.draft,e.target.value);};markUpstreamFields();")
s=s.replace('initReviewV2();','initReviewV2();\n  initHighLevel();')
s=s.replace('review:exportReviewDraft(),strategy','review:exportReviewDraft(),high_level:exportHighLevelDraft(),strategy')
p.write_text(s,encoding='utf8')