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

    为什么不能省：209 个章节只给标题的话，这份总览就是个链接堆，看不出哪章讲啥。
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
PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AI 工程师之旅 · 文档总览</title>
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
        <input id="q" type="search" placeholder="过滤章节（可按标题、路径或正文关键词）…"/>
        <span class="meta" id="counter">共 __TOTAL__ 章</span>
      </div>
      <div class="hero-stats">
        <span><b>__TOTAL__</b> 章</span>
        <span><b>__RENDERED__</b> 篇已渲染</span>
        <span><b>__PORTABLE__</b> 篇带自包含便携版</span>
      </div>
    </section>

    __BODY__

    <footer class="site-foot">
      <p>ai-engineer-journey · 文档总览由 <code>scripts/gen_doc_index.py</code> 生成，
      链接指向 <code>publishing/html/docs/</code> 下的渲染页。带<span class="chip-demo">便携版</span>
      标签的单文件图片已 base64 内嵌，断网也能双击打开。</p>
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
  --bg:#f6f8fa; --panel:#ffffff; --ink:#1f2328; --muted:#656d76;
  --line:#d8dee4; --accent:#0969da; --accent-soft:#ddf4ff; --chip:#eaeef2;
  --shadow:0 1px 2px rgba(27,31,36,.06), 0 8px 24px rgba(27,31,36,.06);
  --topbar:56px;
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
  background:linear-gradient(90deg,#0969da,#54aeff); transition:width .1s linear;}

/* 顶部导航 */
.topbar{
  position:sticky; top:0; z-index:60; height:var(--topbar);
  display:flex; align-items:center; gap:12px; padding:0 18px;
  background:rgba(255,255,255,.9); backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);
}
.brand{display:flex; flex-direction:column; line-height:1.25; min-width:0;}
.brand-title{font-weight:650; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.brand-sub{color:var(--muted); font-size:12px;}
.topbar-right{margin-left:auto; display:flex; align-items:center; gap:10px;}
.ide-link{padding:6px 12px;border-radius:7px;border:1px solid #2f6ea8;background:#123a5c;color:#cfe6ff;text-decoration:none;font-size:12.5px;white-space:nowrap}
.ide-link:hover{background:#17497a;border-color:#4a9fe0;color:#fff}
.crumb{display:flex; align-items:center; gap:8px; min-width:0; color:var(--muted); font-size:12.5px;}
.crumb-no{background:var(--accent-soft); color:#0969da; border-radius:999px; padding:2px 9px;
  font-weight:600; font-variant-numeric:tabular-nums; white-space:nowrap;}
.crumb-t{white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:34vw;}
.jump select{
  height:32px; border:1px solid var(--line); border-radius:8px; background:#fff;
  color:var(--ink); font-size:13px; padding:0 8px; max-width:180px;
}
.icon-btn{display:none;}

/* 侧栏目录 */
.layout{display:grid; grid-template-columns:272px minmax(0,1fr); align-items:start; gap:0;}
.sidebar{position:sticky; top:var(--topbar); height:calc(100vh - var(--topbar)); overflow:hidden;}
.toc{height:100%; display:flex; flex-direction:column; border-right:1px solid var(--line); background:var(--panel);}
.toc-head{display:flex; align-items:center; justify-content:space-between;
  padding:14px 16px 10px; font-size:12px; letter-spacing:.06em; color:var(--muted); text-transform:uppercase;}
.toc-count{background:var(--chip); border-radius:999px; padding:1px 8px; text-transform:none; letter-spacing:0;}
.toc-scroll{overflow:auto; padding:0 10px 24px; scrollbar-width:thin;}
.toc-group{border-bottom:1px solid #eef1f4;}
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
  display:block; padding:5px 8px; border-radius:6px; color:#3d444d;
  font-size:13px; text-decoration:none; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.toc-link:hover{background:var(--accent-soft); color:#0969da;}
.toc-link .tn{color:var(--muted); font-variant-numeric:tabular-nums; margin-right:6px; font-size:11.5px;}
.toc-link.active{background:var(--accent-soft); color:#0969da; font-weight:600;}
.toc-link.active .tn{color:#0969da;}
.toc-link.hidden{display:none;}

/* 正文 */
.content{max-width:900px; padding:26px 26px 80px; min-width:0;}
.hero{background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:26px 24px; margin-bottom:22px; box-shadow:var(--shadow);}
.hero h1{margin:0 0 8px; font-size:24px;}
.hero-desc{margin:0 0 14px; color:var(--muted);}
.hero-toolbar{display:flex; gap:10px; align-items:center; margin-bottom:14px; flex-wrap:wrap;}
.hero-toolbar input{
  flex:1; min-width:200px; padding:8px 12px; border:1px solid var(--line);
  border-radius:8px; font-size:14px; background:#fff; color:var(--ink);
}
.hero-toolbar input:focus{outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft);}
.hero-toolbar .meta{color:var(--muted); font-size:13px; white-space:nowrap;}
.hero-stats{display:flex; flex-wrap:wrap; gap:10px;}
.hero-stats span{background:var(--chip); border-radius:8px; padding:5px 11px; font-size:12.5px; color:var(--muted);}
.hero-stats b{color:var(--ink); font-variant-numeric:tabular-nums;}

.chapter{
  background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:20px 22px; margin-bottom:16px; scroll-margin-top:calc(var(--topbar) + 14px);
  transition:border-color .18s, box-shadow .18s, transform .18s;
}
.chapter:hover{border-color:#b6d7ff; box-shadow:var(--shadow); transform:translateY(-1px);}
.chapter.active{border-color:var(--accent); box-shadow:0 0 0 3px rgba(9,105,218,.10);}
.ch-head{display:flex; gap:14px; align-items:flex-start;}
.ch-no{
  flex:none; min-width:44px; text-align:center; padding:5px 8px; border-radius:9px;
  background:var(--accent-soft); color:#0969da; font-size:13px; font-weight:700;
  font-variant-numeric:tabular-nums; line-height:1.3;
}
.ch-hd{min-width:0;}
.ch-hd h2{margin:0 0 3px; font-size:18px; line-height:1.4;}
.ch-hd h2 a{color:var(--ink); text-decoration:none;}
.ch-hd h2 a:hover{color:var(--accent); text-decoration:none;}
.ch-meta{margin:0; color:var(--muted); font-size:12.5px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;}
.ch-meta .path{font-family:ui-monospace,SFMono-Regular,Menlo,monospace; background:var(--chip);
  border-radius:5px; padding:1px 6px;}
.ch-excerpt{margin:10px 0 0 58px; color:#57606a; font-size:14px; border-left:3px solid var(--line);
  padding-left:12px;}
.ch-actions{margin:14px 0 0 58px; display:flex; flex-wrap:wrap; gap:8px;}
.btn{
  display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:8px;
  border:1px solid var(--line); background:#fff; color:var(--ink); font-size:13px; text-decoration:none;
}
.btn:hover{border-color:var(--accent); color:var(--accent); background:var(--accent-soft); text-decoration:none;}
.btn.primary{background:var(--accent); border-color:var(--accent); color:#fff;}
.btn.primary:hover{background:#0757b5; color:#fff;}
.btn.portable{color:#7c3aed; border-color:#e9d5ff; background:#faf5ff;}
.btn.portable:hover{background:#f3e8ff; color:#6d28d9; border-color:#7c3aed;}
.chip-demo{background:#faf5ff; color:#7c3aed; border:1px solid #e9d5ff; border-radius:999px; padding:0 6px;}

/* 章节链式导航 */
.chapter-nav{display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:14px; margin-left:58px;}
.chapter-nav .nav-card{
  display:block; padding:11px 13px; border:1px solid var(--line); border-radius:10px;
  background:#fbfcfd; text-decoration:none; color:var(--ink); min-width:0;
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
  margin-left:auto; border:1px solid var(--line); background:#fff; color:var(--ink);
  border-radius:999px; padding:7px 14px; font-size:13px; cursor:pointer;
}
.top-btn:hover{border-color:var(--accent); color:var(--accent);}
.top-btn.show{display:inline-block;}

/* 响应式：移动端侧栏变抽屉 */
@media (max-width:900px){
  .layout{grid-template-columns:1fr;}
  .icon-btn{display:inline-flex; align-items:center; justify-content:center;
    width:34px; height:34px; border:1px solid var(--line); border-radius:8px; background:#fff; font-size:15px;}
  .crumb-t{display:none;}
  .jump select{max-width:120px;}
  .sidebar{
    position:fixed; top:var(--topbar); bottom:0; left:0; z-index:70; width:78%; max-width:300px;
    height:auto; transform:translateX(-102%); transition:transform .22s ease;
    box-shadow:0 12px 40px rgba(27,31,36,.16);
  }
  .sidebar.open{transform:translateX(0);}
  .scrim{position:fixed; inset:0; background:rgba(27,31,36,.28); z-index:65; display:none;}
  .scrim.show{display:block;}
  .content{padding:18px 14px 70px;}
  .ch-excerpt,.ch-actions,.chapter-nav{margin-left:0;}
  .chapter-nav{grid-template-columns:1fr;}
  .chapter-nav .nav-card.next{text-align:left;}
  .ch-head{gap:11px;}
}
"""

JS = """
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

  function go(el){
    if(!el) return;
    var y = el.getBoundingClientRect().top + window.pageYOffset - 72;
    window.scrollTo({top: y, behavior:'smooth'});
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

  // 搜索过滤（章节标题、摘要、路径）
  var q = document.getElementById('q');
  var counter = document.getElementById('counter');
  var brandSub = document.getElementById('brandSub');
  if(brandSub) brandSub.dataset.orig = brandSub.textContent;
  if(q){
    q.addEventListener('input', function(){
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
    });
  }

  // 首屏定位：带 #ch-xx 直接滚到该章
  var hash = window.location.hash;
  if(hash.indexOf('#ch-') === 0){
    var el = document.getElementById(hash.slice(1));
    if(el) setTimeout(function(){ go(el); }, 60);
  }
})();
"""


def build_html(data):
    total = total_rendered = total_portable = 0
    chapters = []      # [(idx, theme, sub_name, rel, title, href, href_md, href_portable)]
    groups_toc = []    # [(theme, name, [(idx, title)])]
    seen_theme = None

    theme_order = [t for t, _, _ in THEMES] + (["__other__"] if "__other__" in data else [])
    theme_meta = {t: (name, desc) for t, name, desc in THEMES}
    theme_meta.setdefault("__other__", ("其他", "未分类文档"))

    for theme in theme_order:
        groups = data.get(theme) or {}
        theme_items = []
        for sk in sorted(groups.keys(), key=natural_key):
            for _, fn, rel, title, sub_name in sorted(groups[sk], key=lambda x: x[0]):
                total += 1
                rel_fwd = rel.replace(os.sep, "/")
                rendered = rendered_html_path(rel_fwd)
                port = PORTABLE.get(rel_fwd)
                if rendered:
                    total_rendered += 1
                if port:
                    total_portable += 1
                chapters.append({
                    "idx": total, "theme": theme, "sub": sub_name, "rel": rel_fwd,
                    "title": title, "rendered": rendered, "portable": port,
                })
                theme_items.append((total, title))
        if theme_items:
            groups_toc.append((theme, theme_meta[theme][0], theme_items))

    # ---- 左侧目录大纲 ----
    toc_html = []
    for theme, name, items in groups_toc:
        lis = "\n".join(
            f'        <li><a class="toc-link" href="#ch-{i}">'
            f'<span class="tn">{i:02d}</span>{html.escape(t)}</a></li>'
            for i, t in items)
        toc_html.append(
            f'    <details class="toc-group" open>\n'
            f'      <summary>{html.escape(name)} <span class="cnt">{len(items)} 章</span></summary>\n'
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
            href = rel
        href = urllib.parse.quote(href, safe="/")
        href_md = urllib.parse.quote(rel, safe="/")
        href_portable = None
        if c["portable"]:
            href_portable = urllib.parse.quote(
                os.path.relpath(os.path.join(DOCS_DIR, c["portable"]), OUT_DIR).replace(os.sep, "/"),
                safe="/")

        theme_name = dict((t, n) for t, n, _ in THEMES).get(c["theme"], c["theme"])
        ex = excerpt(os.path.join(ROOT, rel))
        actions = [f'<a class="btn primary" href="{href}" target="_blank" rel="noopener">打开渲染页</a>',
                   f'<a class="btn" href="{href_md}" target="_blank" rel="noopener">原始 .md</a>']
        if href_portable:
            actions.append(
                f'<a class="btn portable" href="{href_portable}" target="_blank" rel="noopener">'
                f'便携版（自包含）</a>')
        if not c["rendered"]:
            actions.insert(0, '<span class="btn" style="color:#656d76;cursor:default">尚未渲染</span>')

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
            f'<span>{html.escape(theme_name)} · {html.escape(c["sub"])}</span></p>\n'
            f'        </div>\n'
            f'      </div>\n'
            + (f'      <p class="ch-excerpt">{ex}</p>\n' if ex else "")
            + '      <div class="ch-actions">\n' + "\n".join("        " + a for a in actions) + "\n      </div>\n"
            + "\n".join(nav) + "\n"
            f'    </section>')

    page = (PAGE
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
    """索引自校验：每条文档链接与便携版链接指向的文件必须真实存在。"""
    bad, total = [], 0
    with open(OUT_FILE, encoding="utf-8") as f:
        text = f.read()
    for tag in ('class="btn primary" href="', 'class="btn portable" href="'):
        for u in re.findall(re.escape(tag) + r'([^"]+)"', text):
            total += 1
            local = urllib.parse.unquote(u).replace("/", os.sep)
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
