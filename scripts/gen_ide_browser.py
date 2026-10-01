#!/usr/bin/env python3
"""把仓库里的真实代码打包成一个自包含单文件 HTML「代码浏览器」。

产物：publishing/html/ide.html

    ide.html  ← 模板（内联 CSS/JS）+ 内嵌 JSON（全部源码文本）
    双击即用，无后端、无网络依赖。

浏览路径：项目列表 → 点某个项目 → 文件树（可折叠）→ 点文件 → 右侧高亮代码。

用法：
    python3 scripts/gen_ide_browser.py            # 生成
    python3 scripts/gen_ide_browser.py --stats    # 只打印统计，不写文件
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "publishing", "html", "ide.html")

# ---------------------------------------------------------------------------
# 采集规则
# ---------------------------------------------------------------------------
SKIP_DIRS = {
    ".venv", "venv", "node_modules", "__pycache__", ".git", ".hg", "target",
    ".gradle", "build", "dist", ".idea", ".mypy_cache", ".pytest_cache",
    "htmlcov", ".cache", ".ipynb_checkpoints", "site-packages", ".mvn",
}

# 只收「给人看的代码/配置/文档」，产物、二进制、训练权重一律不进
EXTS = {
    ".py", ".java", ".js", ".mjs", ".ts", ".vue", ".jsx", ".tsx", ".sh",
    ".bash", ".zsh", ".md", ".yml", ".yaml", ".json", ".toml", ".html", ".css",
    ".txt", ".xml", ".ipynb", ".properties", ".csv", ".rst", ".c", ".h",
    ".ini", ".cfg", ".lock", ".gradle", ".env",
}
EXTRA_NAMES = {"dockerfile", "makefile", "requirements.txt"}

MAX_FILE_BYTES = 160 * 1024      # 单文件上限，超过跳过（避免塞进巨型生成物）

EXT_LANG = {
    ".py": "python", ".pyw": "python", ".java": "java", ".js": "javascript",
    ".mjs": "javascript", ".ts": "javascript", ".jsx": "javascript",
    ".tsx": "javascript", ".vue": "html", ".sh": "shell", ".bash": "shell",
    ".zsh": "shell", ".c": "c", ".h": "c",
    ".md": "markdown", ".yml": "yaml", ".yaml": "yaml", ".json": "json",
    ".toml": "toml", ".ini": "toml", ".cfg": "toml",
    ".html": "html", ".css": "css", ".xml": "xml", ".properties": "plain",
    ".ipynb": "json", ".csv": "plain", ".txt": "plain", ".rst": "markdown",
    ".env": "shell",
}
EXT_TAG = {
    ".py": "Python", ".java": "Java", ".js": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".vue": "Vue", ".sh": "Shell", ".bash": "Shell",
    ".html": "HTML", ".css": "CSS", ".xml": "Maven", ".md": "文档",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".toml": "TOML",
    ".ipynb": "Jupyter", ".csv": "CSV", ".md": "文档",
}
NAME_TAG = {
    "dockerfile": "Docker", "makefile": "Make", "requirements.txt": "pip",
}

# 采集哪些目录、各自叫什么（order = 项目列表里的展示顺序）
SOURCES = [
    ("projects/01-python-ai-cli", None),
    ("projects/02-engineering-ai-assistant", None),
    ("projects/03-ai-application", None),
    ("projects/04-rag", None),
    ("projects/05-agent-mcp", None),
    ("projects/06-mini-transformer-llm", None),
    ("projects/07-open-source-llm", None),
    ("projects/08-fine-tuning", None),
    ("projects/09-evaluation-inference", None),
    ("projects/10-tiny-llm-capstone", None),
    ("python-practice/01-todo-cli", None),
    ("python-practice/02-excel-automation", None),
    ("python-practice/03-web-crawler", None),
    ("python-practice/04-fastapi-blog", None),
    ("scripts", None),
]


def is_text(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(8192)
    except OSError:
        return False
    if b"\x00" in head:
        return False
    return True


def collect_files(root: str):
    """返回可采集的文件绝对路径列表（已排序、已过滤）。"""
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            low = fn.lower()
            if low in EXTRA_NAMES:
                pass
            elif os.path.splitext(low)[1] not in EXTS:
                continue
            p = os.path.join(dp, fn)
            if os.path.getsize(p) > MAX_FILE_BYTES or not is_text(p):
                continue
            out.append(p)
    return out


def read_meta(root: str, fallback_name: str):
    """从项目自己的 README 取标题与一句描述，避免手工维护元数据腐烂。"""
    title, desc = fallback_name, ""
    rd = os.path.join(root, "README.md")
    if os.path.exists(rd):
        try:
            lines = open(rd, encoding="utf-8").read().split("\n")
        except (OSError, UnicodeDecodeError):
            lines = []
        for ln in lines:
            s = ln.strip()
            if not title and s.startswith("# "):
                title = s[2:].strip()
                break
        if not title:
            title = fallback_name
        for ln in lines:
            s = ln.strip()
            if (not s or s.startswith(("#", "|", "!", "-", "*", ">", "<", "[![",
                                      "<!--", "```", "---")) or s.isdigit()):
                continue
            s = s.replace("\\n", " ")
            if len(s) > 2:
                desc = s[:110] + ("…" if len(s) > 110 else "")
                break
    return title or fallback_name, desc


def tags_of(files):
    """从真实文件类型推出技术标签（比手写清单更不会腐烂）。"""
    tags = []
    ext_c = {}
    for f in files:
        low = f.lower()
        if os.path.basename(low) in NAME_TAG and NAME_TAG[os.path.basename(low)] not in tags:
            tags.append(NAME_TAG[os.path.basename(low)])
            continue
        tag = EXT_TAG.get(os.path.splitext(low)[1])
        if tag:
            ext_c[tag] = ext_c.get(tag, 0) + 1
    for tag, _ in sorted(ext_c.items(), key=lambda kv: -kv[1]):
        if tag not in tags:
            tags.append(tag)
    return tags[:5]


def build_project(dirpath: str):
    files = collect_files(dirpath)
    name = os.path.basename(dirpath.rstrip("/"))
    title, desc = read_meta(dirpath, name)
    payload = []
    total_lines = 0
    for p in files:
        rel = os.path.relpath(p, dirpath).replace(os.sep, "/")
        try:
            text = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        # JSON 里不能直接出现裸的控制字符
        text = "".join(ch if ch == "\n" or ch == "\t" or ord(ch) >= 32 else " " for ch in text)
        total_lines += text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        payload.append([rel, text, os.path.getsize(p)])
    return {
        "id": name,
        "name": name,
        "dir": dirpath.replace(os.sep, "/"),
        "title": title,
        "desc": desc,
        "tags": tags_of([os.path.basename(f) for f in files]),
        "files": payload,
        "lines": total_lines,
    }


def build_data():
    projects = []
    for dirpath, _ in SOURCES:
        if not os.path.isdir(os.path.join(ROOT, dirpath)):
            print(f"  跳过（目录不存在）: {dirpath}", file=sys.stderr)
            continue
        projects.append(build_project(dirpath))
    return {"projects": projects}


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 工程师之旅 · 代码浏览器</title>
<style>
:root{
  --bg:#1f1f20; --bg2:#252526; --bg3:#2d2d30; --bg4:#333336;
  --border:#3c3c40; --fg:#d8d8d8; --muted:#8b8b90; --dim:#6a6a70;
  --accent:#4da3ff; --accent2:#0e639c;
  --k:#c586c0; --s:#ce9178; --c:#6a9955; --n:#b5cea8; --fn:#dcdcaa;
  --kw:#569cd6; --ty:#4ec9b0; --num:#b5cea8; --var:#9cdcfe;
  --sel:#04395e; --sel-fg:#ffffff; --hover:#2a2d2e;
  --mono:"SF Mono",SFMono-Regular,Menlo,Monaco,"Cascadia Mono","JetBrains Mono",Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  overflow:hidden}
button{font:inherit;color:inherit;background:none;border:none;cursor:pointer}
::-webkit-scrollbar{width:11px;height:11px}
::-webkit-scrollbar-thumb{background:#4a4a4f;border-radius:6px;border:2px solid transparent;background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:#5f5f66;background-clip:content-box}
::-webkit-scrollbar-track{background:transparent}

/* ---------- 项目列表 ---------- */
#home{height:100%;overflow:auto}
.hd{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:12px;
  padding:14px 24px;background:rgba(31,31,32,.94);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border)}
.hd .logo{width:26px;height:26px;border-radius:6px;background:linear-gradient(135deg,var(--accent),#7c5cff);
  display:grid;place-items:center;color:#fff;font-weight:700;font-size:13px}
.hd h1{margin:0;font-size:15px;font-weight:600;letter-spacing:.3px}
.hd .sub{color:var(--muted);font-size:12.5px}
.hd .sp{flex:1}
.hd .hint{color:var(--dim);font-size:12px}
.grid{padding:22px 24px 40px;display:grid;gap:14px;
  grid-template-columns:repeat(auto-fill,minmax(310px,1fr))}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;
  padding:15px 16px 14px;cursor:pointer;transition:.16s;position:relative;overflow:hidden;text-align:left}
.card:hover{border-color:#5a5a60;transform:translateY(-2px);
  box-shadow:0 8px 22px rgba(0,0,0,.35)}
.card:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card .top{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.card .ic{width:26px;height:26px;flex:none;border-radius:7px;display:grid;place-items:center;
  font-size:11px;font-weight:700;background:#3a3a3f;color:#fff;letter-spacing:-.3px}
.card h3{margin:0;font-size:14.5px;font-weight:600;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card .open{color:var(--accent);font-size:12px;opacity:0;transition:.16s;flex:none}
.card:hover .open{opacity:1}
.card p{margin:0 0 11px;color:var(--muted);font-size:12.5px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:36px}
.card .meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;
  padding-top:10px;border-top:1px solid #333338}
.tag{font-size:11px;padding:2px 7px;border-radius:20px;background:#33333a;color:#b9b9c0;border:1px solid #3e3e46}
.tag.py{background:#2c4a2c22;color:#89d185;border-color:#3c6b3c}
.tag.n{color:#8b949e}
.card .num{margin-left:auto;color:var(--dim);font-size:11.5px;font-family:var(--mono)}

/* ---------- IDE ---------- */
#ide{height:100%;display:none;flex-direction:column;background:var(--bg)}
#ide.on{display:flex}
.bar{height:38px;flex:none;display:flex;align-items:center;gap:10px;padding:0 10px;
  background:var(--bg3);border-bottom:1px solid var(--border);font-size:12.5px}
.bar .crumb{display:flex;align-items:center;gap:5px;color:var(--muted);min-width:0}
.bar .crumb b{color:var(--fg);font-weight:600}
.bar .crumb .sep{opacity:.5}
.bar .sp{flex:1}
.btn{padding:5px 10px;border-radius:6px;border:1px solid var(--border);background:var(--bg4);
  font-size:12px;color:#cfcfd4}
.btn:hover{background:#3d3d43;border-color:#5a5a60}
#burger{display:none}
.body{flex:1;display:flex;min-height:0}
.side{flex:none;width:290px;min-height:0;display:flex;flex-direction:column;
  background:var(--bg2);border-right:1px solid var(--border)}
.side .sh{display:flex;align-items:center;gap:8px;padding:8px 10px;height:35px;
  font-size:11px;letter-spacing:.9px;text-transform:uppercase;color:var(--muted)}
.side .sh .sp{flex:1}
.iconbtn{width:22px;height:22px;border-radius:5px;display:grid;place-items:center;color:var(--muted);font-size:13px}
.iconbtn:hover{background:var(--bg4);color:var(--fg)}
.search{padding:0 10px 8px}
.search input{width:100%;padding:6px 9px;border-radius:6px;border:1px solid var(--border);
  background:#1b1b1c;color:var(--fg);font-size:12.5px;outline:none}
.search input:focus{border-color:var(--accent2)}
.tree{flex:1;overflow:auto;padding:0 6px 14px;font-size:13px}
.row{display:flex;align-items:center;gap:5px;padding:3px 6px;border-radius:5px;cursor:pointer;
  white-space:nowrap;user-select:none}
.row:hover{background:var(--hover)}
.row.sel{background:var(--sel);color:var(--sel-fg)}
.row .chev{width:12px;flex:none;color:var(--dim);font-size:9px;transition:transform .12s;text-align:center}
.row.f .chev{visibility:hidden}
.row.open>.chev{transform:rotate(90deg)}
.row .nm{overflow:hidden;text-overflow:ellipsis}
.row .cnt{margin-left:auto;font-size:10.5px;color:var(--dim);font-family:var(--mono)}
.row.sel .cnt{color:#9dc6ee}
.row .ic{width:15px;flex:none;text-align:center;font-size:10px;font-weight:700;letter-spacing:-.5px}
.row .ic.dir{color:#c09553;font-size:13px}
.i-py{color:#4b8bbe}.i-java{color:#e76f51}.i-js{color:#e5c07b}.i-md{color:#8ab4f8}
.i-json{color:#cbcb41}.i-yaml{color:#d1a04a}.i-sh{color:#89d185}.i-html{color:#e8825a}
.i-css{color:#8ab4f8}.i-txt{color:#9aa0a6}.i-csv{color:#9aa0a6}.i-toml{color:#a5a5a5}
.kids{display:none}
.kids.show{display:block}

.ed{flex:1;min-width:0;display:flex;flex-direction:column;background:var(--bg)}
.tabs{flex:none;display:flex;height:35px;overflow-x:auto;background:var(--bg2);
  border-bottom:1px solid var(--border);scrollbar-width:none}
.tabs::-webkit-scrollbar{height:0}
.tab{display:flex;align-items:center;gap:7px;padding:0 10px 0 12px;font-size:12.5px;color:#a8a8ae;
  border-right:1px solid var(--border);cursor:pointer;white-space:nowrap;flex:none;max-width:230px}
.tab:hover{background:#2f2f31;color:var(--fg)}
.tab.act{background:var(--bg);color:#fff;border-top:1px solid var(--accent);padding-top:0}
.tab .ic{font-weight:700;font-size:10px;letter-spacing:-.5px;opacity:.9}
.tab .x{opacity:0;border-radius:4px;padding:0 3px}
.tab:hover .x{opacity:.7}
.tab .x:hover{opacity:1;background:#48484e}
.code{flex:1;overflow:auto;padding:8px 0 40px;font-family:var(--mono);font-size:12.8px;line-height:1.62}
.cl{display:flex;min-width:min-content}
.cl:hover{background:#ffffff08}
.cl .ln{flex:none;width:52px;padding-right:14px;text-align:right;color:#5a5a60;
  user-select:none;position:sticky;left:0;background:var(--bg)}
.cl:hover .ln{background:#1c1c1d}
.cl .ct{white-space:pre-wrap;word-break:break-word;padding-right:20px;flex:1}
.c-empty{flex:1;display:grid;place-items:center;color:var(--dim);font-size:13.5px;text-align:center;line-height:2}
.c-empty .big{font-size:34px;opacity:.35;margin-bottom:6px}
.t-kw{color:var(--kw)}.t-str{color:var(--s)}.t-com{color:var(--c);font-style:italic}
.t-num{color:var(--num)}.t-fn{color:var(--fn)}.t-type{color:var(--ty)}.t-var{color:var(--var)}
.t-dec{color:var(--k)}.t-op{color:#d4d4d4}.t-tag{color:#4ec9b0}.t-attr{color:#9cdcfe}
.t-key{color:#9cdcfe}.t-bool{color:#569cd6}.t-plain{color:var(--fg)}
.t-h1{color:#569cd6;font-size:1.28em;font-weight:700;display:block;padding:.28em 0 .18em}
.t-h2{color:#569cd6;font-size:1.16em;font-weight:700;display:block;padding:.24em 0 .14em}
.t-h3{color:#4fc1ff;font-size:1.06em;font-weight:700;display:block;padding:.2em 0 .1em}
.md .cl .ct p{margin:0}
.t-mdcode{color:#b5cea8;background:#1b1b1c;border-radius:4px;padding:0 5px}
.t-link{color:#4ec9b0;text-decoration:underline}
.t-quote{color:#a5a5a5;font-style:italic}
.t-head{color:#569cd6;font-weight:700}
.stbar{flex:none;height:24px;display:flex;align-items:center;gap:14px;padding:0 12px;font-size:11.5px;
  background:var(--accent2);color:#fff}
.stbar .sp{flex:1}
.stbar span{opacity:.92}

@media (max-width:860px){
  .grid{grid-template-columns:1fr;padding:16px 14px 34px}
  .hd{padding:12px 14px}
  #burger{display:grid}
  .side{position:fixed;top:38px;bottom:24px;left:0;z-index:20;transform:translateX(-100%);
    transition:transform .18s;box-shadow:6px 0 26px rgba(0,0,0,.5);width:84vw;max-width:300px}
  .side.on{transform:none}
  .side .shd{position:fixed;inset:0;background:#000000aa;z-index:19;display:none}
  .side .shd.on{display:block}
  .bar .hint{display:none}
}
</style>
</head>
<body>

<!-- ================= 项目列表 ================= -->
<div id="home">
  <div class="hd">
    <div class="logo">AI</div>
    <div>
      <h1>AI 工程师之旅 · 代码浏览器</h1>
      <div class="sub">__NPROJ__ 个项目 · __NFILE__ 个文件 · __NLINE__ 行真实代码</div>
    </div>
    <div class="sp"></div>
    <div class="hint">本页把所有源码内嵌进单个 HTML，无后端、可离线双击打开</div>
  </div>
  <div class="grid" id="grid"></div>
</div>

<!-- ================= IDE ================= -->
<div id="ide">
  <div class="bar">
    <button class="iconbtn" id="burger" title="文件树 (Ctrl+B)">☰</button>
    <button class="btn" id="back">‹ 返回项目列表</button>
    <div class="crumb" id="crumb"></div>
    <div class="sp"></div>
    <button class="iconbtn" id="foldAll" title="折叠全部">⤡</button>
    <button class="iconbtn" id="expandAll" title="展开全部">⤢</button>
  </div>
  <div class="body">
    <aside class="side" id="side">
      <div class="sh">
        <span>资源管理器</span><div class="sp"></div>
        <button class="iconbtn" id="closeSide" title="关闭">✕</button>
      </div>
      <div class="search"><input id="fil" placeholder="筛选文件…" autocomplete="off"></div>
      <div class="tree" id="tree"></div>
    </aside>
    <div class="shd" id="shd"></div>
    <main class="ed">
      <div class="tabs" id="tabs"></div>
      <div class="code" id="code"></div>
      <div class="c-empty" id="cempty">
        <div>
          <div class="big">⌨</div>
          从左侧文件树选一个文件<br>或直接点上方已打开的标签
        </div>
      </div>
    </main>
  </div>
  <div class="stbar">
    <span id="st-path">—</span><div class="sp"></div>
    <span id="st-lang">—</span><span id="st-lines">—</span><span id="st-size">—</span>
  </div>
</div>

<script id="ide-data" type="application/json">__DATA__</script>
<script>
(function(){
"use strict";
var DATA = JSON.parse(document.getElementById('ide-data').textContent);
var PROJ = DATA.projects;

/* ------------------------------------------------------------------ 词法 */
var R = function(src){ return new RegExp(src, 'y'); };
var KW = {
python:"False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case",
java:"abstract assert break case catch class const continue default do else enum extends final finally for goto if implements import instanceof interface native new package private protected public return static strictfp super switch synchronized this throw throws transient try var volatile while record sealed permits yield",
javascript:"async await break case catch class const continue debugger default delete do else export extends finally for function get if import in instanceof let new of return set static super switch this throw try typeof var void while with yield",
shell:"if then else elif fi for while until do done case esac function local return export readonly declare source alias in select time coproc"
};
/* 规则顺序即优先级：注释 → 字符串 → 关键字 → 内置 → 数字 → 标点 → 兜底 */
function rules(lang){
  if(rules._c[lang]) return rules._c[lang];
  var kw = KW[lang] ? KW[lang].split(" ") : [];
  var out = [];
  var push = function(t, src){ out.push({t:t, re:R(src)}); };
  if(lang==="python"){
    push("com", "#[^\\n]*");
    push("str", "[rbfuRBFU]{0,2}(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|[rbfuRBFU]{0,2}\"(?:\\\\.|[^\\\\\\n])*\"|[rbfuRBFU]{0,2}'(?:\\\\.|[^\\\\\\n])*')");
    push("dec", "@[A-Za-z_]\\w*");
    push("kw", "\\b(?:"+kw.join("|")+")\\b");
    push("type","\\b(?:self|cls)\\b");
    push("num","\\b\\d[\\d_]*\\.?[\\d_]*(?:[eE][+-]?\\d+)?[jf]?\\b");
    push("op","[^\\w\\s]+"); push("plain","[\\w]+");
  } else if(lang==="java"){
    push("com","//[^\\n]*|/\\*[\\s\\S]*?\\*/");
    push("str","\"(?:\\\\.|[^\\\\\\n])*\"|'(?:\\\\.|[^\\\\'])'");
    push("kw","\\b(?:"+kw.join("|")+")\\b");
    push("type","\\b[A-Z][A-Za-z0-9_]*\\b|\\b(?:String|Integer|Double|Boolean|List|Map|Set|Optional|System|Math|Object|Long|Float|Character|ArrayList|HashMap)\\b");
    push("num","\\b\\d[\\d_]*\\.?[\\d_]*(?:[eE][+-]?\\d+)?[fFdDlL]?\\b");
    push("op","[^\\w\\s]+"); push("plain","[\\w]+");
  } else if(lang==="javascript"){
    push("com","//[^\\n]*|/\\*[\\s\\S]*?\\*/");
    push("str","`(?:\\\\.|[^\\\\`])*`|'(?:\\\\.|[^\\\\\\n])*'|\"(?:\\\\.|[^\\\\\\n])*\"");
    push("kw","\\b(?:"+kw.join("|")+")\\b");
    push("type","\\b[A-Z][A-Za-z0-9_$]*\\b|\\b(?:console|JSON|Math|Date|Promise|Object|Array|String|Number|document|window)\\b");
    push("num","\\b\\d[\\d_]*\\.?[\\d_]*(?:[eE][+-]?\\d+)?[nfl]?\\b");
    push("op","[^\\w\\s]+"); push("plain","[\\w]+");
  } else if(lang==="shell"){
    push("com","#[^\\n]*");
    push("str","'(?:[^'\\n])*'|\"(?:\\\\.|[^\\\\\"])*\"");
    push("var","\\$\\{[^}]*\\}|\\$[A-Za-z_]\\w*|\\$[@#?$*!0-9]");
    push("kw","\\b(?:"+kw.join("|")+")\\b");
    push("num","\\b\\d+\\b");
    push("op","[^\\w\\s]+"); push("plain","[\\w-]+");
  } else if(lang==="json"){
    push("key","\"(?:\\\\.|[^\\\\\"])*\"(?=\\s*:)");
    push("str","\"(?:\\\\.|[^\\\\\"])*\"");
    push("bool","\\b(?:true|false|null)\\b");
    push("num","-?\\b\\d+\\.?\\d*(?:[eE][+-]?\\d+)?\\b");
    push("op","[{}\\[\\],:]"); push("plain","[^\\w\\s]+");
  } else if(lang==="yaml"){
    push("com","#[^\\n]*");
    push("key","[A-Za-z_][\\w.-]*(?=\\s*:)");
    push("str","'(?:[^'\\n])*'|\"(?:\\\\.|[^\\\\\"])*\"");
    push("bool","\\b(?:true|false|null|yes|no|on|off)\\b");
    push("num","\\b\\d+\\.?\\d*\\b");
    push("op","[-:>{}\\[\\],|&*!#@]"); push("plain","[\\w.]+");
  } else if(lang==="toml"){
    push("com","#[^\\n]*");
    push("key","[A-Za-z_][\\w.-]*(?=\\s*=)");
    push("str","\"(?:\\\\.|[^\\\\\"])*\"|'(?:[^'\\n])*'");
    push("bool","\\b(?:true|false)\\b");
    push("num","\\b\\d+\\.?\\d*\\b");
    push("op","[=\\[\\].,:{}]"); push("plain","[\\w.-]+");
  } else if(lang==="html"||lang==="xml"){
    push("com","<!--[\\s\\S]*?-->");
    push("tag","</?[A-Za-z_][\\w:.-]*|/?>");
    push("str","\"(?:\\\\.|[^\\\"])*\"|'(?:[^'\\n])*'");
    push("attr","[A-Za-z_:@#][\\w:.-]*(?=\\s*=)");
    push("num","\\b\\d+\\b"); push("op","=/<>"); push("plain","[\\w.-]+");
  } else if(lang==="css"){
    push("com","/\\*[\\s\\S]*?\\*/");
    push("str","\"(?:[^\\n\"])*\"|'(?:[^\\n'])*'");
    push("kw","[-A-Za-z]+(?=\\s*:)");
    push("type","[.#][\\w-]+|&[\\w-]*");
    push("num","-?\\b\\d*\\.?\\d+(?:px|em|rem|%|vh|vw|s|ms|deg|fr)?\\b");
    push("op","[{}:;,()>]"); push("plain","[\\w-]+");
  } else {
    push("com","//[^\\n]*|#[^\\n]*");
    push("str","\"(?:\\\\.|[^\\\\\\n])*\"|'(?:\\\\.|[^\\\\\\n])*'");
    push("num","\\b\\d+\\.?\\d*\\b");
    push("op","[^\\w\\s]+"); push("plain","[\\w]+");
  }
  out.push({t:null, re:R("[\\s\\S]")});
  rules._c[lang] = out;
  return out;
}
rules._c = {};

function esc(s){ return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

/** 整块 tokenize（能跨行识别三引号字符串 / 块注释），再按行拆分输出 */
function hl(src, lang){
  if(lang==="markdown"||lang==="plain"||lang==="c"){
    return hlSimple(src, lang);
  }
  var rs = rules(lang), i = 0, n = src.length, toks = [];
  while(i < n){
    var hit = null;
    for(var k=0;k<rs.length;k++){
      rs[k].re.lastIndex = i;
      var m = rs[k].re.exec(src);
      if(m && m[0]){ hit = {t:rs[k].t, v:m[0]}; break; }
    }
    if(!hit){ hit = {t:null, v:src[i]}; i += 1; }
    else { i += hit.v.length; }
    toks.push(hit);
  }
  var lines = [[]];
  for(var j=0;j<toks.length;j++){
    var tk = toks[j], parts = tk.v.split("\n");
    for(var p=0;p<parts.length;p++){
      if(p) lines.push([]);
      if(!parts[p]) continue;
      var html = esc(parts[p]);
      lines[lines.length-1].push(tk.t ? '<span class="t-'+tk.t+'">'+html+'</span>' : html);
    }
  }
  return lines;
}

/** markdown：按行处理（标题/引用/围栏/链接/行内码） */
function hlSimple(src, lang){
  var lines = src.split("\n"), out = [[]];
  var fence = false;
  for(var i=0;i<lines.length;i++){
    var L = lines[i], cls = null, rest = null;
    if(/^\s*```/.test(L)){
      out[out.length-1].push(esc(L)); fence = !fence; out.push([]); continue;
    }
    if(fence){ out[out.length-1].push('<span class="t-mdcode">'+esc(L)+'</span>'); continue; }
    var m = L.match(/^\s{0,3}(#{1,6})\s+(.*)$/);
    if(m){ cls = "t-h"+Math.min(m[1].length,3); rest = m[2]; }
    else if(/^\s{0,3}>/.test(L)){ cls="t-quote"; rest=L.replace(/^\s{0,3}>\s?/, ""); }
    var body;
    if(rest!==null){
      body = esc(rest)
        .replace(/(`[^`]+`)/g, '<span class="t-mdcode">$1</span>')
        .replace(/(\[[^\]]+\]\([^)]+\))/g, '<span class="t-link">$1</span>')
        .replace(/(\*\*[^*]+\*\*)/g, '<b>$1</b>');
    } else body = esc(L);
    if(cls) out[out.length-1].push('<span class="'+cls+'">'+body+'</span>');
    else out[out.length-1].push(body);
    out.push([]);
  }
  if(out.length && !out[out.length-1].length) out.pop();
  return out;
}

/* ------------------------------------------------------------------ 图标 */
function extOf(n){
  var i = n.lastIndexOf(".");
  return i<0 ? "" : n.slice(i+1).toLowerCase();
}
var EXTCLS = {py:"i-py",java:"i-java",js:"i-js",mjs:"i-js",ts:"i-js",md:"i-md",
  json:"i-json",yml:"i-yaml",yaml:"i-yaml",sh:"i-sh",bash:"i-sh",html:"i-html",
  css:"i-html",xml:"i-html",toml:"i-toml",csv:"i-csv",txt:"i-txt",env:"i-txt"};

/* ------------------------------------------------------------------ 状态 */
var P = null, TREE = null, TABS = [], ACT = -1, FILTER = "";
var collapsed = Object.create(null);

function buildTree(project){
  var root = {name:project.name, id:"", path:"", type:"dir", children:[], nfile:0, ntree:0};
  for(var i=0;i<project.files.length;i++){
    var f = project.files[i], seg = f[0].split("/"), node = root;
    for(var s=0;s<seg.length;s++){
      var last = s===seg.length-1;
      var nm = seg[s], id = node.id ? node.id+"/"+nm : nm;
      var exist = null;
      for(var c=0;c<node.children.length;c++) if(node.children[c].name===nm){ exist=node.children[c]; break; }
      if(!exist){
        exist = last
          ? {name:nm, id:id, path:f[0], type:"file", content:f[1], size:f[2], lang:langOf(nm)}
          : {name:nm, id:id, path:f[0], type:"dir", children:[], nfile:0, ntree:0};
        node.children.push(exist);
      }
      node = exist;
    }
    bump(root, 1);
  }
  sortKids(root);
  return root;
}
function bump(n, d){ n.nfile += d; if(n.type==="dir") n.ntree += d; }
function sortKids(n){
  if(n.type!=="dir") return;              // 文件节点没有 children
  n.children.sort(function(a,b){
    if(a.type!==b.type) return a.type==="dir" ? -1 : 1;
    return a.name.localeCompare(b.name, "zh");
  });
  n.children.forEach(sortKids);
}
function langOf(name){
  var e = extOf(name);
  var m = {py:"python",java:"java",js:"javascript",mjs:"javascript",mts:"javascript",
    c:"c",h:"c",md:"markdown",yml:"yaml",yaml:"yaml",json:"json",toml:"toml",
    sh:"shell",bash:"shell",html:"html",css:"css",xml:"html",csv:"plain",txt:"plain"};
  return m[e] || "plain";
}

/* ------------------------------------------------------------------ 树渲染 */
function renderTree(){
  var t = document.getElementById("tree");
  t.innerHTML = "";
  if(FILTER){
    var hits = findHits(TREE, FILTER);
    if(!hits.length){
      t.innerHTML = '<div style="padding:14px 10px;color:#6a6a70;font-size:12.5px">没有匹配 “'+esc(FILTER)+'” 的文件</div>';
      return;
    }
    hits.sort(function(a,b){ return a.path<b.path?-1:1; });
    hits.forEach(function(n){
      var row = document.createElement("div");
      row.className = "row f" + (n.path===ACT_PATH() ? " sel" : "");
      row.innerHTML = '<span class="chev"></span>'
        + '<span class="ic '+(EXTCLS[extOf(n.name)]||"i-txt")+'">'+esc(extOf(n.name)||".")+'</span>'
        + '<span class="nm">'+esc(n.name)+'</span>'
        + '<span class="cnt" style="margin-left:0">'+esc(dirName(n.path))+' / '+esc(n.name)+'</span>';
      (function(nd){ row.onclick = function(){ openFile(nd); }; })(n);
      t.appendChild(row);
    });
    return;
  }
  t.appendChild(nodeEl(TREE, 0));
}
function ACT_PATH(){ return ACT>=0 ? TABS[ACT].path : null; }
function dirName(p){ var i=p.lastIndexOf("/"); return i<0?"":p.slice(0,i); }
function findHits(root, q){
  var out = [], q2 = q.toLowerCase();
  // 筛选是「搜索」语义：不管当前折叠状态，全树扫一遍
  (function walk(n){
    if(n.type==="file"){ if(n.name.toLowerCase().indexOf(q2)>=0) out.push(n); return; }
    n.children.forEach(walk);
  })(root);
  return out;
}
function nodeEl(node, depth){
  var box = document.createElement("div");
  if(node.type==="dir"){
    var open = !collapsed[node.id];
    var row = document.createElement("div");
    row.className = "row" + (open?" open":"");
    row.innerHTML = '<span class="chev">▶</span>'
      + '<span class="ic dir">▸</span>'
      + '<span class="nm">'+esc(node.name)+'</span>'
      + '<span class="cnt">'+node.nfile+'</span>';
    var kids = document.createElement("div");
    kids.className = "kids" + (open?" show":"");
    row.onclick = function(){
      collapsed[node.id] = !collapsed[node.id];   // 点行即折叠，与 VSCode 一致
      renderTree();
    };
    box.appendChild(row); box.appendChild(kids);
    node.children.forEach(function(c){ kids.appendChild(nodeEl(c, depth+1)); });
  } else {
    var r2 = document.createElement("div");
    r2.className = "row f" + (node.path===ACT_PATH() ? " sel" : "");
    r2.innerHTML = '<span class="chev"></span>'
      + '<span class="ic '+(EXTCLS[extOf(node.name)]||"i-txt")+'">'+esc(extOf(node.name)||"-")+'</span>'
      + '<span class="nm">'+esc(node.name)+'</span>';
    r2.title = node.path;
    r2.onclick = function(){ openFile(node); };
    box.appendChild(r2);
  }
  return box;
}
function expandTo(path){
  // 只把「祖先目录」置为展开，不动其他节点，避免打开文件后整棵树被打开
  var seg = path.split("/"), node = TREE;
  collapsed[node.id] = false;
  for(var i=0;i<seg.length-1;i++){
    var nx = null;
    for(var c=0;c<node.children.length;c++){
      if(node.children[c].name===seg[i]){ nx = node.children[c]; break; }
    }
    if(!nx) return;
    collapsed[nx.id] = false;
    node = nx;
  }
}
/** 初始折叠：只看一层，深层目录收起（否则大项目一进来就是几百行） */
function seedCollapse(root){
  (function walk(n, depth){
    if(n.type!=="dir") return;
    if(depth>=1) collapsed[n.id] = true;
    n.children.forEach(function(c){ walk(c, depth+1); });
  })(root, 0);
}
function setFoldAll(v){
  collapsed = Object.create(null);
  TREE.children.forEach(function(k){ collapsed[k.id] = v; });
}

/* ------------------------------------------------------------------ 编辑器 */
function openFile(node){
  var idx = -1;
  for(var i=0;i<TABS.length;i++) if(TABS[i].path===node.path){ idx=i; break; }
  if(idx<0){ TABS.push(node); idx = TABS.length-1; }
  ACT = idx;
  expandTo(node.path);
  renderTabs(); renderCode(); renderTree(); renderCrumb(); renderStatus();
  document.getElementById("cempty").style.display = "none";
}
function closeTab(i){
  TABS.splice(i,1);
  if(ACT>=TABS.length) ACT = TABS.length-1;
  if(ACT<0){
    ACT = -1;
    document.getElementById("cempty").style.display = "grid";
    document.getElementById("code").innerHTML = "";
  }
  renderTabs(); renderCode(); renderTree(); renderCrumb(); renderStatus();
}
function renderTabs(){
  var box = document.getElementById("tabs"); box.innerHTML = "";
  TABS.forEach(function(n, i){
    var el = document.createElement("div");
    el.className = "tab" + (i===ACT?" act":"");
    el.innerHTML = '<span class="ic '+(EXTCLS[extOf(n.name)]||"i-txt")+'">'+esc(extOf(n.name)||"-")+'</span>'
      + '<span>'+esc(n.name)+'</span><span class="x">✕</span>';
    el.onclick = function(){ ACT=i; renderTabs(); renderCode(); renderTree(); renderCrumb(); renderStatus(); };
    el.querySelector(".x").onclick = function(ev){ ev.stopPropagation(); closeTab(i); };
    box.appendChild(el);
  });
  box.scrollLeft = 99999;
}
function renderCode(){
  var code = document.getElementById("code");
  if(ACT<0){ code.innerHTML = ""; return; }
  var n = TABS[ACT];
  var lines = hl(n.content, n.lang);
  var h = "";
  for(var i=0;i<lines.length;i++){
    h += '<div class="cl"><span class="ln">'+(i+1)+'</span><span class="ct">'+lines[i].join("")+'</span></div>';
  }
  code.innerHTML = h;
  code.scrollTop = 0; code.scrollLeft = 0;
}
function renderCrumb(){
  var el = document.getElementById("crumb");
  if(ACT<0){ el.innerHTML = "<b>"+esc(P.title)+"</b>"; return; }
  var p = TABS[ACT].path, seg = p.split("/"), parts = [];
  parts.push('<span>'+esc(P.name)+'</span>');
  for(var i=0;i<seg.length-1;i++) parts.push('<span class="sep">›</span><span>'+esc(seg[i])+'</span>');
  parts.push('<span class="sep">›</span><b>'+esc(seg[seg.length-1])+'</b>');
  el.innerHTML = parts.join("");
}
function fmtSize(b){
  if(b<1024) return b+" B";
  if(b<1048576) return (b/1024).toFixed(1)+" KB";
  return (b/1048576).toFixed(2)+" MB";
}
function renderStatus(){
  document.getElementById("st-path").textContent = P.name+" · "+(ACT>=0?TABS[ACT].path:"(未打开文件)");
  if(ACT<0){ document.getElementById("st-lang").textContent="—";
    document.getElementById("st-lines").textContent="—";
    document.getElementById("st-size").textContent="—"; return; }
  var n = TABS[ACT];
  document.getElementById("st-lang").textContent = n.lang;
  document.getElementById("st-lines").textContent = n.content.split("\n").length+" 行";
  document.getElementById("st-size").textContent = fmtSize(n.size);
}

/* ------------------------------------------------------------------ 首页 */
function renderHome(){
  var g = document.getElementById("grid");
  g.innerHTML = "";
  PROJ.forEach(function(p, i){
    var card = document.createElement("button");
    card.className = "card";
    card.innerHTML =
      '<div class="top"><span class="ic">'+esc(p.name.slice(0,2).toUpperCase())+'</span>'
      + '<h3>'+esc(p.title)+'</h3><span class="open">打开 ›</span></div>'
      + '<p>'+esc(p.desc||"（无描述）")+'</p>'
      + '<div class="meta">'+p.tags.map(function(t){
          return '<span class="tag">'+esc(t)+'</span>';
        }).join("")
        + '<span class="num">'+p.files.length+' 文件 · '+p.lines+' 行</span></div>';
    card.onclick = function(){ openProject(i); };
    g.appendChild(card);
  });
}

/* ------------------------------------------------------------------ 导航 */
function openProject(i){
  P = PROJ[i];
  TABS = []; ACT = -1; FILTER = "";
  document.getElementById("fil").value = "";
  TREE = buildTree(P);
  collapsed = Object.create(null);
  seedCollapse(TREE);
  document.getElementById("home").style.display = "none";
  document.getElementById("ide").classList.add("on");
  document.getElementById("cempty").style.display = "grid";
  renderTabs(); renderCode(); renderTree(); renderCrumb(); renderStatus();
}
function goHome(){
  document.getElementById("ide").classList.remove("on");
  document.getElementById("home").style.display = "";
  renderHome();
  document.getElementById("shd").classList.remove("on");
  document.getElementById("side").classList.remove("on");
}

/* ------------------------------------------------------------------ 绑定 */
document.getElementById("back").onclick = goHome;
document.getElementById("foldAll").onclick = function(){ setFoldAll(true); renderTree(); };
document.getElementById("expandAll").onclick = function(){ setFoldAll(false); renderTree(); };
document.getElementById("closeSide").onclick = toggleSide(false);
document.getElementById("shd").onclick = toggleSide(false);
var burger = document.getElementById("burger");
burger.onclick = toggleSide(true);
function toggleSide(force){
  return function(){
    var el = document.getElementById("side");
    var on = typeof force==="boolean" ? force : !el.classList.contains("on");
    el.classList.toggle("on", on);
    document.getElementById("shd").classList.toggle("on", on);
  };
}
document.getElementById("fil").addEventListener("input", function(e){
  FILTER = e.target.value.trim(); renderTree();
});
document.addEventListener("keydown", function(e){
  if((e.ctrlKey||e.metaKey) && (e.key==="b"||e.key==="B")){ e.preventDefault(); toggleSide(); }
  if(e.key==="Escape" && document.getElementById("ide").classList.contains("on") && ACT<0) goHome();
});
window.addEventListener("resize", function(){
  if(window.innerWidth>860){
    document.getElementById("side").classList.remove("on");
    document.getElementById("shd").classList.remove("on");
  }
});

renderHome();
})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="只统计不写文件")
    args = ap.parse_args()

    data = build_data()
    total_files = sum(len(p["files"]) for p in data["projects"])
    total_lines = sum(p["lines"] for p in data["projects"])
    mb = sum(len(p["files"][i][1]) for p in data["projects"] for i in range(len(p["files"])))
    print(f"项目: {len(data['projects'])}  文件: {total_files}  行数: {total_lines}  文本量: {mb/1048576:.2f} MB")
    for p in data["projects"]:
        print(f"  {p['dir']:44s} {len(p['files']):4d} 文件 {p['lines']:6d} 行")
    if args.stats:
        return

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # 防止 JSON 里出现 </script> 提前闭合脚本块
    payload = payload.replace("</", "<\\/")

    html = TEMPLATE.replace("__DATA__", payload)
    html = (html.replace("__NPROJ__", str(len(data["projects"])))
                .replace("__NFILE__", str(total_files))
                .replace("__NLINE__", f"{total_lines:,}"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成: {OUT}  ({os.path.getsize(OUT)/1048576:.2f} MB)")


if __name__ == "__main__":
    main()
