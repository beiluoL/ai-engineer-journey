#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_to_book_html.py —— 把仓库里的图文教程 Markdown 转换成「自包含」的 HTML。

设计目标（对应需求）：
1. 每个输出的 .html 都是单个文件、零外部依赖（CSS 内联、图片 base64 内嵌、Mermaid 图改画成内联 SVG）。
2. 双击即可在浏览器打开，无需起服务器、无需联网（外链 GitHub 除外，那是超链接不是依赖）。
3. 保留原文档的标题层级 / 段落 / 列表 / 表格 / 引用 / 代码块结构。
4. 多个 HTML 文件可由一个主 index.html 打开（脚本只负责单文件；index 另外手写）。

用法：
    python3 scripts/md_to_book_html.py <input.md> <output.html> [--title 标题]

约定：
- 图片：相对路径解析到 input.md 同目录，转 base64 内嵌。
- 跨文档链接：若指向 07-延伸阅读.md / 12-tutorials-and-agent.md，改为同目录 .html。
- Mermaid：本仓库只用 flowchart，已为 3 张已知图手绘内联 SVG；未知图降级为可读列表。
"""

import argparse
import base64
import html
import os
import re
from html.parser import HTMLParser

KNOWN_MD_TO_HTML = {
    "python-practice/07-延伸阅读.md": "07-延伸阅读.html",
    "llm-fundamentals/12-tutorials-and-agent.md": "12-tutorials-and-agent.html",
    "07-延伸阅读.md": "07-延伸阅读.html",
    "12-tutorials-and-agent.md": "12-tutorials-and-agent.html",
}


# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------
def escape(text: str) -> str:
    return html.escape(text, quote=True)


def slug(text: str) -> str:
    """尽量贴近 GitHub 的标题锚点规则：小写、去标点、空格转连字符、保留中文。"""
    t = re.sub(r"[*`_]+", "", text)
    out = []
    for ch in t:
        if ch == " ":
            out.append("-")
        elif re.match(r"[\w一-鿿]", ch):
            out.append(ch.lower())
        # 其它标点（。、（）：「」【】等）直接丢弃
    s = "".join(out)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


# ----------------------------------------------------------------------------
# 行内元素：代码 / 链接 / 粗体 / 斜体
# ----------------------------------------------------------------------------
def link_html(text: str, url: str) -> str:
    raw = url
    base = raw.rsplit("/", 1)[-1]
    if base in KNOWN_MD_TO_HTML:
        raw = raw[: len(raw) - len(base)] + KNOWN_MD_TO_HTML[base]
    # 外链新窗口打开，站内/相对链接原窗口
    target = ' target="_blank" rel="noopener"' if raw.startswith("http") else ""
    return f'<a href="{raw}"{target}>{text}</a>'


def inline(text: str) -> str:
    # 1) 先抽取行内代码，避免内部被转义/加格式
    codes = []

    def coderepl(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", coderepl, text)
    # 2) 转义剩余文本
    text = escape(text)
    # 3) 链接 [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: link_html(m.group(1), m.group(2)),
        text,
    )
    # 4) 粗体 / 斜体
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", text)
    # 5) 还原代码
    def coderest(m):
        idx = int(m.group(1))
        return "<code>" + escape(codes[idx]) + "</code>"

    text = re.sub(r"\x00(\d+)\x00", coderest, text)
    return text


# ----------------------------------------------------------------------------
# 列表（支持多级嵌套，按缩进建树）
# ----------------------------------------------------------------------------
def render_list(items):
    root = {"ordered": False, "html": "", "children": []}
    stack = [(-1, root)]
    for indent, ordered, content in items:
        node = {"ordered": ordered, "html": inline(" ".join(content)), "children": []}
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        parent["children"].append(node)
        stack.append((indent, node))

    def to_html(node):
        if not node["children"]:
            return ""
        tag = "ol" if node["ordered"] else "ul"
        inner = ""
        for ch in node["children"]:
            inner += "<li>" + ch["html"]
            if ch["children"]:
                inner += to_html(ch)
            inner += "</li>"
        return f'<{tag} class="lvl">{inner}</{tag}>'

    return to_html(root)


# ----------------------------------------------------------------------------
# Mermaid -> 内联 SVG（仅支持本仓库出现过的 flowchart 子集）
# ----------------------------------------------------------------------------
SVG_73 = '''<svg viewBox="0 0 640 380" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="读生产代码四阶梯">
  <defs>
    <marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L7,3 L0,6 Z" fill="#57606a"/></marker>
    <marker id="dot" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L7,3 L0,6 Z" fill="none" stroke="#57606a" stroke-width="1"/></marker>
  </defs>
  <g font-family="sans-serif" font-size="13">
    <rect x="30" y="20" width="270" height="64" rx="8" fill="#e1f5ee" stroke="#0f6e56"/>
    <text fill="#085041" text-anchor="middle"><tspan x="165" y="46">① 读完一个「小」库</tspan><tspan x="165" y="66">先建立「我能读完一个库」的信心</tspan></text>
    <rect x="30" y="110" width="270" height="64" rx="8" fill="#e1f5ee" stroke="#0f6e56"/>
    <text fill="#085041" text-anchor="middle"><tspan x="165" y="136">② 读数据 / 校验层</tspan><tspan x="165" y="156">学一个包怎么被组织起来</tspan></text>
    <rect x="30" y="200" width="270" height="64" rx="8" fill="#e6f1fb" stroke="#185fa5"/>
    <text fill="#0c447c" text-anchor="middle"><tspan x="165" y="226">③ 读 Web 框架骨架</tspan><tspan x="165" y="246">学路由、上下文、依赖注入</tspan></text>
    <rect x="30" y="290" width="270" height="64" rx="8" fill="#e6f1fb" stroke="#185fa5"/>
    <text fill="#0c447c" text-anchor="middle"><tspan x="165" y="316">④ 读大型系统</tspan><tspan x="165" y="336">学分层、并发、分布式协作</tspan></text>
    <rect x="360" y="30" width="250" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="485" y="57" fill="#1f2328" text-anchor="middle">httpx</text>
    <rect x="360" y="120" width="250" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="485" y="147" fill="#1f2328" text-anchor="middle">pydantic · kedro</text>
    <rect x="360" y="210" width="250" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="485" y="237" fill="#1f2328" text-anchor="middle">flask · fastapi</text>
    <rect x="360" y="300" width="250" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="485" y="327" fill="#1f2328" text-anchor="middle">superset · sentry · prefect</text>
    <line x1="165" y1="84" x2="165" y2="110" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="165" y1="174" x2="165" y2="200" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="165" y1="264" x2="165" y2="290" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="300" y1="52" x2="360" y2="52" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot)"/>
    <line x1="300" y1="142" x2="360" y2="142" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot)"/>
    <line x1="300" y1="232" x2="360" y2="232" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot)"/>
    <line x1="300" y1="322" x2="360" y2="322" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot)"/>
  </g>
</svg>'''

SVG_121 = '''<svg viewBox="0 0 760 250" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="学、调、造三张地图">
  <defs>
    <marker id="arr2" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L7,3 L0,6 Z" fill="#57606a"/></marker>
    <marker id="dot2" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L7,3 L0,6 Z" fill="none" stroke="#57606a" stroke-width="1"/></marker>
  </defs>
  <g font-family="sans-serif" font-size="13">
    <rect x="20" y="90" width="150" height="56" rx="8" fill="#f1efe8" stroke="#5f5e5a"/>
    <text x="95" y="123" fill="#2c2c2a" text-anchor="middle">你现在的位置</text>
    <rect x="210" y="90" width="150" height="56" rx="8" fill="#e1f5ee" stroke="#0f6e56"/>
    <text x="285" y="116" fill="#085041" text-anchor="middle">① 学</text><text x="285" y="134" fill="#085041" text-anchor="middle">把原理搞明白</text>
    <rect x="400" y="90" width="150" height="56" rx="8" fill="#e6f1fb" stroke="#185fa5"/>
    <text x="475" y="116" fill="#0c447c" text-anchor="middle">② 调</text><text x="475" y="134" fill="#0c447c" text-anchor="middle">把模型变你的</text>
    <rect x="590" y="90" width="150" height="56" rx="8" fill="#faeeda" stroke="#854f0b"/>
    <text x="665" y="116" fill="#412402" text-anchor="middle">③ 造</text><text x="665" y="134" fill="#412402" text-anchor="middle">变成产品</text>
    <rect x="210" y="170" width="150" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="285" y="197" fill="#1f2328" text-anchor="middle">12.2 教程与课程</text>
    <rect x="400" y="170" width="150" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="475" y="197" fill="#1f2328" text-anchor="middle">12.3 微调框架</text>
    <rect x="590" y="170" width="150" height="44" rx="6" fill="#f6f8fa" stroke="#d0d7de"/>
    <text x="665" y="197" fill="#1f2328" text-anchor="middle">12.4 Agent 开发</text>
    <line x1="170" y1="118" x2="210" y2="118" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr2)"/>
    <line x1="360" y1="118" x2="400" y2="118" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr2)"/>
    <line x1="550" y1="118" x2="590" y2="118" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr2)"/>
    <line x1="285" y1="146" x2="285" y2="170" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot2)"/>
    <line x1="475" y1="146" x2="475" y2="170" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot2)"/>
    <line x1="665" y1="146" x2="665" y2="170" stroke="#57606a" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#dot2)"/>
  </g>
</svg>'''

SVG_1246 = '''<svg viewBox="0 0 880 370" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Agent 框架怎么选">
  <defs>
    <marker id="arr3" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L7,3 L0,6 Z" fill="#57606a"/></marker>
  </defs>
  <g font-family="sans-serif" font-size="13">
    <rect x="330" y="10" width="180" height="44" rx="8" fill="#f1efe8" stroke="#5f5e5a"/>
    <text x="420" y="37" fill="#2c2c2a" text-anchor="middle">我要做 Agent</text>
    <rect x="300" y="80" width="240" height="46" rx="8" fill="#fff" stroke="#57606a"/>
    <text x="420" y="107" fill="#1f2328" text-anchor="middle">我要的是能上生产的编排？</text>
    <line x1="420" y1="54" x2="420" y2="80" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr3)"/>
    <rect x="40" y="150" width="250" height="50" rx="8" fill="#e6f1fb" stroke="#185fa5"/>
    <text x="165" y="170" fill="#0c447c" text-anchor="middle">LangGraph</text><text x="165" y="188" fill="#0c447c" text-anchor="middle">状态图 + 检查点 + 人工介入</text>
    <text x="270" y="100" fill="#57606a" font-size="12">是</text>
    <line x1="300" y1="103" x2="290" y2="165" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr3)"/>
    <rect x="470" y="150" width="240" height="46" rx="8" fill="#fff" stroke="#57606a"/>
    <text x="590" y="177" fill="#1f2328" text-anchor="middle">我要的是最快出原型？</text>
    <text x="455" y="100" fill="#57606a" font-size="12">否</text>
    <line x1="540" y1="103" x2="590" y2="150" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr3)"/>
    <rect x="420" y="224" width="260" height="50" rx="8" fill="#faeeda" stroke="#854f0b"/>
    <text x="550" y="244" fill="#412402" text-anchor="middle">CrewAI（多角色）</text><text x="550" y="262" fill="#412402" text-anchor="middle">或 Dify（不写代码）</text>
    <text x="585" y="200" fill="#57606a" font-size="12">是</text>
    <line x1="590" y1="196" x2="550" y2="224" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr3)"/>
    <rect x="650" y="224" width="210" height="46" rx="8" fill="#fff" stroke="#57606a"/>
    <text x="755" y="251" fill="#1f2328" text-anchor="middle">我要的是先搞懂原理？</text>
    <text x="700" y="200" fill="#57606a" font-size="12">否</text>
    <line x1="710" y1="173" x2="755" y2="224" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr3)"/>
    <rect x="600" y="298" width="270" height="50" rx="8" fill="#e1f5ee" stroke="#0f6e56"/>
    <text x="735" y="318" fill="#085041" text-anchor="middle">先读 smolagents 源码</text><text x="735" y="336" fill="#085041" text-anchor="middle">再去 projects/05 跑 MCP</text>
    <text x="755" y="274" fill="#57606a" font-size="12">是</text>
    <line x1="755" y1="270" x2="735" y2="298" stroke="#57606a" stroke-width="1.5" marker-end="url(#arr3)"/>
  </g>
</svg>'''


def mermaid_svg(src: str) -> str:
    s = src
    if "S1" in s and "S2" in s and "S4" in s and ("TD" in s or "TB" in s):
        return '<div class="mermaid-svg">' + SVG_73 + "</div>"
    if "Q1" in s and "R1" in s and "R2" in s and "R3" in s:
        return '<div class="mermaid-svg">' + SVG_1246 + "</div>"
    if "你现在的位置" in s:
        return '<div class="mermaid-svg">' + SVG_121 + "</div>"
    # 未知图：降级为可读列表
    nodes = re.findall(r"(\w+)\s*(?:\[\"([^\"]*)\"\]|\[([^\]]*)\])", s)
    items = []
    for nid, a, b in nodes:
        label = (a or b or nid).replace("<br/>", " ")
        items.append(f"<li><code>{nid}</code> — {inline(label)}</li>")
    return '<div class="mermaid-fallback"><p>流程图（简化）：</p><ul>' + "".join(items) + "</ul></div>"


# ----------------------------------------------------------------------------
# 图片：读取并 base64 内嵌
# ----------------------------------------------------------------------------
def embed_image(alt: str, path: str, base_dir: str) -> str:
    p = path
    if not os.path.isabs(p):
        p = os.path.join(base_dir, p)
    try:
        with open(p, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return (
            f'<figure class="figure"><img alt="{escape(alt)}" '
            f'src="data:image/png;base64,{data}"/>'
            f'<figcaption>{escape(alt)}</figcaption></figure>'
        )
    except OSError:
        return f'<p class="img-missing">[图片缺失：{escape(path)}]</p>'


# ----------------------------------------------------------------------------
# 块级解析
# ----------------------------------------------------------------------------
def is_block_start(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("```"):
        return True
    if re.match(r"^#{1,6}\s", line):
        return True
    if re.match(r"^---+\s*$", line):
        return True
    if s.startswith(">"):
        return True
    if re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
        return True
    return False


def split_row(s: str):
    s = s.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_table(lines, i, n):
    """lines[i] 为表头行，lines[i+1] 为分隔行；返回 (html, next_i)。"""
    header = split_row(lines[i])
    i += 2
    rows = []
    while i < n and lines[i].strip().startswith("|") and "|" in lines[i]:
        rows.append(split_row(lines[i]))
        i += 1
    thead = "<tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr>"
    tbody = "".join(
        "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>", i


def md_to_html(md_text: str, base_dir: str) -> str:
    lines = md_text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 代码块 / Mermaid
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结束 ```
            code = "\n".join(buf)
            if lang == "mermaid":
                out.append(mermaid_svg(code))
            else:
                out.append(f"<pre><code>{escape(code)}</code></pre>")
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            out.append(f'<h{level} id="{slug(text)}">{inline(text)}</h{level}>')
            i += 1
            continue

        # 分隔线
        if re.match(r"^---+\s*$", line):
            out.append("<hr/>")
            i += 1
            continue

        # GFM 表格：当前行含 | 且下一行是分隔行
        if (
            "|" in line
            and i + 1 < n
            and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]+\|?\s*$", lines[i + 1])
        ):
            tbl, i = parse_table(lines, i, n)
            out.append(tbl)
            continue

        # 独立图片行
        im = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if im:
            out.append(embed_image(im.group(1), im.group(2), base_dir))
            i += 1
            continue

        # 引用块
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip())
                i += 1
            # 多个 "> " 空行分隔的段落
            paras = "\n".join(buf).split("\n\n")
            inner = "".join(
                f"<p>{inline(p.replace(chr(10), ' '))}</p>" for p in paras if p.strip()
            )
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # 列表
        if re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            items = []
            base_indent = None
            while i < n:
                l = lines[i]
                lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", l)
                if lm:
                    indent = len(lm.group(1))
                    ordered = lm.group(2) not in ("-", "*")
                    if base_indent is None:
                        base_indent = indent
                    items.append([indent, ordered, [lm.group(3)]])
                    i += 1
                elif l.strip() and l[:1].isspace() and items:
                    items[-1][2].append(l.strip())
                    i += 1
                else:
                    break
            out.append(render_list(items))
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 段落：聚合到下一个块起点
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not is_block_start(lines[i]):
            buf.append(lines[i])
            i += 1
        text = " ".join(x.strip() for x in buf)
        cls = ' class="nav-footer"' if ("[" in text and ("返回" in text or "←" in text)) else ""
        out.append(f"<p{cls}>{inline(text)}</p>")

    return "\n".join(out)


# ----------------------------------------------------------------------------
# 包裹成完整 HTML
# ----------------------------------------------------------------------------
PAGE_CSS = """
:root{
  --bg:#ffffff; --fg:#1f2328; --muted:#57606a; --accent:#0969da;
  --code-bg:#f6f8fa; --border:#d0d7de; --quote-bg:#f6f8fa;
  --table-alt:rgba(0,0,0,.025);
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0d1117; --fg:#e6edf3; --muted:#9da7b3; --accent:#4493f8;
    --code-bg:#161b22; --border:#30363d; --quote-bg:#161b22;
    --table-alt:rgba(255,255,255,.03);
  }
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.container{max-width:900px; margin:0 auto; padding:36px 22px 90px;}
h1,h2,h3,h4{line-height:1.3; margin-top:1.9em; scroll-margin-top:18px;}
h1{font-size:1.9em; border-bottom:1px solid var(--border); padding-bottom:.35em;}
h2{font-size:1.45em; border-bottom:1px solid var(--border); padding-bottom:.28em;}
h3{font-size:1.18em;}
h4{font-size:1.04em; color:var(--muted);}
a{color:var(--accent); text-decoration:none;}
a:hover{text-decoration:underline;}
code{background:var(--code-bg); padding:.15em .42em; border-radius:4px;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.86em;}
pre{background:var(--code-bg); padding:14px 16px; border-radius:8px; overflow:auto;}
pre code{background:none; padding:0; font-size:.85em;}
table{border-collapse:collapse; width:100%; margin:1.2em 0; font-size:.92em;}
th,td{border:1px solid var(--border); padding:8px 10px; text-align:left; vertical-align:top;}
th{background:var(--code-bg); font-weight:600;}
tbody tr:nth-child(2n){background:var(--table-alt);}
blockquote{border-left:4px solid var(--border); margin:1.1em 0; padding:.3em 1em;
  color:var(--muted); background:var(--quote-bg); border-radius:0 6px 6px 0;}
blockquote p{margin:.4em 0;}
.figure{margin:1.6em 0; text-align:center;}
.figure img{max-width:100%; border:1px solid var(--border); border-radius:8px; background:#fff;}
.figure figcaption{color:var(--muted); font-size:.85em; margin-top:.6em;}
.mermaid-svg{margin:1.6em 0; text-align:center;}
.mermaid-svg svg{max-width:100%; height:auto;}
.mermaid-fallback{margin:1.2em 0; padding:.8em 1em; border:1px dashed var(--border); border-radius:8px;}
hr{border:none; border-top:1px solid var(--border); margin:2.2em 0;}
ul.lvl, ol.lvl{margin:.6em 0; padding-left:1.6em;}
li{margin:.3em 0;}
.nav-footer{margin-top:2.2em; padding-top:1em; border-top:1px solid var(--border);
  color:var(--muted); font-size:.92em;}
.img-missing{color:#b35900; font-weight:600;}
""".strip()


def build_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<main class="container">
{body}
</main>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        md_text = f.read()
    base_dir = os.path.dirname(os.path.abspath(args.input))
    body = md_to_html(md_text, base_dir)

    # 取首个一级标题作默认标题
    m = re.search(r"^#\s+(.*)$", md_text, re.M)
    title = args.title or (m.group(1).strip() if m else os.path.basename(args.input))
    page = build_page(title, body)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"written: {args.output}  ({len(page)} bytes)")


if __name__ == "__main__":
    main()
