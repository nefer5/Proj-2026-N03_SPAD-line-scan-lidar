// Read-only QA using the KaTeX engine bundled with a local VS Code install.
// Usage: node scripts/check-math.cjs "<VS Code>/.../markdown-math/notebook-out/katex.js"
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const bundlePath = process.argv[2];
if (!bundlePath) throw new Error("Pass the local VS Code katex.js bundle path.");
const context = vm.createContext({});
const bundle = fs.readFileSync(bundlePath, "utf8");
// Fail visibly if another installed version uses a different bundle layout.
if (!bundle.includes("var rn=tn") || !bundle.includes("export{xs as activate};"))
  throw new Error("Unsupported VS Code bundle layout; update this QA adapter.");
vm.runInContext(bundle.replace("export{xs as activate};", "globalThis.qaKatex = rn();")
  .replaceAll("import.meta.url", JSON.stringify(bundlePath)), context);
const docs = path.resolve(__dirname, "../docs");
let count = 0;
for (const name of fs.readdirSync(docs).filter(name => name.endsWith(".md"))) {
  let text = fs.readFileSync(path.join(docs, name), "utf8");
  text = text.replace(/~~~[\s\S]*?~~~/g, "").replace(/\x60{3}[\s\S]*?\x60{3}/g, "").replace(/\x60[^\x60]*\x60/g, "");
  for (const match of text.matchAll(/\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$/g)) {
    context.qaKatex.renderToString(match[1] ?? match[2], {throwOnError:true, displayMode:match[1] !== undefined});
    count++;
  }
}
if (count === 0) throw new Error("No equations found.");
console.log(count + " equations parsed by VS Code bundled KaTeX.");
