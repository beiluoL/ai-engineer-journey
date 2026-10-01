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
    python3 scripts/md_to_book_html.py <input.md> <output.html> --relative-images
    python3 scripts/md_to_book_html.py <input.md> <output.html> --rewrite-md-links

两种图片策略（务必按场景选一个）：
- 默认 base64 内嵌：产出「单个文件、可随便拷走」——代价是体积膨胀约 1.33 倍，
  而本仓库 339 张图合计 56.7 MB，全量内嵌会让仓库多出 ~76 MB。只适合少数重点文档。
- --relative-images：图片按相对路径引用。**必须配合「输出目录镜像源目录结构」使用**，
  这样 `assets/x.png` 才在浏览器里真的存在。批量转换 200+ 篇文档一律用这个。

两种链接策略：
- 默认：`.md` 链接原样保留（适合单文件版，接收方是 GitHub 这类 md 渲染器）。
- --rewrite-md-links：把相对链接里的 `.md` 后缀改成 `.html`（含锚点），
  用于「已批量生成 HTML 树」的站点——否则点进去又回到原始 Markdown 文本。

约定：
- 跨文档链接：默认仅映射 KNOWN_MD_TO_HTML 那几张已知文档。
- Mermaid：本仓库只用 flowchart，已为 3 张已知图手绘内联 SVG；未知图降级为可读列表。
"""

import argparse
import base64
import html
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from latex_mathml import render_math  # noqa: E402  构建期 LaTeX → MathML

# 全局转换开关（--relative-images / --rewrite-md-links 时置位）
RELATIVE_IMAGES = False
REWRITE_MD_LINKS = False

# 本次渲染遇到的、暂不认识的 LaTeX 命令（构建结束时会打印，绝不静默吞）
MATH_UNKNOWN: set = set()
MATH_COUNT = 0

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
def rewrite_md_link(url: str) -> str:
    """把相对链接里的 .md 后缀改成 .html（锚点保留）。

    仅在 REWRITE_MD_LINKS 开启时调用。之所以只改「相对」链接：
    外链（http/mailto/data）本就不是文档，页内锚点（#）没有后缀可改。
    """
    frag = ""
    if "#" in url:
        url, frag = url.split("#", 1)
        frag = "#" + frag
    if url.lower().endswith(".md"):
        url = url[:-3] + ".html"
    return url + frag


def link_html(text: str, url: str) -> str:
    raw = url
    base = raw.rsplit("/", 1)[-1]
    if base in KNOWN_MD_TO_HTML:
        raw = raw[: len(raw) - len(base)] + KNOWN_MD_TO_HTML[base]
    # 批量生成 HTML 树时，站内文档链接应指向渲染后的页面
    if REWRITE_MD_LINKS and not raw.startswith(("http", "mailto:", "data:", "#")):
        raw = rewrite_md_link(raw)
    # 外链新窗口打开，站内/相对链接原窗口
    target = ' target="_blank" rel="noopener"' if raw.startswith("http") else ""
    return f'<a href="{raw}"{target}>{text}</a>'


def math_span(body: str, display: bool) -> str:
    """包一层容器：行内跟着正文走，行间独立成块、过长可横滚。"""
    global MATH_COUNT
    MATH_COUNT += 1
    if display:
        return f'<div class="math-block"><math display="block">{body}</math></div>'
    return f'<math class="math-inline">{body}</math>'


def render_inline_math(latex: str) -> str:
    body, unknown = render_math(latex, display=False)
    MATH_UNKNOWN.update(unknown)
    return math_span(body, display=False)


# 行内公式 $...$：开号后不能是空白、闭号前不能是空白（避免把「价格 $5 和 $10」
# 这类连用当公式），且不能与 $$ 抢。转义过的 \$ 不参与匹配。
INLINE_MATH_RE = re.compile(r"(?<![\\$])\$(?![\s$])([^$\n]+?)(?<![\s\\])\$(?!\$)")


def inline(text: str) -> str:
    # 1) 先抽取行内代码，避免内部被转义/加格式
    codes = []

    def coderepl(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", coderepl, text)
    # 1.5) 抽取行内公式。必须在转义之前：LaTeX 里的 \text \mathbb 等反斜杠
    #      一旦先被 html.escape 处理就没了，再想还原得反解实体，极易出错。
    maths = []

    def mathrepl(m):
        maths.append(render_inline_math(m.group(1)))
        return f"\x01{len(maths) - 1}\x01"

    text = INLINE_MATH_RE.sub(mathrepl, text)
    # 2) 转义剩余文本
    text = escape(text)
    # 3) 粗体 / 斜体 —— 必须**早于**链接渲染，否则这里的规则会去改写
    #    链接已经生成的 <a href="..."> 属性本身。踩过的坑：文件名 `_offline_guard.py`
    #    里的下划线被当成斜体标记，href 被改成 "<em>offline</em>guard.py"，链接直接失效。
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # 下划线遵循 CommonMark：夹在字母数字之间的下划线不产生强调
    # （否则 p07_finetune_java_interview.ipynb 这类文件名会被啃掉一半）
    text = re.sub(
        r"(?<![A-Za-z0-9_])_(?=\S)([^\s_]+)_(?![A-Za-z0-9])",
        r"<em>\1</em>",
        text,
    )
    # 4) 链接 [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: link_html(m.group(1), m.group(2)),
        text,
    )
    # 5) 还原代码与公式（公式是已生成的 MathML，直接原样放回，不能再转义）
    def coderest(m):
        idx = int(m.group(1))
        return "<code>" + escape(codes[idx]) + "</code>"

    text = re.sub(r"\x00(\d+)\x00", coderest, text)
    text = re.sub(r"\x01(\d+)\x01", lambda m: maths[int(m.group(1))], text)
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
    if RELATIVE_IMAGES:
        # 相对路径引用：输出目录必须镜像源目录结构，否则图会 404
        return (
            f'<figure class="figure"><img alt="{escape(alt)}" src="{escape(path)}" '
            f'loading="lazy"/>'
            f'<figcaption>{escape(alt)}</figcaption></figure>'
        )
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
    if s == "$$":                      # 行间公式，不能被段落吞掉
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
    """按 | 切单元格；转义的 \\| 与行内公式 $…$ 里的竖线不算分隔符。

    踩过的坑（2026-10-01）：表格里写 $\\mathrm{KL}(p\\|q)$——`\\|` 是 LaTeX 的
    「平行/整除」符号——朴素 split("|") 会把公式拦腰切成两个单元格，
    页面直接露出半截裸 LaTeX（`$\\mathrm{KL}(p\\` + `q) \\neq …$`）。
    """
    s = s.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]

    cells, buf, in_math = [], [], False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            buf.append(s[i:i + 2])          # 连同被转义字符一起原样保留
            i += 2
            continue
        if c == "$":
            in_math = not in_math
        elif c == "|" and not in_math:
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    cells.append("".join(buf))
    return [c.strip() for c in cells]


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

        # 行间公式：本仓库统一写成「独占一行的 $$ 包裹」（140 个标记 = 70 组）
        if line.strip() == "$$":
            buf = []
            i += 1
            while i < n and lines[i].strip() != "$$":
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结束 $$
            latex = "\n".join(buf).strip()
            body, unknown = render_math(latex, display=True)
            MATH_UNKNOWN.update(unknown)
            out.append(math_span(body, display=True))
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


# ---------------------------------------------------------------------------
# 文档式阅读增强：左侧可折叠目录大纲 + 阅读进度条 + 章节链式导航 + 移动端抽屉。
# 同一套交互（进度条、scrollspy、上下章、回到顶部）在 209 篇渲染页里复用。
# ---------------------------------------------------------------------------
EXTRA_CSS = """
.book-side{display:none;}
.book-scrim{display:none;}
.book-fab, .book-top{display:none;}
@media (min-width:1000px){
  .container{margin-left:296px; max-width:1180px; padding:32px 30px 90px;}
  .book-side{
    display:flex; flex-direction:column; position:fixed; left:0; top:0; bottom:0; width:280px;
    background:var(--bg); border-right:1px solid var(--border); z-index:40;
  }
  .book-side-head{
    display:flex; align-items:center; gap:8px; padding:18px 18px 10px;
    font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
  }
  .book-toc{overflow:auto; padding:0 12px 30px; scrollbar-width:thin;}
  .book-toc a{
    display:block; padding:5px 9px; border-radius:6px; color:var(--muted);
    font-size:13px; text-decoration:none; line-height:1.5;
  }
  .book-toc a:hover{background:var(--code-bg); color:var(--accent);}
  .book-toc a.lvl3{padding-left:22px; font-size:12.5px;}
  .book-toc a.active{background:var(--code-bg); color:var(--accent); font-weight:600;}
}
@media (max-width:999px){
  .book-side{
    display:flex; flex-direction:column; position:fixed; left:0; top:0; bottom:0; width:80%;
    max-width:300px; background:var(--bg); border-right:1px solid var(--border); z-index:60;
    transform:translateX(-102%); transition:transform .22s ease;
  }
  .book-side.open{transform:translateX(0);}
  .book-side-head{
    display:flex; align-items:center; gap:8px; padding:16px 18px 10px;
    font-size:13px; font-weight:600; border-bottom:1px solid var(--border);
  }
  .book-side-head button{margin-left:auto; border:none; background:none; cursor:pointer;
    font-size:20px; line-height:1; color:var(--muted);}
  .book-toc{overflow:auto; padding:10px 12px 30px;}
  .book-toc a{display:block; padding:8px 9px; border-radius:6px; color:var(--fg);
    text-decoration:none; font-size:14px;}
  .book-toc a.lvl3{padding-left:22px; font-size:13px;}
  .book-toc a.active{background:var(--code-bg); color:var(--accent); font-weight:600;}
  .book-scrim{display:block; position:fixed; inset:0; background:rgba(31,35,40,.3); z-index:55;}
  .book-scrim.show{display:block;}
  .book-fab{
    display:flex; align-items:center; gap:6px; position:fixed; left:14px; bottom:18px; z-index:50;
    border:1px solid var(--border); background:var(--bg); color:var(--fg);
    border-radius:999px; padding:8px 14px; font-size:13px; cursor:pointer;
    box-shadow:0 4px 16px rgba(31,35,40,.16);
  }
}
/* 章节链式导航（每个章节末尾自动插入） */
.sec-nav{
  display:flex; gap:10px; justify-content:space-between; align-items:stretch;
  margin:1.8em 0 .2em; padding-top:1em; border-top:1px solid var(--border);
}
.sec-nav .sn{
  flex:1 1 0; min-width:0; display:flex; flex-direction:column; gap:2px;
  padding:10px 13px; border:1px solid var(--border); border-radius:10px;
  text-decoration:none; color:var(--fg); background:var(--code-bg);
}
.sec-nav .sn:hover{border-color:var(--accent); text-decoration:none;}
.sec-nav .sn.next{align-items:flex-end; text-align:right;}
.sec-nav .sn-label{color:var(--muted); font-size:11.5px;}
.sec-nav .sn-name{font-size:13.5px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%;}
.sec-nav .sn.empty{opacity:.4; pointer-events:none;}
.book-progress{position:fixed; top:0; left:0; height:3px; width:0; z-index:70;}
.book-top{
  position:fixed; right:18px; bottom:18px; z-index:50; border:1px solid var(--border);
  background:var(--bg); color:var(--muted); border-radius:999px; padding:8px 14px;
  font-size:13px; cursor:pointer; box-shadow:0 4px 16px rgba(31,35,40,.14);
}
.book-top.show{display:block;}

/* 数学公式（构建期已转成 MathML，运行时零依赖、无脚本）
   字体按「本机真实存在」排序：macOS 自带 STIX Two Math，Windows 有 Cambria Math，
   装了 TeX 的 Linux 有 Latin Modern Math。都缺时退回 serif，字形仍有兜底。 */
math{font-family:"STIX Two Math","Latin Modern Math","Cambria Math",
  "STIXGeneral","Times New Roman",serif; font-size:1.04em;}
/* 千万别给 math 写 display:block / inline-block —— 那是踩过的坑：
   单关键字 display 会把内层排版类型打回「普通块流」，MathML 的 math inner
   display 丢失，于是整条公式被竖排成「一行一个符号」，而且元素尺寸非零、
   结构良构，纯结构校验完全发现不了。display="block" 属性已由 UA 样式表
   映射成 `block math`，保持默认即可。 */
math.math-inline{margin:0 .1em;}
/* \text{} 是「正文字类文字」：中文在数学字体里没有字形，必须换回正文栈，
   否则 \text{注意力} 会掉进衬线中文、与周围苹方/黑体对不上。 */
math mtext.tx{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
    "Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
  font-style:normal;
}
/* 行间公式：外层负责居中与横向兜底，math 本体不碰 display（见上方注释） */
.math-block{
  display:block; margin:1.15em 0; padding:.15em .2em;
  overflow-x:auto; overflow-y:hidden;
  text-align:center; scrollbar-width:thin;
}
/* 移动端：公式不缩小到看不清，宁可横向滚动 */
@media (max-width:640px){
  .math-block{font-size:.94em; padding-bottom:.35em;}
  math{font-size:1em;}
}
/* 表格单元格里的公式：单元格可能很窄，允许自身横滚而不是撑破表格 */
td math, th math{font-size:1em;}
"""

EXTRA_JS = """
(function(){
  var side = document.querySelector('.book-side');
  var scrim = document.querySelector('.book-scrim');
  var links = [].slice.call(document.querySelectorAll('.book-toc a'));
  var bar = document.querySelector('.book-progress');
  var topBtn = document.querySelector('.book-top');

  function close(){ side.classList.remove('open'); scrim.classList.remove('show'); }
  document.querySelector('.book-fab').addEventListener('click', function(){
    side.classList.toggle('open'); scrim.classList.toggle('show');
  });
  scrim.addEventListener('click', close);
  var cl = document.querySelector('.book-side-head button');
  if(cl) cl.addEventListener('click', close);
  links.forEach(function(a){ a.addEventListener('click', close); });

  function active(){
    var best = null;
    links.forEach(function(a){
      var el = document.getElementById(a.getAttribute('href').slice(1));
      if(!el) return;
      var r = el.getBoundingClientRect();
      if(r.top <= 140 && (!best || r.top < best.getBoundingClientRect().top)) best = el;
    });
    if(!best) return;
    links.forEach(function(a){
      a.classList.toggle('active', a.getAttribute('href') === '#' + best.id);
    });
  }
  // 行间公式自适应：窄屏上先按容器宽度缩小字号，缩到 9px 仍放不下才交给横向滚动。
  // 不这么做时，长公式（如 DPO 的 J(θ) 全式）在 390px 视口下会是「一屏只看到半条」。
  function fitMath(){
    var MIN = 9;
    [].slice.call(document.querySelectorAll('.math-block')).forEach(function(box){
      var m = box.querySelector('math');
      if(!m) return;
      m.style.fontSize = '';
      var guard = 0;
      while(box.scrollWidth > box.clientWidth + 1 && guard < 30){
        var cur = parseFloat(getComputedStyle(m).fontSize) || 16;
        var next = cur - 0.4;
        if(next < MIN) break;
        m.style.fontSize = next + 'px';
        guard++;
      }
    });
  }
  if(document.fonts && document.fonts.ready) document.fonts.ready.then(fitMath);
  fitMath();
  var rt;
  window.addEventListener('resize', function(){
    clearTimeout(rt); rt = setTimeout(fitMath, 150);
  });

  window.addEventListener('scroll', function(){
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h > 0 ? window.pageYOffset / h : 0;
    bar.style.width = (p * 100).toFixed(2) + '%';
    topBtn.classList.toggle('show', window.pageYOffset > 500);
    active();
  }, {passive:true});
  topBtn.addEventListener('click', function(){
    window.scrollTo({top:0, behavior:'smooth'});
  });
})();
"""

H_TAG_RE = re.compile(r'<h([23])\s+id="([^"]+)">(.*?)</h\1>', re.S)


PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__</title>
<style>/*__CSS__*/</style>
</head>
<body>
<div class="book-progress"></div>
<aside class="book-side">
  <div class="book-side-head">目录大纲<button data-close aria-label="关闭目录">&times;</button></div>
  <nav class="book-toc">/*__TOC__*/</nav>
</aside>
<div class="book-scrim"></div>
<button class="book-fab">☰ 目录</button>
<main class="container">
__BODY__
</main>
<button class="book-top">↑ 顶部</button>
<script>__JS__</script>
</body>
</html>
"""


def outline(body: str):
    """从渲染后的正文里抽出 (level, id, 纯文本) 章节列表，供目录与链式导航共用。"""
    secs = []
    for m in H_TAG_RE.finditer(body):
        text = re.sub(r"<[^>]+>", "", m.group(3))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            secs.append((int(m.group(1)), m.group(2), escape(text)))
    return secs


def _sn_card(kind, label, sec):
    if not sec:
        cls, name = "sn empty", ("文档开头" if kind == "prev" else "文档结尾")
        return f'<span class="{cls}"><span class="sn-label">{label}</span>' \
               f'<span class="sn-name">{name}</span></span>'
    _, sid, name = sec
    return f'<a class="sn {kind}" href="#{sid}"><span class="sn-label">{label}</span>' \
           f'<span class="sn-name">{name}</span></a>'


def inject_section_nav(body: str, secs):
    """把「上一节 / 下一节」卡片插到每个主章节标题后面。

    两个细节：
    * 主层级只取一个（有 h2 就用 h2，否则退化到 h3）——否则每个 h3 小标题后面
      都挂一对卡片，一篇 40 节的小节标题能插出 40 张卡，页面直接废掉；
    * 倒序插入：先插后面的章节，前面章节的查找才不会被插入内容串位。
    """
    if not secs:
        return body
    levels = sorted({lvl for lvl, _, _ in secs})
    main = next((lvl for lvl in (2, 3) if lvl in levels), levels[0])
    order = [i for i, (lvl, _, _) in enumerate(secs) if lvl == main]

    for k in reversed(range(len(order))):
        i = order[k]
        lvl, sid, _ = secs[i]
        tag_end = f'<h{lvl} id="{sid}">'
        pos = body.find(tag_end)
        if pos < 0:
            continue
        end = body.find(f"</h{lvl}>", pos)
        if end < 0:
            continue
        end += len(f"</h{lvl}>")
        prev = secs[order[k - 1]] if k > 0 else None
        nxt = secs[order[k + 1]] if k + 1 < len(order) else None
        nav = ('<nav class="sec-nav">'
               + _sn_card("prev", "← 上一节", prev)
               + _sn_card("next", "下一节 →", nxt)
               + '</nav>')
        body = body[:end] + nav + body[end:]
    return body


def build_page(title: str, body: str) -> str:
    """页模板：正文 + 左侧目录大纲 + 阅读进度 + 章节链式导航 + 回到顶部。"""
    secs = outline(body)
    toc = []
    for lvl, sid, name in secs:
        toc.append(f'<a href="#{sid}" class="lvl{lvl}">{name}</a>')
    toc_html = "".join(toc)
    body = inject_section_nav(body, secs)

    return (PAGE_TMPL.replace("/*__CSS__*/", PAGE_CSS + EXTRA_CSS)
                     .replace("/*__TOC__*/", toc_html)
                     .replace("__BODY__", body)
                     .replace("__TITLE__", escape(title))
                     .replace("__JS__", EXTRA_JS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--title", default=None)
    ap.add_argument("--relative-images", action="store_true",
                    help="图片按相对路径引用（须配合镜像目录结构），而非 base64 内嵌")
    ap.add_argument("--rewrite-md-links", action="store_true",
                    help="把站内 .md 链接改写成 .html")
    args = ap.parse_args()

    globals()["RELATIVE_IMAGES"] = args.relative_images
    globals()["REWRITE_MD_LINKS"] = args.rewrite_md_links

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
    print(f"  公式 {MATH_COUNT} 处（LaTeX → MathML，构建期完成、运行时零依赖）")
    if MATH_UNKNOWN:
        print("  ⚠ 未识别的 LaTeX 命令（已按字面输出）: "
              + ", ".join(sorted(MATH_UNKNOWN)))


if __name__ == "__main__":
    main()
