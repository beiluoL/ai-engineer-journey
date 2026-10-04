#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描 ai-engineer-journey 仓库里的全部 Markdown 文档，生成文档式总览页
publishing/html/index.html —— 一份可以从头读到尾的长文档：

  * **有序章节**：全部文档按「主题 → 子分组 → 文件」的顺序编号为第 1 章…第 N 章，
    每章有编号、标题、路径、摘要与操作链接；
  * **左侧可折叠目录大纲**：按主题分组折叠，点击平滑滚动到对应章节，
    滚动时自动定位「当前阅读位置」（IntersectionObserver）；
  * **顶部导航**：标题 + 当前章节面包屑 + 章节下拉快速跳转 + 移动端抽屉开关，
    页面顶端有阅读进度条；
  * **链式导航**：每章底部自动算「上一章 / 下一章」并显示章节名；
  * **交互**：平滑滚动、章节悬停高亮、搜索过滤、返回顶部；
  * **响应式**：桌面左右分栏，移动端侧栏变抽屉。

纯内联 CSS / 原生 JS，零外部依赖，双击即离线可用。

用法：
    python3 scripts/gen_doc_index.py
输出：
    publishing/html/index.html
"""
import os
import re
import html
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "publishing", "html")
OUT_FILE = os.path.join(OUT_DIR, "index.html")

# 不视为「文档」的目录
EXCLUDE_DIRS = {".git", ".workbuddy", "node_modules", "__pycache__",
                ".venv", "venv", "site-packages", ".pytest_cache", ".mypy_cache"}

# 主题定义（顺序即侧栏顺序，也决定章节编号顺序）。key 为顶层目录名。
THEMES = [
    ("root",               "项目总览",        "仓库根目录的总览、进度、路线图与导航"),
    ("llm-fundamentals",   "大模型理论基础",  "11 章理论 + 配套 demo 证据"),
    ("python-practice",    "Python 练手层",   "6 个动手练习 + 延伸阅读"),
    ("projects",           "实践项目",        "10 个可交付项目（milestones / exercises）"),
    ("publishing",         "发布产物（派生）", "由 projects 派生的文章 / 教程 / 微调系列"),
    ("audit",              "审计与复盘",      "仓库体检与错误复盘"),
    ("mistakes",           "审计与复盘",      "仓库体检与错误复盘"),
]

DOCS_DIR = os.path.join(OUT_DIR, "docs")

# 手工保留的「自包含便携版」：图片 base64 内嵌，双击即离线可读。
# 也在 docs/ 镜像树里，但刻意用 .portable.html 后缀——渲染产物叫 <源文件名>.html，
# 同名会被下一次 build_docs_html.py --force 覆盖掉。
PORTABLE = {
    "python-practice/07-延伸阅读.md": "python-practice/07-延伸阅读.portable.html",
    "llm-fundamentals/12-tutorials-and-agent.md":
        "llm-fundamentals/12-tutorials-and-agent.portable.html",
}

H1_RE = re.compile(r"^\s*#\s+(.+?)\s*#*\s*$", re.M)
NUM_RE = re.compile(r"(\d+)")
NUM_PREFIX_RE = re.compile(r"^(\d{2})-")


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in NUM_RE.split(s)]


def first_heading(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = H1_RE.match(line)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return None


def excerpt(path, limit=110):
    """给章节一段「人能读」的摘要：跳过标题、代码块、表格、图片，正文抓前 limit 字。

    为什么不能省：只给标题的话，这份总览就是个链接堆，看不出哪章讲啥。
    摘要直接从源 .md 现算，不落盘、不缓存——源文档一改，下次生成自动跟着变。
    """
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            buf = f.read(6000)
    except Exception:
        return ""
    out, in_fence = [], False
    for raw in buf.split("\n"):
        s = raw.strip()
        if s.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or not s:
            continue
        if s[0] in "#>|-=<!" or set(s) <= {"-"} and len(s) > 3:
            continue
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"[*_`~]{1,3}", "", s)
        s = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", s)
        out.append(s)
        if sum(len(x) for x in out) >= limit:
            break
    txt = re.sub(r"\s+", " ", "".join(out)).strip()
    if not txt:
        return ""
    return html.escape(txt[:limit] + ("…" if len(txt) > limit else ""))


def rendered_html_path(rel_md):
    """某篇 .md 对应的渲染页；未转换则返回 None（索引回退 .md，不会死链）。"""
    p = os.path.join(DOCS_DIR, rel_md[:-3] + ".html")
    return p if os.path.exists(p) else None


def theme_of(rel_parts):
    if not rel_parts:
        return "root"
    return rel_parts[0]


def subgroup_of(theme, rel_parts, fname):
    """返回 (子组排序键, 子组显示名)。"""
    if theme == "root":
        return ("0", "根文档")
    if theme == "llm-fundamentals":
        m = NUM_PREFIX_RE.match(fname)
        if m:
            return (m.group(1), f"第 {m.group(1)} 章")
        return ("99", "概览 / 其他")
    if theme == "python-practice":
        if len(rel_parts) >= 2:
            return (rel_parts[1], rel_parts[1])
        return ("00", "概览 / 其他")
    if theme in ("projects", "publishing"):
        if len(rel_parts) >= 2:
            return (rel_parts[1], rel_parts[1])
        return ("00", "根")
    return (rel_parts[0] if rel_parts else theme, rel_parts[0] if rel_parts else theme)


def collect():
    data = {t: {} for t, _, _ in THEMES}
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
        for fn in fns:
            if not fn.lower().endswith(".md"):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, ROOT)
            parts = rel.split(os.sep)
            theme = theme_of(parts)
            if theme not in data:
                data.setdefault("__other__", {})
                theme = "__other__"
            sub_key, sub_name = subgroup_of(theme, parts, fn)
            data[theme].setdefault(sub_key, []).append(
                (natural_key(rel), fn, rel, first_heading(full) or fn, sub_name))
    return data


# --------------------------------------------------------------------------
# 页面模板：占位符替换，避免 f-string 里满屏 {{ }}
# --------------------------------------------------------------------------
# 主题首屏脚本：必须在 <head> 里、CSS 之前**同步**执行。放到 body 末尾的话，
# 深色系统上会先渲染一屏浅色再跳成深色（闪白）。docs/*.html 与 ide.html 里有
# 同一份逻辑，三处共用 localStorage 键 `aij-theme`。
THEME_BOOT = """(function(){try{
var s=localStorage.getItem('aij-theme');
var sys=!!(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches);
var dark=(s==='dark')||((!s||s==='auto')&&sys);
document.documentElement.setAttribute('data-theme',dark?'dark':'light');
}catch(e){}})();"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AI 工程师之旅 · 文档总览</title>
<script>/*__THEMEBOOT__*/</script>
<style>__CSS__</style>
</head>
<body>
<div class="progress" id="progress"></div>

<header class="topbar">
  <button class="icon-btn only-mobile" id="drawerBtn" aria-label="目录">☰</button>
  <div class="brand">
    <span class="brand-title">AI 工程师之旅 · 文档总览</span>
    <span class="brand-sub" id="brandSub">__TOTAL__ 章 / __RENDERED__ 篇已渲染</span>
  </div>
  <div class="topbar-right">
    <a class="ide-link" href="ide.html" title="代码浏览器：15 个项目 / 675 个源码文件，单文件离线打开">⌘ 代码浏览器</a>
    <button class="theme-btn" id="themeBtn" type="button" aria-label="切换主题">🌗</button>
    <nav class="crumb" id="crumb"><span class="crumb-no">第 1 章</span><span class="crumb-t">目录</span></nav>
    <label class="jump">
      <select id="jump" aria-label="跳转到章节">
        __OPTIONS__
      </select>
    </label>
  </div>
</header>

<div class="scrim" id="scrim"></div>

<div class="layout">
  <aside class="sidebar" id="sidebar">
    <nav class="toc">
      <div class="toc-head">目录大纲 <span class="toc-count">__TOTAL__ 章</span></div>
      <div class="toc-scroll">__TOC__</div>
    </nav>
  </aside>

  <main class="content">
    <section class="hero">
      <h1>文档总览</h1>
      <p class="hero-desc">这份页面把仓库里 __TOTAL__ 篇 Markdown 按阅读顺序排成 __TOTAL__ 章：
      先从「项目总览」看清全局，再逐章进入理论基础、练手练习、实战项目与发布产物。
      左侧目录可折叠跳转到任意一章，每章底部自动给出上一章 / 下一章。</p>
      <div class="hero-toolbar">
        <div class="sw">
          <input id="q" type="search" autocomplete="off" spellcheck="false"
                 placeholder="搜索全部 __TOTAL__ 篇正文（标题 / 正文 / 代码，可空格分隔多词，快捷键 /）…"
                 aria-label="全站全文搜索" aria-controls="searchPanel" aria-expanded="false"/>
          <div class="search-panel" id="searchPanel" hidden></div>
        </div>
        <span class="meta" id="counter">共 __TOTAL__ 章</span>
      </div>
      <div class="hero-stats">
        <span><b>__TOTAL__</b> 章</span>
        <span><b>__RENDERED__</b> 篇已渲染</span>
        <span><b>__PORTABLE__</b> 篇带自包含便携版</span>
        <span>全站正文可全文检索（构建期索引 · 零后端 · 断网可用）</span>
      </div>
    </section>

    __BODY__

    <footer class="site-foot">
      <p>ai-engineer-journey · 文档总览由 <code>scripts/gen_doc_index.py</code> 生成，
      链接指向 <code>publishing/html/docs/</code> 下的渲染页；点「原始 Markdown」
      会打开该页的源码视图（带行号、可复制、可下载 .md）。
      带<span class="chip-demo">便携版</span>标签的单文件图片已 base64 内嵌，断网也能双击打开。</p>
      <button class="top-btn" id="topBtn">↑ 回到顶部</button>
    </footer>
  </main>
</div>

<script>__JS__</script>
</body>
</html>
"""

CSS = """
:root{
  --bg:#f6f8fa; --panel:#ffffff; --ink:#1f2328; --ink-2:#3d444d; --muted:#656d76;
  --line:#d8dee4; --accent:#0969da; --accent-soft:#ddf4ff; --chip:#eaeef2;
  --accent-ink:#0969da; --accent-deep:#0757b5;
  --topbar-bg:rgba(255,255,255,.9); --input-bg:#ffffff;
  --hair:#eef1f4; --hover-line:#b6d7ff; --row-bg:#fbfcfd; --excerpt:#57606a;
  --mark-bg:#fff3a3; --mark-fg:#3d2c00;
  --prog-a:#0969da; --prog-b:#54aeff;
  --ide-bg:#123a5c; --ide-bd:#2f6ea8; --ide-fg:#cfe6ff; --ide-hbg:#17497a; --ide-hbd:#4a9fe0;
  --portable:#7c3aed; --portable-bg:#faf5ff; --portable-bd:#e9d5ff;
  --portable-hbg:#f3e8ff; --portable-hfg:#6d28d9;
  --toast-bg:#1f2328; --toast-fg:#fff;
  --shadow:0 1px 2px rgba(27,31,36,.06), 0 8px 24px rgba(27,31,36,.06);
  --shadow-lg:0 12px 40px rgba(27,31,36,.16);
  --scrim:rgba(27,31,36,.28); --ring:rgba(9,105,218,.10);
  --topbar:56px;
}
/* 深色主题。只有这一份深色变量——「跟随系统」由 head 里的内联脚本换算成
   显式的 data-theme，纯 CSS 侧就不用再复制一份 media query 声明块。
   同一条规则用在 docs/*.html 与 ide.html，三处共用 localStorage 键 aij-theme。 */
html[data-theme="dark"]{
  --bg:#0d1117; --panel:#161b22; --ink:#e6edf3; --ink-2:#c9d1d9; --muted:#8b949e;
  --line:#30363d; --accent:#4493f8; --accent-soft:#12365e; --chip:#21262d;
  --accent-ink:#6cb6ff; --accent-deep:#388bfd;
  --topbar-bg:rgba(13,17,23,.92); --input-bg:#0d1117;
  --hair:#21262d; --hover-line:#1f6feb; --row-bg:#12181f; --excerpt:#9da7b3;
  --mark-bg:#6b5300; --mark-fg:#ffeaa7;
  --prog-a:#4493f8; --prog-b:#1f6feb;
  --ide-bg:#0d419d; --ide-bd:#1f6feb; --ide-fg:#cae8ff; --ide-hbg:#1158c7; --ide-hbd:#388bfd;
  --portable:#a371f7; --portable-bg:#1c1430; --portable-bd:#3d2a63;
  --portable-hbg:#26193f; --portable-hfg:#c9a6ff;
  --toast-bg:#e6edf3; --toast-fg:#0d1117;
  --shadow:0 1px 2px rgba(0,0,0,.5), 0 8px 24px rgba(0,0,0,.4);
  --shadow-lg:0 14px 44px rgba(0,0,0,.6);
  --scrim:rgba(1,4,9,.62); --ring:rgba(68,147,248,.18);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.85em;}

/* 阅读进度条 */
.progress{position:fixed; inset:0 0 auto 0; height:3px; background:transparent; z-index:80;}
.progress::after{content:""; display:block; height:100%; width:var(--p,0%);
  background:linear-gradient(90deg,var(--prog-a),var(--prog-b)); transition:width .1s linear;}

/* 顶部导航 */
.topbar{
  position:sticky; top:0; z-index:60; height:var(--topbar);
  display:flex; align-items:center; gap:12px; padding:0 18px;
  background:var(--topbar-bg); backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);
}
.brand{display:flex; flex-direction:column; line-height:1.25; min-width:0;}
.brand-title{font-weight:650; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.brand-sub{color:var(--muted); font-size:12px;}
.topbar-right{margin-left:auto; display:flex; align-items:center; gap:10px;}
.ide-link{padding:6px 12px;border-radius:7px;border:1px solid var(--ide-bd);background:var(--ide-bg);color:var(--ide-fg);text-decoration:none;font-size:12.5px;white-space:nowrap}
.ide-link:hover{background:var(--ide-hbg);border-color:var(--ide-hbd);color:#fff}
.crumb{display:flex; align-items:center; gap:8px; min-width:0; color:var(--muted); font-size:12.5px;}
.crumb-no{background:var(--accent-soft); color:var(--accent-ink); border-radius:999px; padding:2px 9px;
  font-weight:600; font-variant-numeric:tabular-nums; white-space:nowrap;}
.crumb-t{white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:34vw;}
.jump select{
  height:32px; border:1px solid var(--line); border-radius:8px; background:var(--input-bg);
  color:var(--ink); font-size:13px; padding:0 8px; max-width:180px;
}
.icon-btn{display:none;}
.theme-btn{
  flex:none; width:32px; height:32px; padding:0; cursor:pointer; line-height:1;
  border:1px solid var(--line); border-radius:8px; background:var(--input-bg);
  color:var(--ink); font-size:14px;
}
.theme-btn:hover{border-color:var(--accent); color:var(--accent);}

/* 侧栏目录 */
.layout{display:grid; grid-template-columns:272px minmax(0,1fr); align-items:start; gap:0;}
.sidebar{position:sticky; top:var(--topbar); height:calc(100vh - var(--topbar)); overflow:hidden;}
.toc{height:100%; display:flex; flex-direction:column; border-right:1px solid var(--line); background:var(--panel);}
.toc-head{display:flex; align-items:center; justify-content:space-between;
  padding:14px 16px 10px; font-size:12px; letter-spacing:.06em; color:var(--muted); text-transform:uppercase;}
.toc-count{background:var(--chip); border-radius:999px; padding:1px 8px; text-transform:none; letter-spacing:0;}
.toc-scroll{overflow:auto; padding:0 10px 24px; scrollbar-width:thin;}
.toc-group{border-bottom:1px solid var(--hair);}
.toc-group > summary{
  cursor:pointer; list-style:none; padding:9px 8px; border-radius:8px;
  font-size:13.5px; font-weight:600; display:flex; align-items:center; gap:6px; user-select:none;
}
.toc-group > summary::-webkit-details-marker{display:none;}
.toc-group > summary::before{content:"▾"; color:var(--muted); font-size:10px; transition:transform .15s;}
.toc-group:not([open]) > summary::before{transform:rotate(-90deg);}
.toc-group > summary:hover{background:var(--chip);}
.toc-group > summary .cnt{margin-left:auto; color:var(--muted); font-weight:400; font-size:11.5px;}
.toc-list{list-style:none; margin:2px 0 10px; padding:0 0 0 12px; border-left:1px solid var(--line);}
.toc-link{
  display:block; padding:5px 8px; border-radius:6px; color:var(--ink-2);
  font-size:13px; text-decoration:none; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.toc-link:hover{background:var(--accent-soft); color:var(--accent-ink);}
.toc-link .tn{color:var(--muted); font-variant-numeric:tabular-nums; margin-right:6px; font-size:11.5px;}
.toc-link.active{background:var(--accent-soft); color:var(--accent-ink); font-weight:600;}
.toc-link.active .tn{color:var(--accent-ink);}
.toc-link.hidden{display:none;}

/* 正文 */
.content{max-width:900px; padding:26px 26px 80px; min-width:0;}
.hero{background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:26px 24px; margin-bottom:22px; box-shadow:var(--shadow);}
.hero h1{margin:0 0 8px; font-size:24px;}
.hero-desc{margin:0 0 14px; color:var(--muted);}
.hero-toolbar{display:flex; gap:10px; align-items:flex-start; margin-bottom:14px; flex-wrap:wrap;}
.sw{position:relative; flex:1; min-width:230px;}
.sw input{
  width:100%; padding:8px 12px; border:1px solid var(--line);
  border-radius:8px; font-size:14px; background:var(--input-bg); color:var(--ink);
}
.sw input:focus{outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft);}
.hero-toolbar .meta{color:var(--muted); font-size:13px; white-space:nowrap; padding-top:9px;}

/* 全站全文搜索：结果面板（构建期索引 + 纯前端检索，零后端） */
.search-panel{
  position:absolute; top:calc(100% + 6px); left:0; right:0; z-index:70;
  background:var(--panel); border:1px solid var(--line); border-radius:10px;
  box-shadow:var(--shadow); max-height:min(64vh, 540px); overflow:auto;
}
.search-panel[hidden]{display:none;}
.sp-head{
  position:sticky; top:0; z-index:1; background:var(--panel);
  padding:9px 14px; border-bottom:1px solid var(--line);
  font-size:12.5px; color:var(--muted);
}
.sp-head b{color:var(--accent); font-variant-numeric:tabular-nums;}
.sp-tip{margin-left:8px; opacity:.85;}
.sp-item{display:block; padding:10px 14px; border-bottom:1px solid var(--line); color:inherit;}
.sp-item:last-child{border-bottom:none;}
.sp-item:hover,.sp-item:focus{background:var(--accent-soft); outline:none;}
.sp-doc{display:block; font-size:11.5px; color:var(--muted); margin-bottom:2px;}
.sp-sec{display:block; font-size:13.5px; font-weight:600; color:var(--ink); margin-bottom:3px;}
.sp-snip{display:block; font-size:12.5px; color:var(--muted); line-height:1.65;}
.search-panel mark{background:var(--mark-bg); color:var(--mark-fg); border-radius:3px; padding:0 1px;}

.hero-stats{display:flex; flex-wrap:wrap; gap:10px;}
.hero-stats span{background:var(--chip); border-radius:8px; padding:5px 11px; font-size:12.5px; color:var(--muted);}
.hero-stats b{color:var(--ink); font-variant-numeric:tabular-nums;}

.chapter{
  background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:20px 22px; margin-bottom:16px; scroll-margin-top:calc(var(--topbar) + 14px);
  transition:border-color .18s, box-shadow .18s, transform .18s;
}
.chapter:hover{border-color:var(--hover-line); box-shadow:var(--shadow); transform:translateY(-1px);}
.chapter.active{border-color:var(--accent); box-shadow:0 0 0 3px var(--ring);}
.ch-head{display:flex; gap:14px; align-items:flex-start;}
.ch-no{
  flex:none; min-width:44px; text-align:center; padding:5px 8px; border-radius:9px;
  background:var(--accent-soft); color:var(--accent-ink); font-size:13px; font-weight:700;
  font-variant-numeric:tabular-nums; line-height:1.3;
}
.ch-hd{min-width:0;}
.ch-hd h2{margin:0 0 3px; font-size:18px; line-height:1.4;}
.ch-hd h2 a{color:var(--ink); text-decoration:none;}
.ch-hd h2 a:hover{color:var(--accent); text-decoration:none;}
.ch-meta{margin:0; color:var(--muted); font-size:12.5px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;}
.ch-meta .path{font-family:ui-monospace,SFMono-Regular,Menlo,monospace; background:var(--chip);
  border-radius:5px; padding:1px 6px;}
.ch-excerpt{margin:10px 0 0 58px; color:var(--excerpt); font-size:14px; border-left:3px solid var(--line);
  padding-left:12px;}
.ch-actions{margin:14px 0 0 58px; display:flex; flex-wrap:wrap; gap:8px;}
.btn{
  display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:8px;
  border:1px solid var(--line); background:var(--input-bg); color:var(--ink); font-size:13px; text-decoration:none;
}
.btn:hover{border-color:var(--accent); color:var(--accent); background:var(--accent-soft); text-decoration:none;}
.btn.primary{background:var(--accent); border-color:var(--accent); color:#fff;}
.btn.primary:hover{background:var(--accent-deep); color:#fff;}
.btn.portable{color:var(--portable); border-color:var(--portable-bd); background:var(--portable-bg);}
.btn.portable:hover{background:var(--portable-hbg); color:var(--portable-hfg); border-color:var(--portable);}
.btn.copy{font:inherit; font-size:13px; cursor:pointer;}
.chip-demo{background:var(--portable-bg); color:var(--portable); border:1px solid var(--portable-bd); border-radius:999px; padding:0 6px;}

/* 轻量提示条（复制反馈） */
.toast{
  position:fixed; left:50%; bottom:26px; z-index:120;
  transform:translate(-50%,10px); opacity:0; pointer-events:none;
  background:var(--toast-bg); color:var(--toast-fg); padding:9px 16px; border-radius:10px;
  font-size:13px; max-width:80vw; text-align:center; transition:.2s;
  box-shadow:0 10px 30px var(--scrim);
}
.toast.on{opacity:1; transform:translate(-50%,0);}
kbd{background:var(--chip); border:1px solid var(--line); border-bottom-width:2px;
  border-radius:4px; padding:0 5px; font-size:11.5px; font-family:inherit;}

/* 章节链式导航 */
.chapter-nav{display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:14px; margin-left:58px;}
.chapter-nav .nav-card{
  display:block; padding:11px 13px; border:1px solid var(--line); border-radius:10px;
  background:var(--row-bg); text-decoration:none; color:var(--ink); min-width:0;
}
.chapter-nav .nav-card:hover{border-color:var(--accent); background:var(--accent-soft);}
.chapter-nav .nav-card.next{text-align:right;}
.chapter-nav .nav-label{display:block; color:var(--muted); font-size:11.5px; margin-bottom:2px;}
.chapter-nav .nav-name{display:block; font-size:13.5px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.chapter-nav .empty{opacity:.4; pointer-events:none;}

.site-foot{
  margin-top:26px; padding-top:18px; border-top:1px solid var(--line);
  color:var(--muted); font-size:13px; display:flex; align-items:center; gap:14px; flex-wrap:wrap;
}
.site-foot p{margin:0; max-width:70ch;}
.top-btn{
  margin-left:auto; border:1px solid var(--line); background:var(--input-bg); color:var(--ink);
  border-radius:999px; padding:7px 14px; font-size:13px; cursor:pointer;
}
.top-btn:hover{border-color:var(--accent); color:var(--accent);}
.top-btn.show{display:inline-block;}

/* 响应式：移动端侧栏变抽屉 */
@media (max-width:900px){
  .layout{grid-template-columns:1fr;}
  .icon-btn{display:inline-flex; align-items:center; justify-content:center;
    width:34px; height:34px; border:1px solid var(--line); border-radius:8px; background:var(--input-bg); font-size:15px;}
  .crumb-t{display:none;}
  .jump select{max-width:120px;}
  .sidebar{
    position:fixed; top:var(--topbar); bottom:0; left:0; z-index:70; width:78%; max-width:300px;
    height:auto; transform:translateX(-102%); transition:transform .22s ease;
    box-shadow:var(--shadow-lg);
  }
  .sidebar.open{transform:translateX(0);}
  .scrim{position:fixed; inset:0; background:var(--scrim); z-index:65; display:none;}
  .scrim.show{display:block;}
  .content{padding:18px 14px 70px;}
  .ch-excerpt,.ch-actions,.chapter-nav{margin-left:0;}
  .chapter-nav{grid-template-columns:1fr;}
  .chapter-nav .nav-card.next{text-align:left;}
  .ch-head{gap:11px;}
}
"""

# JS 段用 raw 字符串：里面全是正则转义（\u0001 / \s / \+ / [\]\\]），
# 非 raw 时 Python 会先吃一层反斜杠（\u0001 变控制字符、\] 变 ]），
# 产物里的正则静默损坏——页面不报错，只是高亮和分词悄悄失灵。
JS = r"""
(function(){
  var chapters = Array.prototype.slice.call(document.querySelectorAll('.chapter'));
  var links = Array.prototype.slice.call(document.querySelectorAll('.toc-link'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('.toc-group'));
  var progress = document.getElementById('progress');
  var crumbNo = document.querySelector('.crumb-no');
  var crumbT = document.querySelector('.crumb-t');
  var topBtn = document.getElementById('topBtn');
  var drawerBtn = document.getElementById('drawerBtn');
  var scrim = document.getElementById('scrim');
  var sidebar = document.getElementById('sidebar');
  var current = -1;

  function go(el, instant){
    if(!el) return;
    var y = el.getBoundingClientRect().top + window.pageYOffset - 72;
    // 深链（从章节页点「返回文档总览」回来）用瞬移：隔着上百张卡做平滑滚动，
    // 用户要盯着屏幕滑好几秒，体验比直接落位差得多。
    window.scrollTo({top: y, behavior: instant ? 'instant' : 'smooth'});
    if(sidebar.classList.contains('open')) closeDrawer();
  }
  links.forEach(function(a){
    a.addEventListener('click', function(e){
      var id = a.getAttribute('href').slice(1);
      var el = document.getElementById(id);
      if(!el) return;
      e.preventDefault();
      go(el);
      history.replaceState(null, '', '#' + id);
    });
  });

  var jump = document.getElementById('jump');
  jump.addEventListener('change', function(){
    go(document.getElementById(jump.value));
  });

  function closeDrawer(){ sidebar.classList.remove('open'); scrim.classList.remove('show'); }
  drawerBtn.addEventListener('click', function(){
    sidebar.classList.toggle('open');
    scrim.classList.toggle('show');
  });
  scrim.addEventListener('click', closeDrawer);
  linkGroup('.chapter .btn', function(){ if(sidebar.classList.contains('open')) closeDrawer(); });
  linkGroup('.chapter .ch-hd h2 a', function(){ if(sidebar.classList.contains('open')) closeDrawer(); });
  function linkGroup(sel, fn){
    Array.prototype.forEach.call(document.querySelectorAll(sel), function(a){
      a.addEventListener('click', fn);
    });
  }

  // 当前章节高亮：取视口顶部附近最靠上的那一章
  function setActive(idx){
    if(idx === current) return;
    current = idx;
    links.forEach(function(a, i){
      a.classList.toggle('active', i === idx);
      if(i === idx){
        var g = a.closest('.toc-group');
        if(g && !g.open) g.open = true;
        var hit = a.getBoundingClientRect();
        var box = document.querySelector('.toc-scroll').getBoundingClientRect();
        if(hit.top < box.top + 8 || hit.bottom > box.bottom - 8){
          a.scrollIntoView({block:'nearest'});
        }
      }
    });
    chapters.forEach(function(s, i){ s.classList.toggle('active', i === idx); });
    var title = chapters[idx] ? (chapters[idx].querySelector('.ch-hd h2').textContent.trim()) : '';
    crumbNo.textContent = '第 ' + (idx + 1) + ' 章';
    crumbT.textContent = title;
    jump.value = 'ch-' + (idx + 1);
  }

  if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(entries){
      var best = null;
      entries.forEach(function(en){
        if(en.isIntersecting && (!best || en.boundingClientRect.top < best.boundingClientRect.top)) best = en;
      });
      if(best) setActive(chapters.indexOf(best.target));
    }, {rootMargin: '-70px 0px -65% 0px', threshold: 0});
    chapters.forEach(function(s){ io.observe(s); });
  }

  function onScroll(){
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h > 0 ? (window.pageYOffset / h) : 0;
    progress.style.setProperty('--p', (p * 100).toFixed(2) + '%');
    topBtn.classList.toggle('show', window.pageYOffset > 420);
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('resize', onScroll);
  onScroll();

  topBtn.addEventListener('click', function(){
    window.scrollTo({top:0, behavior:'smooth'});
  });

  // ---------------------------------------------------------------------
  // 搜索：① 即时过滤章节卡片（不依赖索引）② 全站正文全文检索（构建期索引）
  // ---------------------------------------------------------------------
  var q = document.getElementById('q');
  var counter = document.getElementById('counter');
  var brandSub = document.getElementById('brandSub');
  var panel = document.getElementById('searchPanel');
  if(brandSub) brandSub.dataset.orig = brandSub.textContent;

  function filterChapters(){
    var s = q.value.trim().toLowerCase(), shown = 0;
    chapters.forEach(function(section, i){
      var txt = (section.textContent + ' ' + section.dataset.k).toLowerCase();
      var ok = !s || txt.indexOf(s) !== -1;
      section.style.display = ok ? '' : 'none';
      if(ok) shown++;
      links[i].classList.toggle('hidden', !ok);
    });
    counter.textContent = s ? ('匹配 ' + shown + ' / ' + chapters.length) : ('共 ' + chapters.length + ' 章');
    if(brandSub) brandSub.textContent = s
      ? (shown + ' / ' + chapters.length + ' 章')
      : brandSub.dataset.orig;
  }

  /* ---------- 全站正文检索（索引按需加载） ---------- */
  var SEC = null, SEC_LOADING = false;

  function loadIndex(){
    if(SEC || SEC_LOADING) return;
    SEC_LOADING = true;
    var el = document.createElement('script');
    el.src = 'search-data.js';
    el.onload = function(){
      SEC_LOADING = false;
      SEC = window.__SEARCH__ || null;
      if(!SEC) showPanel('<div class="sp-head">索引已加载，但没有读到数据</div>');
      else if(q.value.trim()) runSearch();
    };
    el.onerror = function(){
      SEC_LOADING = false;
      showPanel('<div class="sp-head">没有找到搜索索引 search-data.js'
        + '<span class="sp-tip">先跑 <code>python3 scripts/gen_search_index.py</code> 生成</span></div>');
    };
    document.head.appendChild(el);
  }
  // 空闲预热：用户第一次敲键盘时索引通常已就绪，省掉「正在载入」的等待感。
  // 用 <script src> 而不是 fetch —— file:// 下 fetch 本地 JSON 会被 CORS 拦掉。
  if(window.requestIdleCallback) requestIdleCallback(loadIndex, {timeout:2500});
  else setTimeout(loadIndex, 1500);

  function escHtml(s){
    return String(s).replace(/[&<>"]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }
  function rxEsc(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  // 高亮：先在原文上打一对占位符，再整体转义，最后把占位符换回 <mark>。
  // 若反过来「先转义再替换」，关键词里含 & < > 时就和转义后的正文对不上，高亮整段失效。
  function mark(text, terms){
    var re = new RegExp('(' + terms.map(rxEsc).join('|') + ')', 'gi');
    return escHtml(String(text).replace(re, '\u0001$1\u0002'))
      .replace(/\u0001/g, '<mark>').replace(/\u0002/g, '</mark>');
  }
  function snippet(text, terms){
    if(!text) return '';
    var lower = text.toLowerCase(), pos = -1;
    for(var i=0;i<terms.length;i++){
      var p = lower.indexOf(terms[i]);
      if(p >= 0 && (pos < 0 || p < pos)) pos = p;
    }
    if(pos < 0) pos = 0;
    var start = Math.max(0, pos - 30), end = Math.min(text.length, pos + 90);
    return mark((start > 0 ? '…' : '') + text.slice(start, end)
      + (end < text.length ? '…' : ''), terms);
  }
  function showPanel(html){
    if(!panel) return;
    panel.innerHTML = html;
    panel.hidden = false;
    q.setAttribute('aria-expanded', 'true');
  }
  function hidePanel(){
    if(!panel) return;
    panel.hidden = true;
    panel.innerHTML = '';
    q.setAttribute('aria-expanded', 'false');
  }

  var MAX_HITS = 30;
  function renderHits(hits, terms, raw){
    if(!hits.length){
      showPanel('<div class="sp-head">没有找到「' + escHtml(raw) + '」'
        + '<span class="sp-tip">试试更短的关键词；空格分隔的多个词要求同时命中</span></div>');
      return;
    }
    var secs = SEC.secs, docs = SEC.docs, out = [];
    out.push('<div class="sp-head">正文命中 <b>' + hits.length + '</b> 个小节'
      + (hits.length > MAX_HITS ? '（显示前 ' + MAX_HITS + ' 条）' : '')
      + '<span class="sp-tip">点条目在新标签打开对应小节</span></div>');
    for(var k=0;k<hits.length && k<MAX_HITS;k++){
      var s = secs[hits[k].i], d = docs[s[0]];
      var url = d[2] + (s[1] ? '#' + encodeURIComponent(s[1]) : '');
      out.push('<a class="sp-item" href="' + escHtml(url) + '" target="_blank" rel="noopener">'
        + '<span class="sp-doc">第 ' + d[3] + ' 章 · ' + escHtml(d[1]) + '</span>'
        + (s[2] ? '<span class="sp-sec">' + mark(s[2], terms) + '</span>' : '')
        + '<span class="sp-snip">' + snippet(s[3], terms) + '</span>'
        + '</a>');
    }
    showPanel(out.join(''));
  }

  function runSearch(){
    var raw = q.value.trim();
    if(!raw){ hidePanel(); return; }
    if(!SEC){
      showPanel('<div class="sp-head">正在载入搜索索引…</div>');
      loadIndex(); return;
    }
    var terms = raw.toLowerCase().split(/\s+/).filter(Boolean);
    if(!terms.length){ hidePanel(); return; }
    var secs = SEC.secs, hits = [];
    for(var i=0;i<secs.length;i++){
      var s = secs[i], head = s[2].toLowerCase(), body = s[3].toLowerCase();
      var score = 0, ok = true, lo = -1, hi = -1;
      for(var t=0;t<terms.length;t++){
        var term = terms[t];
        var hp = head.indexOf(term), bp = body.indexOf(term);
        if(hp < 0 && bp < 0){ ok = false; break; }
        if(hp >= 0) score += 150 - Math.min(hp, 80);      // 命中标题权重最高
        if(bp >= 0){
          score += 30;
          var p = bp, cnt = 0;
          while(p >= 0 && cnt < 8){ cnt++; p = body.indexOf(term, p + term.length); }
          score += cnt * 4;                               // 出现次数
          if(lo < 0 || bp < lo) lo = bp;
          if(bp > hi) hi = bp;
        }
      }
      if(!ok) continue;
      // 多词落点越集中，越可能是「整段在讲这件事」，而不是零散撞词
      if(terms.length > 1 && lo >= 0) score += Math.max(0, 60 - Math.min((hi - lo) / 12, 60));
      if(s[1] && head.indexOf(terms[0]) >= 0) score += 40;  // 有锚点 → 能直达小节
      hits.push({i:i, score:score, pos:lo < 0 ? 0 : lo});
    }
    hits.sort(function(a,b){ return b.score - a.score || a.pos - b.pos; });
    renderHits(hits, terms, raw);
  }

  if(q){
    q.addEventListener('input', function(){ filterChapters(); runSearch(); });
    q.addEventListener('focus', function(){ if(q.value.trim()) runSearch(); });
    q.addEventListener('keydown', function(e){
      if(e.key !== 'Enter') return;
      var first = panel && panel.querySelector('.sp-item');
      if(first){ e.preventDefault(); first.click(); }
    });
    document.addEventListener('click', function(e){
      if(!panel.hidden && e.target !== q && !panel.contains(e.target)) hidePanel();
    });
  }

  /* ---------- 复制路径 ---------- */
  var toastEl = document.createElement('div');
  toastEl.className = 'toast';
  document.body.appendChild(toastEl);
  var toastTimer;
  function toast(msg){
    toastEl.textContent = msg;
    toastEl.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ toastEl.classList.remove('on'); }, 2000);
  }
  function copyText(text, msg){
    function fallback(){
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly','');
      ta.style.cssText = 'position:fixed;top:-1000px;left:0;opacity:0';
      document.body.appendChild(ta); ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch(e){ ok = false; }
      document.body.removeChild(ta);
      toast(ok ? msg : '复制失败：请手动选中后复制');
    }
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(function(){ toast(msg); }, fallback);
    } else fallback();
  }
  Array.prototype.forEach.call(document.querySelectorAll('.btn.copy'), function(b){
    b.addEventListener('click', function(){
      copyText(b.getAttribute('data-path') || '', '已复制路径：' + b.getAttribute('data-path'));
    });
  });

  /* ---------- 快捷键：/ 聚焦搜索，Esc 清空并收起结果 ---------- */
  document.addEventListener('keydown', function(e){
    if(e.metaKey || e.ctrlKey || e.altKey) return;
    if(e.key === '/' && q && document.activeElement !== q){
      e.preventDefault(); q.focus(); q.select();
    } else if(e.key === 'Escape' && q && document.activeElement === q){
      q.value = '';
      q.dispatchEvent(new Event('input'));
      hidePanel();
      q.blur();
    }
  });

  // 深链 #q=关键词：从章节页顶栏的「搜索」入口过来时，直接带词落在这里。
  // 章节页拿不到索引，所以搜索统一由总览页承接，避免两处各维护一套。
  function applyQueryHash(){
    var h = window.location.hash;
    if(h.indexOf('#q=') !== 0 || !q) return;
    var term = '';
    try { term = decodeURIComponent(h.slice(3).replace(/\+/g, ' ')); } catch(err){ term = h.slice(3); }
    if(!term) return;
    q.value = term;
    filterChapters();
    loadIndex();
    runSearch();
  }
  applyQueryHash();
  window.addEventListener('hashchange', function(){
    if(window.location.hash.indexOf('#q=') === 0) applyQueryHash();
  });

  // 首屏定位：带 #ch-xx 直接落到该章
  var hash = window.location.hash;
  if(hash.indexOf('#ch-') === 0){
    var el = document.getElementById(hash.slice(1));
    if(el) setTimeout(function(){ go(el, true); }, 60);
  }
  // 同一页面内改 hash（浏览器前进/后退、或再次点「返回文档总览」）也要落位，
  // 否则只有首次加载生效，回来的人会停在原地。
  window.addEventListener('hashchange', function(){
    var h = window.location.hash;
    if(h.indexOf('#ch-') !== 0) return;
    var el = document.getElementById(h.slice(1));
    if(el) go(el, true);
  });

  /* ---------- 主题：跟随系统 / 浅色 / 深色 三态循环 ---------- */
  // 首屏那一下由 head 里的内联脚本完成（否则深色系统上会先闪一屏白），
  // 这里只负责切换与记忆。localStorage 键 `aij-theme` 与 docs/*.html、
  // ide.html 共用——三处必须一致，否则从章节页点回总览会跳色。
  var themeBtn = document.getElementById('themeBtn');
  var THEME_ICON = {auto:'🌗', light:'☀️', dark:'🌙'};
  var THEME_NAME = {auto:'跟随系统', light:'浅色', dark:'深色'};

  function themePref(){
    try { return localStorage.getItem('aij-theme') || 'auto'; } catch(e){ return 'auto'; }
  }
  function themeIsDark(p){
    var sys = !!(window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    return p === 'dark' || (p === 'auto' && sys);
  }
  function applyTheme(p){
    if(p !== 'light' && p !== 'dark') p = 'auto';
    document.documentElement.setAttribute('data-theme', themeIsDark(p) ? 'dark' : 'light');
    if(themeBtn){
      themeBtn.textContent = THEME_ICON[p];
      themeBtn.title = '主题：' + THEME_NAME[p] + '（点击切换）';
    }
  }
  if(themeBtn){
    applyTheme(themePref());
    themeBtn.addEventListener('click', function(){
      var order = ['auto', 'light', 'dark'];
      var next = order[(order.indexOf(themePref()) + 1) % order.length];
      try { localStorage.setItem('aij-theme', next); } catch(e){}
      applyTheme(next);
    });
    if(window.matchMedia){
      var mq = matchMedia('(prefers-color-scheme: dark)');
      var onSys = function(){ if(themePref() === 'auto') applyTheme('auto'); };
      if(mq.addEventListener) mq.addEventListener('change', onSys);
      else if(mq.addListener) mq.addListener(onSys);
    }
  }
})();
"""


def ordered_docs(data=None):
    """全仓库文档的**唯一**排序口径：主题 → 子分组 → 文件名，编号第 1…N 章。

    索引页、渲染页的「返回总览」回链、自校验都从这里取编号。以前这段排序逻辑
    只长在 build_html 里，渲染页想拿章节号就得再抄一份——抄一份就会漂移一份。
    """
    data = collect() if data is None else data
    out = []
    theme_order = [t for t, _, _ in THEMES] + (["__other__"] if "__other__" in data else [])
    for theme in theme_order:
        groups = data.get(theme) or {}
        for sk in sorted(groups.keys(), key=natural_key):
            for _, fn, rel, title, sub_name in sorted(groups[sk], key=lambda x: x[0]):
                rel_fwd = rel.replace(os.sep, "/")
                out.append({
                    "theme": theme, "sub": sub_name, "rel": rel_fwd, "title": title,
                    "rendered": rendered_html_path(rel_fwd),
                    "portable": PORTABLE.get(rel_fwd),
                })
    for i, c in enumerate(out, 1):
        c["idx"] = i
    return out


def chapter_map():
    """rel（正斜杠，含 .md 后缀）→ 章节号。供渲染页回链 index.html#ch-N。"""
    return {c["rel"]: c["idx"] for c in ordered_docs()}


def build_html(data):
    chapters = ordered_docs(data)
    total = len(chapters)
    total_rendered = sum(1 for c in chapters if c["rendered"])
    total_portable = sum(1 for c in chapters if c["portable"])

    # ---- 左侧目录大纲：按主题分组，分组顺序 = 章节流里主题首次出现的顺序 ----
    theme_name = {t: n for t, n, _ in THEMES}
    theme_name.setdefault("__other__", "其他")
    groups_toc, group_idx = [], {}
    for c in chapters:
        g = group_idx.get(c["theme"])
        if g is None:
            g = {"name": theme_name.get(c["theme"], c["theme"]), "items": []}
            group_idx[c["theme"]] = g
            groups_toc.append(g)
        g["items"].append((c["idx"], c["title"]))

    toc_html = []
    for g in groups_toc:
        lis = "\n".join(
            f'        <li><a class="toc-link" href="#ch-{i}">'
            f'<span class="tn">{i:02d}</span>{html.escape(t)}</a></li>'
            for i, t in g["items"])
        toc_html.append(
            f'    <details class="toc-group" open>\n'
            f'      <summary>{html.escape(g["name"])} '
            f'<span class="cnt">{len(g["items"])} 章</span></summary>\n'
            f'      <ul class="toc-list">\n{lis}\n      </ul>\n'
            f'    </details>')
    toc = "\n".join(toc_html)

    # ---- 顶部下拉快速跳转 ----
    options = "\n".join(
        f'        <option value="ch-{c["idx"]}">第 {c["idx"]} 章 · {html.escape(c["title"])}</option>'
        for c in chapters)

    # ---- 正文章节 ----
    body = []
    for c in chapters:
        i = c["idx"]
        rel = c["rel"]
        if c["rendered"]:
            href = os.path.relpath(c["rendered"], OUT_DIR).replace(os.sep, "/")
        else:
            href = os.path.join("..", "..", rel).replace(os.sep, "/")
        href = urllib.parse.quote(href, safe="/")
        # 「原始 Markdown」不再是死链：指向渲染页的源码视图（同一页面里的阅读/源码切换）。
        # 以前这里给的是 `rel`——那是相对仓库根的路径，从 publishing/html/ 打开必然 404。
        href_src = href + "#src" if c["rendered"] else None
        href_portable = None
        if c["portable"]:
            href_portable = urllib.parse.quote(
                os.path.relpath(os.path.join(DOCS_DIR, c["portable"]), OUT_DIR).replace(os.sep, "/"),
                safe="/")

        theme_disp = theme_name.get(c["theme"], c["theme"])
        ex = excerpt(os.path.join(ROOT, rel))
        actions = [f'<a class="btn primary" href="{href}" target="_blank" rel="noopener">打开渲染页</a>']
        if href_src:
            actions.append(
                f'<a class="btn" href="{href_src}" target="_blank" rel="noopener" '
                f'title="在页面内查看这篇文档的原始 Markdown 源码（带行号、可复制、可下载）">'
                f'原始 Markdown</a>')
        if href_portable:
            actions.append(
                f'<a class="btn portable" href="{href_portable}" target="_blank" rel="noopener">'
                f'便携版（自包含）</a>')
        actions.append(
            f'<button class="btn copy" type="button" data-path="{html.escape(rel)}" '
            f'title="复制该文档在仓库里的相对路径">⧉ 路径</button>')
        if not c["rendered"]:
            actions.insert(0, '<span class="btn" style="color:var(--muted);cursor:default">尚未渲染</span>')

        prev_c = chapters[i - 2] if i >= 2 else None
        next_c = chapters[i] if i < len(chapters) else None
        nav = ['    <nav class="chapter-nav">']
        if prev_c:
            nav.append(
                f'      <a class="nav-card" href="#ch-{prev_c["idx"]}">'
                f'<span class="nav-label">← 上一章 · 第 {prev_c["idx"]} 章</span>'
                f'<span class="nav-name">{html.escape(prev_c["title"])}</span></a>')
        else:
            nav.append('<span class="nav-card empty"><span class="nav-label">← 上一章</span>'
                       '<span class="nav-name">已是第一章</span></span>')
        if next_c:
            nav.append(
                f'      <a class="nav-card next" href="#ch-{next_c["idx"]}">'
                f'<span class="nav-label">下一章 · 第 {next_c["idx"]} 章 →</span>'
                f'<span class="nav-name">{html.escape(next_c["title"])}</span></a>')
        else:
            nav.append('<span class="nav-card next empty"><span class="nav-label">下一章 →</span>'
                       '<span class="nav-name">已是最后一章</span></span>')
        nav.append('    </nav>')

        body.append(
            f'    <section class="chapter" id="ch-{i}" data-k="{html.escape(rel + " " + c["title"])}">\n'
            f'      <div class="ch-head">\n'
            f'        <span class="ch-no">第 {i} 章</span>\n'
            f'        <div class="ch-hd">\n'
            f'          <h2><a href="{href}" target="_blank" rel="noopener">{html.escape(c["title"])}</a></h2>\n'
            f'          <p class="ch-meta"><span class="path">{html.escape(rel)}</span>'
            f'<span>{html.escape(theme_disp)} · {html.escape(c["sub"])}</span></p>\n'
            f'        </div>\n'
            f'      </div>\n'
            + (f'      <p class="ch-excerpt">{ex}</p>\n' if ex else "")
            + '      <div class="ch-actions">\n' + "\n".join("        " + a for a in actions) + "\n      </div>\n"
            + "\n".join(nav) + "\n"
            f'    </section>')

    page = (PAGE
            .replace("/*__THEMEBOOT__*/", THEME_BOOT)
            .replace("__CSS__", CSS)
            .replace("__JS__", JS)
            .replace("__TOC__", toc)
            .replace("__BODY__", "\n".join(body))
            .replace("__OPTIONS__", options)
            .replace("__TOTAL__", str(total))
            .replace("__RENDERED__", str(total_rendered))
            .replace("__PORTABLE__", str(total_portable)))
    return page, total


def verify_index():
    """索引自校验：每条文档链接、源码视图链接、便携版链接都必须真实存在。

    漏掉「原始 .md」这一类链接的教训（2026-10-01）：之前只校验了「打开渲染页」和
    「便携版」两个 class 的 href，于是整批原始 md 链接全部 404 却一路绿灯——
    校验覆盖不到的地方，就等于没有校验。
    """
    bad, total = [], 0
    with open(OUT_FILE, encoding="utf-8") as f:
        text = f.read()
    pats = [r'class="btn primary" href="([^"]+)"',
            r'class="btn portable" href="([^"]+)"',
            r'class="btn" href="([^"]+)" target="_blank" rel="noopener" title="在页面内查看']
    for pat in pats:
        for u in re.findall(pat, text):
            total += 1
            local = urllib.parse.unquote(u.split("#")[0]).replace("/", os.sep)
            if not os.path.exists(os.path.join(OUT_DIR, local)):
                bad.append(u)
    return total, bad


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    page, total = build_html(collect())
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"已生成: {OUT_FILE}")
    print(f"章节总数: {page.count('<section class=\"chapter\"')}")
    checked, bad = verify_index()
    print(f"索引校验：检查 {checked} 条链接，失效 {len(bad)} 条")
    for u in bad[:20]:
        print("  死链:", u)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
