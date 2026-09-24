from pathlib import Path
p=Path('web/prototypes/c-exposure/index.template.html')
s=p.read_text(encoding='utf8').replace('保持相同脉冲，比较时间安排','以逐发计划定义曝光策略').replace('固定比较条件','时序对比建议固定').replace('只改时间安排，性能优劣待仿真。','逐发能量也可修改；公平性需按比较目标核对。').replace('并行处理耗时 <b>待定义</b>','DSP 整列耗时 <b>待定义</b>').replace('DMA / 链路耗时 <b>待定义</b>','MIPI 搬运耗时 <b>待定义</b>')
p.write_text(s,encoding='utf8')
p=Path('web/prototypes/c-exposure/design.js');s=p.read_text(encoding='utf8').replace('draft_inputs:draft,strategy,output_format:outputFormat','draft_inputs:draft,review:exportReviewDraft(),strategy,output_format:outputFormat').replace("['双缓冲 A / B',503]","[value==='single'?'单缓冲':'双缓冲 A / B',503]")
p.write_text(s,encoding='utf8')