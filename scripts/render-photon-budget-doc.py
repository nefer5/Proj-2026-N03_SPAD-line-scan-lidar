"""Print photon-budget Markdown from the shared UI definitions; --check verifies sync."""
import argparse
from pathlib import Path
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]


def render():
    load=lambda name:yaml.safe_load((ROOT/"config"/name).read_text(encoding="utf-8"))
    definition=load("photon-flow.yaml")
    formulas=load("formulas.yaml")
    notes=load("formula-notes.yaml")
    tick=chr(96)
    lines=["# "+definition["title"],"",
           "> 本文由 scripts/render-photon-budget-doc.py 生成。公式、变量说明与步骤分别来自 config/formulas.yaml、config/formula-notes.yaml 和 config/photon-flow.yaml；评估页和专家页使用同一数据源。","",
           definition["intro"],"",
           "网页在每一步显示当前数值和单位；本页定义公式与计算逻辑，不固化随用户工况变化的结果。","","## 参考面与统计口径",""]
    lines.extend("- "+text for text in definition["conventions"])
    lines.append("")
    def steps(items):
        for step in items:
            fid=step["formula_id"]
            lines.extend(["### "+step["title"],"",step["logic"],"","$$",formulas[fid],"$$","",
                          "**符号与单位：** "+notes[fid],"",
                          "| 中间量 | 单位 | Python结果字段 |","|---|---|---|"])
            for v in step["values"]:
                lines.append("| "+v["label"]+" | "+v["unit"]+" | "+tick+v["key"]+tick+" |")
            lines.append("")
    lines.extend(["## 共同几何与单位",""]);steps(definition["common"])
    for chain in definition["chains"]:
        lines.extend(["## "+chain["title"],""]);steps(chain["steps"])
    lines.extend(["## 候选输入到实际读出",""]);steps(definition["readout"])
    lines.extend(["## 对照代码与模型边界","",
                  "- simulator.py / photon_budget：分阶段回波能量、入瞳光子、探测面光子与各来源候选数。",
                  "- spectra.py / spectral_components：太阳lux归一化、反射、其他光倍率、同波段分层光谱积分。",
                  "- photon_flow.py：将真实中间量绑定到共享步骤定义；不从LaTeX执行计算。",
                  "- readout.py：候选事件经过死时间、OR/符合/TDC限制，得到混合直方图。",
                  "- 太阳反射假定灰朗伯面；其他光输入已经是接收方向辐亮度。光学入瞳、通道视场、PDE/FF的适用范围见同目录模型说明。",
                  "- 回波门内份额G是理想IRF参考。事件模式中的门控与电子时间抖动可能带来不同的边缘损失，以实际读出审计为准。",
                  "- 背景原始计数使用B波段作分层对照；波段外的光子没有被这张预算表计入，不应把它解释为硬件已经拒收。",
                  "",
                  "运行 "+tick+"python scripts/render-photon-budget-doc.py --check"+tick+" 可检测此文档是否与共享定义一致。更新定义后运行不带参数的脚本输出新版Markdown，并更新本文件。",""])
    return "\n".join(lines)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    text=render()
    if args.check:
        target=ROOT/"docs"/"photon-budget.md"
        if not target.exists() or target.read_text(encoding="utf-8")!=text:
            raise SystemExit("docs/photon-budget.md is out of sync with shared definitions")
        print("Photon-budget document matches shared definitions.")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text,end="")
