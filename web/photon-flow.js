/* Shared formula/logic/value renderer for live evaluation and expert snapshots. */
globalThis.renderPhotonFlow = function(container, flow, options={}) {
  const make=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
  const number=value=>typeof value==="boolean"?(value?"启用":"关闭"):typeof value==="number"?(Number.isFinite(value)?Number(value.toPrecision(8)).toString():"—"):String(value);
  const heading=make("h2",flow.title);
  const stamp=make("p",options.snapshot?"本次仿真快照 · "+options.snapshot:"实时预算 · 当前有效输入","photon-stamp");
  const bounds=make("p","背景比较波段 B："+number(flow.values.band_min_nm)+"–"+number(flow.values.band_max_nm)+" nm；回波按每脉冲、背景按每门统计。","formula-note");
  const conventions=make("details");conventions.append(make("summary","计算口径与参考面"));
  flow.conventions.forEach(text=>conventions.append(make("p",text,"formula-note")));
  const stepNode=(step)=>{
    const el=make("section",undefined,"photon-step");
    el.append(make("h3",step.title),make("p",step.logic,"photon-logic"));
    const formula=make("div",undefined,"formula");
    try{katex.render(step.latex,formula,{displayMode:true,throwOnError:true});}
    catch(error){formula.textContent="公式渲染失败："+error.message+"\n"+step.latex;}
    const note=make("p",step.symbols,"formula-note");
    const table=make("table"),head=make("thead"),header=make("tr"),body=make("tbody");
    ["中间量","当前数值","单位"].forEach(label=>header.append(make("th",label)));
    head.append(header);
    step.values.forEach(item=>{
      const row=make("tr");row.dataset.valueKey=item.key;
      row.append(make("td",item.label),make("td",number(item.value)),make("td",item.unit));body.append(row);
    });
    table.append(head,body);
    const scroll=make("div",undefined,"table-scroll");scroll.append(table);
    el.append(formula,note,scroll);return el;
  };
  const common=make("details");common.append(make("summary","共同几何、单位与比较波段"));
  flow.common.forEach(step=>common.append(stepNode(step)));
  const buttons=make("div",undefined,"toolbar photon-tabs"),panels=make("div");
  const choose=id=>{
    container.dataset.activeChain=id;
    Array.from(panels.children).forEach(panel=>panel.classList.toggle("hidden",id!=="all"&&panel.dataset.chain!==id));
    Array.from(buttons.children).forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.chain===id)));
  };
  [...flow.chains,{id:"all",title:"显示全部"}].forEach(chain=>{
    const button=make("button",chain.title);button.dataset.chain=chain.id;
    button.addEventListener("click",()=>choose(chain.id));buttons.append(button);
  });
  flow.chains.forEach(chain=>{
    const panel=make("div");panel.dataset.chain=chain.id;
    chain.steps.forEach(step=>panel.append(stepNode(step)));panels.append(panel);
  });
  const readout=make("details");readout.append(make("summary","候选数如何进入读出，为什么不等于最终记录数"));
  flow.readout.forEach(step=>readout.append(stepNode(step)));
  const recorded=make("p",options.recorded==null?"实际记录总数：运行仿真后按匹配的参数快照显示。":"实际混合记录总数："+number(options.recorded)+" 个时间戳（不按光源线性拆分）。","photon-stamp");
  container.replaceChildren(heading,stamp,bounds,conventions,common,buttons,panels,readout,recorded);
  container.dataset.inputHash=flow.input_sha256;container.dataset.stale="false";
  choose(container.dataset.activeChain||flow.chains[0].id);
};
globalThis.markPhotonFlowStale = function(container) {
  const stamp=container.querySelector(".photon-stamp");
  if(stamp)stamp.textContent="当前输入待修正；下面保留上次有效预算，尚未随本次输入更新。";
  container.dataset.stale="true";
};
