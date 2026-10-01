#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描 ai-engineer-journey 仓库里的全部 Markdown 文档，生成一个自包含的 index.html 索引页。
- 按「主题 → 子分组」两级组织，左侧固定导航 + 右侧列表
- **每个条目默认指向「渲染后的 HTML」**（publishing/html/docs/<相对路径>.html），
  由 scripts/build_docs_html.py 批量生成；若某篇还没转换，则自动回退到 .md，不会死链
- 每个条目附一个次级「.md」链接，给想看源码的人
- 纯内联 CSS + 原生 JS，零外部依赖，双击即可离线浏览

用法：
    python3 scripts/gen_doc_index.py
输出：
    publishing/html/index.html
"""
import os, re, html, urllib.parse, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "publishing", "html")
OUT_FILE = os.path.join(OUT_DIR, "index.html")

# 不视为「文档」的目录（缓存/依赖/生成产物的 html）
EXCLUDE_DIRS = {".git", ".workbuddy", "node_modules", "__pycache__",
                ".venv", "venv", "site-packages", ".pytest_cache", ".mypy_cache"}

# 主题定义（顺序即侧栏顺序）。key 为顶层目录名；root 表示仓库根。
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


def rendered_html_path(rel_md):
    """某篇 .md 对应的渲染页路径；未转换则返回 None。

    索引**不写死**「哪几篇已渲染」——那张表一旦有人新增文档就会腐烂。
    改为每次生成时现查 docs/ 里有没有产物，没有就回退到 .md。
    """
    p = os.path.join(DOCS_DIR, rel_md[:-3] + ".html")
    return p if os.path.exists(p) else None

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
    if theme == "projects":
        if len(rel_parts) >= 2:
            return (rel_parts[1], rel_parts[1])
        return ("00", "根")
    if theme == "publishing":
        if len(rel_parts) >= 2:
            return (rel_parts[1], rel_parts[1])
        return ("00", "根")
    # audit / mistakes
    return (rel_parts[0] if rel_parts else theme, rel_parts[0] if rel_parts else theme)

def collect():
    data = {}  # theme -> { subgroup_key: [(sort_key, fname, rel, title)] }
    for theme, _, _ in THEMES:
        data[theme] = {}
    skipped = []
    for dp, dns, fns in os.walk(ROOT):
        # 过滤排除目录
        dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
        for fn in fns:
            if not fn.lower().endswith(".md"):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, ROOT)
            parts = rel.split(os.sep)
            theme = theme_of(parts)
            if theme not in data:
                # 未知顶层目录：归入「其他」
                data.setdefault("__other__", {})
                theme = "__other__"
            sub_key, sub_name = subgroup_of(theme, parts, fn)
            title = first_heading(full) or fn
            data[theme].setdefault(sub_key, []).append(
                (natural_key(rel), fn, rel, title, sub_name))
    return data

def build_html(data):
    total = 0
    total_rendered = 0
    theme_blocks = []
    nav_items = []

    theme_order = [t for t, _, _ in THEMES] + (["__other__"] if "__other__" in data else [])
    theme_meta = {t: (name, desc) for t, name, desc in THEMES}
    theme_meta.setdefault("__other__", ("其他", "未分类文档"))

    for theme in theme_order:
        groups = data.get(theme)
        if not groups:
            continue
        name, desc = theme_meta[theme]
        sec_id = "sec-" + re.sub(r"[^a-z0-9]+", "-", theme.lower())
        # 子组按排序键
        sub_keys = sorted(groups.keys(), key=natural_key)
        groups_html = []
        theme_count = 0
        theme_rendered = 0
        for sk in sub_keys:
            rows = sorted(groups[sk], key=lambda x: x[0])
            rows_html = []
            for _, fn, rel, title, _ in rows:
                total += 1
                theme_count += 1
                rel_fwd = rel.replace(os.sep, "/")
                # 链接相对 index.html 所在目录（publishing/html/），优先指向渲染页
                rendered = rendered_html_path(rel_fwd)
                if rendered:
                    href = urllib.parse.quote(
                        os.path.relpath(rendered, OUT_DIR), safe="/")
                    # 次级 .md 链接要退回仓库根（index 在 publishing/html/ 下）
                    href_md = urllib.parse.quote(
                        os.path.relpath(os.path.join(ROOT, rel_fwd), OUT_DIR), safe="/")
                    extra = (
                        f'<a class="md-link" href="{href_md}"'
                        f'title="原始 Markdown 源文档">.md</a>')
                    theme_rendered += 1
                    total_rendered += 1
                else:
                    href = urllib.parse.quote(rel_fwd, safe="/")
                    extra = '<span class="md-link pending" title="尚未转换，暂显示原文">待转换</span>'
                rows_html.append(
                    f'      <li>\n'
                    f'        <a class="doc" href="{html.escape(href)}">{html.escape(title)}</a>\n'
                    f'        <span class="path">{html.escape(rel)}</span>\n'
                    f'        {extra}\n'
                    f'      </li>')
            gname = rows[0][4]
            groups_html.append(
                f'    <details class="group" open>\n'
                f'      <summary>{html.escape(gname)} <span class="cnt">{len(rows)}</span></summary>\n'
                f'      <ul class="docs">\n' + "\n".join(rows_html) + "\n      </ul>\n"
                f'    </details>')
        theme_blocks.append(
            f'  <section id="{sec_id}">\n'
            f'    <h2>{html.escape(name)} <span class="cnt">{theme_rendered}/{theme_count} 已渲染</span></h2>\n'
            f'    <p class="desc">{html.escape(desc)}</p>\n'
            + "\n".join(groups_html) +
            f'\n  </section>')
        nav_items.append(
            f'      <li><a href="#{sec_id}">{html.escape(name)} '
            f'<span class="cnt">{theme_rendered}/{theme_count}</span></a></li>')

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    nav = "\n".join(nav_items)
    body = "\n".join(theme_blocks)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AI 工程师之旅 · 文档索引</title>
<style>
  :root {{
    --bg:#f7f8fa; --panel:#ffffff; --ink:#1f2328; --muted:#6b7280;
    --line:#e5e7eb; --accent:#2563eb; --accent-soft:#eff6ff; --chip:#eef2f7;
  }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; padding:0; }}
  body {{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    color:var(--ink); background:var(--bg); line-height:1.6;
  }}
  header.top {{
    padding:22px 28px 18px; background:var(--panel); border-bottom:1px solid var(--line);
  }}
  header.top h1 {{ margin:0 0 4px; font-size:22px; }}
  header.top .sub {{ color:var(--muted); font-size:13px; }}
  .toolbar {{ display:flex; gap:12px; align-items:center; margin-top:14px; flex-wrap:wrap; }}
  .toolbar input {{
    flex:1; min-width:220px; padding:9px 12px; border:1px solid var(--line);
    border-radius:8px; font-size:14px; background:#fff; color:var(--ink);
  }}
  .toolbar input:focus {{ outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }}
  .toolbar .meta {{ color:var(--muted); font-size:13px; white-space:nowrap; }}
  .layout {{ display:grid; grid-template-columns:240px 1fr; align-items:start; }}
  nav.side {{
    position:sticky; top:0; align-self:start; height:calc(100vh); overflow:auto;
    background:var(--panel); border-right:1px solid var(--line); padding:18px 14px;
  }}
  nav.side h3 {{ margin:0 0 10px; font-size:12px; letter-spacing:.08em; color:var(--muted); text-transform:uppercase; }}
  nav.side ul {{ list-style:none; margin:0; padding:0; }}
  nav.side li a {{
    display:flex; justify-content:space-between; gap:8px; padding:7px 10px;
    border-radius:7px; color:var(--ink); text-decoration:none; font-size:14px;
  }}
  nav.side li a:hover {{ background:var(--accent-soft); }}
  nav.side li a .cnt {{ color:var(--muted); font-size:12px; }}
  main {{ padding:20px 28px 60px; min-width:0; }}
  section {{ margin-bottom:30px; }}
  section > h2 {{ font-size:18px; margin:0 0 2px; }}
  section > h2 .cnt {{ color:var(--muted); font-size:13px; font-weight:normal; margin-left:6px; }}
  .desc {{ color:var(--muted); font-size:13px; margin:0 0 12px; }}
  details.group {{ border:1px solid var(--line); border-radius:10px; background:var(--panel); margin-bottom:10px; overflow:hidden; }}
  details.group > summary {{
    cursor:pointer; padding:11px 14px; font-weight:600; font-size:14px;
    list-style:none; display:flex; align-items:center; gap:8px; user-select:none;
  }}
  details.group > summary::-webkit-details-marker {{ display:none; }}
  details.group > summary::before {{ content:"▾"; color:var(--muted); font-size:12px; transition:transform .15s; }}
  details.group:not([open]) > summary::before {{ transform:rotate(-90deg); }}
  details.group > summary .cnt {{ color:var(--muted); font-weight:normal; font-size:12px; }}
  ul.docs {{ list-style:none; margin:0; padding:6px 8px 10px; }}
  ul.docs li {{ padding:7px 10px; border-top:1px solid var(--line); display:flex; flex-wrap:wrap; align-items:baseline; gap:8px; }}
  ul.docs li:first-child {{ border-top:none; }}
  a.doc {{ color:var(--accent); text-decoration:none; font-size:14px; font-weight:500; }}
  a.doc:hover {{ text-decoration:underline; }}
  .path {{ color:var(--muted); font-size:12px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
  a.md-link, span.md-link {{ font-size:12px; color:#6b7280; text-decoration:none;
    border:1px solid var(--line); background:#f9fafb; padding:1px 7px; border-radius:999px; white-space:nowrap; }}
  a.md-link:hover {{ background:#eef2f7; color:var(--ink); }}
  .empty {{ color:var(--muted); font-size:14px; padding:30px; text-align:center; }}
  @media (max-width:760px) {{
    .layout {{ grid-template-columns:1fr; }}
    nav.side {{ position:static; height:auto; border-right:none; border-bottom:1px solid var(--line); }}
  }}
</style>
</head>
<body>
<header class="top">
  <h1>AI 工程师之旅 · 文档索引</h1>
  <div class="sub">ai-engineer-journey 仓库全部文档 · 按主题与目录层级组织 · 点击打开<b>渲染后的页面</b>（{total_rendered}/{total} 篇已生成）</div>
  <div class="toolbar">
    <input id="q" type="search" placeholder="过滤文档（按标题或路径，例如 12、rag、微调）…" oninput="filterDocs()"/>
    <span class="meta" id="counter">共 {total} 篇</span>
  </div>
</header>
<div class="layout">
  <nav class="side">
    <h3>主题导航</h3>
    <ul>
{nav}
    </ul>
  </nav>
  <main>
{body}
  </main>
</div>
<script>
function filterDocs() {{
  var q = document.getElementById('q').value.trim().toLowerCase();
  var groups = document.querySelectorAll('details.group');
  var totalShown = 0;
  groups.forEach(function(g) {{
    var rows = g.querySelectorAll('li');
    var shown = 0;
    rows.forEach(function(li) {{
      var txt = li.textContent.toLowerCase();
      var ok = !q || txt.indexOf(q) !== -1;
      li.style.display = ok ? '' : 'none';
      if (ok) shown++;
    }});
    g.style.display = shown ? '' : 'none';
    if (shown) totalShown += shown;
  }});
  document.getElementById('counter').textContent = q
    ? ('匹配 ' + totalShown + ' / ' + {total} + ' 篇')
    : ('共 ' + {total} + ' 篇');
}}
</script>
</body>
</html>'''

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = collect()
    html_out = build_html(data)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"已生成: {OUT_FILE}")
    print(f"文档总数: {html_out.count('class=\"doc\"')}")

if __name__ == "__main__":
    main()
