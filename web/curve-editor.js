/* Shared UI only: curve evaluation and integration remain in Python. */
globalThis.CurveEditors = class {
  constructor(catalog, onChange, validate) {
    this.catalog=catalog;this.onChange=onChange;this.validate=validate;this.editors={};
    for(const [kind,meta] of Object.entries(catalog.groups)) {
      const root=document.getElementById("curve-"+kind);
      const editor={kind,meta,root,spec:null,dirty:false,revision:0};
      const create=(tag,text)=>{const node=document.createElement(tag);if(text)node.textContent=text;return node;};
      const label=create("label",meta.label+" · 输入模式");
      const mode=create("select");mode.id=kind+"CurveMode";
      for(const [value,text] of Object.entries(catalog.modes)) {
        if(value==="standard" && kind!=="solar")continue;
        const option=create("option",text);option.value=value;mode.append(option);
      }
      label.append(mode);root.append(label);
      const panels={};
      for(const name of ["standard","basic","csv","manual"]) {
        const panel=create("div");panel.dataset.curvePanel=name;panels[name]=panel;root.append(panel);
      }
      panels.standard.textContent="ASTM G173-03 AM1.5G标准谱形。强度由太阳照度lux确定。";
      const shapeLabel=create("label","基础类型"),shape=create("select");shape.id=kind+"BasicShape";
      for(const [value,item] of Object.entries(catalog.shapes)) {
        const option=create("option",item.label);option.value=value;shape.append(option);
      }
      shapeLabel.append(shape);panels.basic.append(shapeLabel);
      const fields=create("div");fields.className="field-grid";
      const inputs={};
      for(const [key,item] of Object.entries(catalog.fields)) {
        const fieldLabel=create("label",item.label+" ("+(key==="amplitude"?meta.unit:item.unit)+")");
        fieldLabel.title=item.description;
        const input=create("input");input.type="number";input.step="any";input.id=kind+"Basic_"+key;
        fieldLabel.append(input);fields.append(fieldLabel);inputs[key]=input;
        input.addEventListener("input",()=>{
          onChange();
        });
      }
      panels.basic.append(fields);
      const formula=create("div");formula.className="formula";
      const domainNote=create("p","所有基础波形仅在有效波段内使用，波段外为0。");
      domainNote.className="editor-note";panels.basic.append(formula,domainNote);
      const inputFile=create("input");inputFile.type="file";inputFile.accept=".csv,text/csv";inputFile.id=kind+"CurveFile";
      const fileLabel=create("label","CSV表头：wavelength_nm,"+meta.column);fileLabel.append(inputFile);
      const filename=create("p");filename.className="editor-note";
      const filePreview=create("pre");filePreview.className="csv-preview";
      panels.csv.append(fileLabel,filename,filePreview);
      const manualLabel=create("label","每行：波长nm, "+meta.unit);
      const textarea=create("textarea");textarea.rows=7;textarea.spellcheck=false;textarea.id=kind+"CurvePoints";
      manualLabel.append(textarea);
      const apply=create("button","应用手动数据");apply.id=kind+"ApplyCurve";
      panels.manual.append(manualLabel,apply);
      const methodLabel=create("label","采样点插值"),method=create("select");method.id=kind+"CurveInterpolation";
      for(const [value,text] of [["pchip","PCHIP保形插值"],["linear","线性插值"]]) {
        const option=create("option",text);option.value=value;method.append(option);
      }
      methodLabel.append(method);root.append(methodLabel);
      const status=create("p");status.className="editor-note";status.id=kind+"CurveStatus";root.append(status);
      Object.assign(editor,{mode,shape,panels,inputs,inputFile,filename,filePreview,textarea,methodLabel,method,status,formula});
      this.editors[kind]=editor;
      mode.addEventListener("change",()=>{editor.revision++;editor.spec.mode=mode.value;this.visibility(editor);onChange();});
      shape.addEventListener("change",()=>{this.visibility(editor);onChange();});
      method.addEventListener("change",()=>{editor.spec.interpolation=method.value;onChange();});
      textarea.addEventListener("input",()=>{editor.dirty=true;editor.revision++;status.textContent="手动数据尚未应用。其他模式不使用此草稿。";});
      apply.addEventListener("click",async()=>{await this.apply(editor,textarea.value,"manual","");});
      inputFile.addEventListener("change",async()=>{
        const file=inputFile.files[0];if(!file)return;
        const revision=editor.revision;
        const text=await file.text();
        if(revision===editor.revision)await this.apply(editor,text,"csv",file.name);
      });
    }
  }
  visibility(e) {
    for(const [mode,panel] of Object.entries(e.panels))panel.classList.toggle("hidden",e.spec.mode!==mode);
    e.methodLabel.classList.toggle("hidden",!["csv","manual"].includes(e.spec.mode));
    const active=this.catalog.shapes[e.shape.value].fields;
    for(const [key,input] of Object.entries(e.inputs))input.closest("label").classList.toggle("hidden",!active.includes(key));
    e.inputs.width_nm.closest("label").firstChild.textContent=e.shape.value==="gaussian"?"半高全宽 FWHM (nm)":"矩形全宽 (nm)";
    const latex=this.catalog.formulas["basic_"+e.shape.value];
    try {katex.render(latex,e.formula,{displayMode:true,throwOnError:true});}
    catch(error){e.formula.textContent="公式渲染失败："+error.message+"\n"+latex;}
    e.status.textContent=e.spec.mode==="manual"&&e.dirty?"手动数据尚未应用":this.catalog.modes[e.spec.mode]+"模式；仅当前模式的数据参与计算。";
  }
  fill(specs) {
    for(const [kind,e] of Object.entries(this.editors)) {
      e.spec=structuredClone(specs[kind]);e.dirty=false;e.revision++;
      e.mode.value=e.spec.mode;e.shape.value=e.spec.basic.shape;e.method.value=e.spec.interpolation;
      for(const [key,input] of Object.entries(e.inputs))input.value=e.spec.basic[key];
      e.textarea.value=e.spec.manual_points.map(p=>p.wavelength_nm+","+p.value).join("\n");
      e.inputFile.value="";this.fileInfo(e);this.visibility(e);
    }
  }
  fileInfo(e) {
    e.filename.textContent=e.spec.csv_name||(e.spec.csv_points.length?"配置内CSV数据（"+e.spec.csv_points.length+"点）":"尚未导入CSV");
    e.filePreview.textContent=e.spec.csv_points.map(p=>p.wavelength_nm+","+p.value).join("\n");
  }
  values() {
    const result={};
    for(const [kind,e] of Object.entries(this.editors)) {
      if(e.spec.mode==="manual" && e.dirty)throw new Error(e.meta.label+"手动数据未应用。");
      if(["csv","manual"].includes(e.spec.mode) && !e.spec[e.spec.mode+"_points"].length)throw new Error(e.meta.label+"：请先"+(e.spec.mode==="csv"?"导入CSV文件":"输入并应用手动数据")+"。");
      const spec=structuredClone(e.spec);
      if(spec.mode==="basic") {
        spec.basic.shape=e.shape.value;
        for(const key of this.catalog.shapes[spec.basic.shape].fields) {
          const input=e.inputs[key];
          if(input.value.trim()==="" || !Number.isFinite(Number(input.value)))throw new Error(e.meta.label+"："+this.catalog.fields[key].label+"需要有效数字。");
          spec.basic[key]=Number(input.value);
        }
      }
      result[kind]=spec;
    }
    return result;
  }
  confirmBasic(specs) {
    for(const [kind,e] of Object.entries(this.editors)) {
      if(e.spec.mode==='basic' && specs[kind].mode==='basic')e.spec.basic=structuredClone(specs[kind].basic);
    }
  }
  async apply(e,text,mode,filename) {
    const revision=++e.revision;
    try {
      const points=CurveEditors.parsePoints(text,e.meta.column);
      const spec=structuredClone(e.spec);spec.mode=mode;spec[mode+"_points"]=points;
      if(mode==="csv")spec.csv_name=filename;
      const validated=await this.validate(e.kind,spec);
      if(revision!==e.revision)return;
      e.spec=validated;e.mode.value=mode;
      if(mode==="manual")e.dirty=false;
      this.fileInfo(e);this.visibility(e);e.status.textContent=points.length+"个点已应用。";
      this.onChange();
    }catch(error){if(revision===e.revision)e.status.textContent="未应用："+error.message;}
  }
  static parsePoints(text,column) {
    const lines=text.replace(/^\uFEFF/,"").trim().split(/\r?\n/).filter(line=>line.trim());
    const split=line=>line.includes(",")?line.split(",").map(x=>x.trim()):line.trim().split(/\s+/);
    if(lines[0]) {
      const header=split(lines[0]);
      if(header[0]==="wavelength_nm") {
        if(header.length!==2 || ![column,"value"].includes(header[1]))throw new Error("表头应为 wavelength_nm,"+column+"；请确认单位。");
        lines.shift();
      }
    }
    if(lines.length<2)throw new Error("至少需要两点。");
    return lines.map((line,index)=>{
      const cells=split(line);
      if(cells.length!==2 || cells.some(x=>x==="" || !Number.isFinite(Number(x))))throw new Error("第"+(index+1)+"行需要两列有效数字。");
      return {wavelength_nm:Number(cells[0]),value:Number(cells[1])};
    });
  }
};
