#!/usr/bin/env python3
"""把本仓库「图文教程」风格的 Markdown 转成对应 HTML。

约定（与 publishing/tutorials/ 保持一致）：
- 第 1 行 # H1 为标题
- 以 > 开头的 blockquote 分两类：
  - > [!NOTE] / [!WARN] / [!GOAL]  → <div class="note|warn|goal">
  - 其他 > ...  → <blockquote>
- ![alt](path) → <figure><img><figcaption>
- ```lang 代码块 → <pre><code class="lang">
- 自动生成目录 .toc（仅 H2）
- 目录与文末导航由脚本拼接，保持 4 套已发布教程风格一致
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

CSS = """  :root { --blue:#3776AB; --yellow:#FFD43B; --ink:#1e293b; --muted:#64748b; --line:#e2e8f0; --bg:#f6f8fa; --green:#2f9e5f; --amber:#b8860b; --purple:#7c5cd6; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink); background:var(--bg); line-height:1.85; }
  .wrap { max-width:880px; margin:0 auto; padding:48px 28px 80px; }
  article { background:#fff; border:1px solid var(--line); border-radius:18px; padding:56px 60px; box-shadow:0 8px 30px rgba(15,23,42,.05); }
  .kicker { display:flex; align-items:center; gap:10px; margin-bottom:18px; }
  .logo-dot { width:34px; height:34px; border-radius:9px; background:linear-gradient(135deg,#2563eb,#1e3a8a); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:15px; }
  .kicker span { font-size:13px; color:var(--muted); font-weight:600; letter-spacing:.5px; }
  h1 { font-size:32px; line-height:1.35; margin-bottom:14px; }
  .meta { font-size:13px; color:var(--muted); padding-bottom:26px; border-bottom:1px solid var(--line); margin-bottom:34px; }
  h2 { font-size:23px; margin:44px 0 16px; padding-left:14px; border-left:4px solid var(--purple); }
  h3 { font-size:17px; margin:26px 0 10px; }
  p { margin-bottom:14px; }
  ul,ol { margin:0 0 14px 22px; } li { margin-bottom:6px; }
  a { color:var(--blue); }
  strong { color:#0f172a; }
  code { font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.88em; background:#eef2f7; border:1px solid #dbe3ec; border-radius:5px; padding:1px 6px; color:#b3541e; }
  pre { background:#16181d; color:#d6dce5; border-radius:12px; padding:18px 20px; overflow-x:auto; margin:18px 0 22px; font-size:13px; line-height:1.7; }
  pre code { background:none; border:none; color:inherit; padding:0; }
  pre .cm { color:#6b7280; } pre .hl { color:#7cd4ff; }
  blockquote { border-left:4px solid var(--yellow); background:#fffbea; padding:12px 18px; border-radius:0 10px 10px 0; margin:18px 0; color:#57534e; }
  blockquote b { color:#92400e; }
  figure { margin:26px 0 30px; text-align:center; }
  figure img { max-width:100%; border:1px solid var(--line); border-radius:12px; box-shadow:0 6px 18px rgba(15,23,42,.08); }
  figcaption { font-size:12.5px; color:var(--muted); margin-top:10px; }
  table { width:100%; border-collapse:collapse; margin:16px 0 24px; font-size:13.5px; }
  th { background:#f1f5f9; text-align:left; }
  th,td { border:1px solid var(--line); padding:9px 13px; }
  tr:nth-child(even) td { background:#fafbfd; }
  .toc { background:#f8fafc; border:1px dashed #cbd5e1; border-radius:12px; padding:18px 24px; margin-bottom:8px; font-size:14px; }
  .toc b { color:var(--purple); }
  .toc ol { margin:8px 0 0 20px; }
  .note { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:12px; padding:14px 20px; font-size:13.5px; color:#14532d; margin-bottom:24px; }
  .warn { background:#fffbea; border:1px solid #fde68a; border-radius:12px; padding:14px 20px; font-size:13.5px; color:#78350f; margin-bottom:24px; }
  .goal { background:#eff6ff; border:1px solid #bfdbfe; border-radius:14px; padding:20px 26px; font-size:15px; }
  .goal .chain { font-family:"SF Mono",Menlo,monospace; font-size:13px; line-height:2; color:#1e3a8a; margin-top:8px; }
  .foot { margin-top:46px; padding-top:20px; border-top:1px solid var(--line); font-size:12.5px; color:var(--muted); }
  .next { display:flex; gap:12px; margin-top:30px; }
  .next a { flex:1; border:1px solid var(--line); border-radius:12px; padding:14px 18px; text-decoration:none; font-size:14px; background:#fafbfd; }
  .next a:hover { border-color:var(--purple); }
  .next .label { display:block; font-size:11.5px; color:var(--muted); margin-bottom:4px; }
  .next a.disabled { color:#94a3b8; pointer-events:none; }
  @media (max-width:640px){ article{padding:32px 22px;} h1{font-size:25px;} }"""

CALLOUT_RE = re.compile(r"^\[!(NOTE|WARN|GOAL)\]\s*(.*)", re.S)
H1_RE = re.compile(r"^# (.+)$")
H2_RE = re.compile(r"^## (.+)$")
H3_RE = re.compile(r"^### (.+)$")
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
CODE_INLINE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def slugify(s: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "-", s).strip("-")[:40]


def inline_md(s: str) -> str:
    s = BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = CODE_INLINE_RE.sub(r"<code>\1</code>", s)
    s = LINK_RE.sub(r'<a href="\2">\1</a>', s)
    return s


def md_para(s: str) -> str:
    """把一行/一段 Markdown 转 HTML（处理 inline 元素）。"""
    # 图片必须先处理，否则 `[alt](path)` 会被当成普通链接
    s = IMG_RE.sub(
        lambda m: (
            f'<figure><img src="{html.escape(m.group(2))}" alt="{html.escape(m.group(1))}">'
            f'<figcaption>{html.escape(m.group(1))}</figcaption></figure>'
        ),
        s,
    )
    s = inline_md(s)
    return s


def render_table(lines: list[str], start: int) -> tuple[str, int]:
    """渲染 Markdown 表格，返回 (html, next_index)。"""
    rows: list[list[str]] = []
    i = start
    while i < len(lines) and lines[i].startswith("|"):
        cells = [c.strip() for c in lines[i].strip().split("|")[1:-1]]
        if cells and not all(re.match(r":?-+:?,*", c) for c in cells):
            rows.append(cells)
        i += 1
    if not rows:
        return "", i
    out = ["<table>"]
    out.append("<tr>" + "".join(f"<th>{inline_md(c)}</th>" for c in rows[0]) + "</tr>")
    for row in rows[1:]:
        out.append("<tr>" + "".join(f"<td>{inline_md(c)}</td>" for c in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out), i


def convert(md_text: str, number: str, series: str, short: str,
            prev_href: str, prev_label: str,
            next_href: str, next_label: str,
            date: str) -> str:
    lines = md_text.splitlines()
    title = "图文教程"
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]

    # 第一遍：收集 H2 目录
    toc: list[tuple[str, str]] = []
    for line in lines:
        if line.startswith("## "):
            h = line[3:].strip()
            toc.append((slugify(h), h))

    body_parts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        blank = line.strip() == ""
        if blank:
            i += 1
            continue

        # H2
        if line.startswith("## "):
            h = line[3:].strip()
            body_parts.append(f'<h2 id="{slugify(h)}">{inline_md(h)}</h2>')
            i += 1
            continue

        # H3
        if line.startswith("### "):
            h = line[4:].strip()
            body_parts.append(f"<h3>{inline_md(h)}</h3>")
            i += 1
            continue

        # blockquote / callout（兼容空行仅 `>` 或 `> `）
        if line.startswith(">"):
            content = [line[1:].lstrip()]
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                content.append(lines[i][1:].lstrip())
                i += 1
            text = "\n".join(content)
            m = CALLOUT_RE.match(text)
            if m:
                cls = m.group(1).lower()
                inner = "\n".join(f"<p>{inline_md(p)}</p>" for p in m.group(2).split("\n\n") if p.strip())
                body_parts.append(f'<div class="{cls}">{inner}</div>')
            else:
                inner = "\n".join(f"<p>{inline_md(p)}</p>" for p in text.split("\n\n") if p.strip())
                body_parts.append(f"<blockquote>{inner}</blockquote>")
            continue

        # fenced code block
        if line.startswith("```"):
            lang = line[3:].strip() or "text"
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code = html.escape("\n".join(code_lines))
            body_parts.append(f'<pre><code class="{html.escape(lang)}">{code}</code></pre>')
            continue

        # table
        if line.startswith("|"):
            table_html, i = render_table(lines, i)
            body_parts.append(table_html)
            continue

        # unordered list
        if line.startswith("- ") or line.startswith("* "):
            items: list[str] = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("* ")):
                items.append(f"<li>{inline_md(lines[i][2:])}</li>")
                i += 1
            body_parts.append(f"<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        # ordered list
        if re.match(r"^\d+\.\s", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                text = re.sub(r"^\d+\.\s", "", lines[i])
                items.append(f"<li>{inline_md(text)}</li>")
                i += 1
            body_parts.append(f"<ol>\n" + "\n".join(items) + "\n</ol>")
            continue

        # plain paragraph (possibly containing images inline)
        rendered = md_para(line)
        if rendered.startswith("<figure>") and rendered.endswith("</figure>"):
            body_parts.append(rendered)
        else:
            body_parts.append(f"<p>{rendered}</p>")
        i += 1

    body = "\n".join(body_parts)

    toc_html = ""
    if toc:
        toc_html = '<div class="toc"><b>目录</b><ol>' + "".join(
            f'<li><a href="#{slug}">{html.escape(h)}</a></li>' for slug, h in toc
        ) + "</ol></div>"

    prev_cls = " disabled" if prev_href == "#" else ""
    next_cls = " disabled" if next_href == "#" else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — AI Engineer Journey 图文教程</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">
<article>
  <div class="kicker"><div class="logo-dot">AI</div><span>AI ENGINEER JOURNEY · 图文教程 {html.escape(number)} · {html.escape(series)}</span></div>
  <h1>{html.escape(title)}</h1>
  <div class="meta">最后更新：{html.escape(date)} · 本文同步发表于 <a href="https://github.com/beiluoL/ai-engineer-journey">github.com/beiluoL/ai-engineer-journey</a></div>
  {toc_html}
{body}
  <div class="foot">
    转载请注明来源。技术栈与版本号请以实际下载时官方文档为准。
  </div>
  <div class="next">
    <a href="{html.escape(prev_href)}" class="{prev_cls.strip()}"><span class="label">上一篇</span>{html.escape(prev_label)}</a>
    <a href="{html.escape(next_href)}" class="{next_cls.strip()}"><span class="label">下一篇</span>{html.escape(next_label)}</a>
  </div>
</article>
</div>
</body>
</html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", help="输入 Markdown 文件")
    ap.add_argument("--out", required=True, help="输出 HTML 文件")
    ap.add_argument("--number", default="05", help="教程编号")
    ap.add_argument("--series", default="大模型微调实战", help="系列名")
    ap.add_argument("--short", default="微调入门", help="短标签")
    ap.add_argument("--prev-href", default="#", help="上一篇链接")
    ap.add_argument("--prev-label", default="—", help="上一篇标题")
    ap.add_argument("--next-href", default="#", help="下一篇链接")
    ap.add_argument("--next-label", default="—", help="下一篇标题")
    ap.add_argument("--date", default="2026-09-26", help="更新日期")
    args = ap.parse_args()

    md_text = Path(args.md).read_text(encoding="utf-8")
    html_text = convert(
        md_text, args.number, args.series, args.short,
        args.prev_href, args.prev_label,
        args.next_href, args.next_label,
        args.date,
    )
    Path(args.out).write_text(html_text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
