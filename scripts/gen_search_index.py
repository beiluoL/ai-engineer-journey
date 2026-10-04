#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建期生成**全站全文搜索索引** publishing/html/search-data.js。

为什么要它：索引页原本只能按「标题 / 路径」过滤（`data-k`），200+ 篇文档的
**正文一个字都搜不到**。读完几篇之后想回头找「某个概念在哪一篇讲过」，
只能靠猜标题——这是这个站点最大的功能缺口。

为什么是「构建期索引 + 纯前端检索」：

  * 站点必须**零后端、零外部依赖、双击即开**（`file://`），
    所以不能引搜索服务，也不能引 CDN 上的 lunr/MiniSearch；
  * `file://` 下 `fetch()` 读本地 JSON 会被 CORS 拦掉，
    索引只能做成 **`window.xxx = {...}` 的 JS 文件**，用 `<script src>` 注入
    （跟 JSONP 一个道理）。这是本方案最硬的一条约束；
  * 语料很小（200+ 篇、正文约 0.7 MB），一次性全部装进浏览器完全可行，
    不需要任何分片 / 懒加载技巧。

索引的粒度是**节**（h1–h3 标题 + 其下正文），不是篇也不是段落：
  * 比「篇」细 → 搜索结果能直接落到具体小节（`docs/x.html#<slug>`）；
  * 比「段落」粗 → 数据量小、片段上下文完整。

两个「必须复用、绝不允许各写一份」的地方：
  1. 文档清单与章节号来自 `gen_doc_index.ordered_docs()`（全站唯一排序口径）；
  2. 小节锚点来自 `md_to_book_html.slug()`（渲染页的 `<h2 id=...>` 就是它生成的）。
     自己抄一份 slug 规则 → 渲染器一改，搜索就跳到空白处。

用法：
    python3 scripts/gen_search_index.py [--stats]
输出：
    publishing/html/search-data.js
"""
import argparse
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_doc_index as idx        # noqa: E402  唯一排序口径
import md_to_book_html as book     # noqa: E402  slug() 与渲染页共用

OUT_FILE = os.path.join(idx.OUT_DIR, "search-data.js")

FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
IMG_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
TEXT_MATH_RE = re.compile(r"\\text\{([^{}]*)\}")
BLOCK_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
INLINE_MATH_RE = re.compile(r"\$([^$\n]+)\$")

# 单节正文上限：某篇若整文没有小标题（整篇一节），不设限会把整篇塞进一条记录，
# 前端高亮片段时无从定位。截断只影响「搜索召回」，展示与跳转都不受影响。
MAX_SEC_CHARS = 4000


def clean_math(s: str) -> str:
    """把公式换成它能贡献的**可读文本**，其余丢弃。

    直接留着 `\\operatorname{softmax}` 没有意义（没人会搜反斜杠命令），
    但 `\\text{连续提升}`、`\\text{dropout}` 里的中文/英文是真正能搜的内容。
    """
    def repl(m):
        texts = TEXT_MATH_RE.findall(m.group(1))
        return " ".join(texts) if texts else " "

    s = BLOCK_MATH_RE.sub(repl, s)
    return INLINE_MATH_RE.sub(repl, s)


def clean_inline(s: str) -> str:
    """剥掉行内 Markdown 标记，只留「人会读到的字」。"""
    s = IMG_RE.sub(r"\1", s)
    s = LINK_RE.sub(r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", s)
    s = re.sub(r"~~([^~]+)~~", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", s)   # 列表项
    s = re.sub(r"^\s*>\s?", "", s)                 # 引用
    s = re.sub(r"^\s*\|", "", s)
    s = s.replace("|", " ")
    return s


def is_noise(s: str) -> bool:
    """表格分隔行 / 纯分隔线 / 纯符号行 —— 不进索引。"""
    t = s.strip()
    if not t:
        return True
    if not re.sub(r"[\s\-|:+*]+", "", t):
        return True
    return False


def sections_of(md_text: str, fallback_title: str):
    """把一篇 Markdown 切成 [(anchor, head, text)]。

    anchor 用渲染页同一套 `slug()` 算，保证 `docs/x.html#anchor` 一定命中。
    代码块**保留**（能搜到 API / 函数名），但会与正文拼在同一段文本里，
    前端打分时再降权。
    """
    secs, cur = [], {"anchor": "", "head": fallback_title, "parts": []}
    in_fence, fence = False, []
    for raw in md_text.split("\n"):
        if FENCE_RE.match(raw):
            if in_fence:
                cur["parts"].append(("c", "\n".join(fence)))
                fence, in_fence = [], False
            else:
                in_fence = True
            continue
        if in_fence:
            fence.append(raw)
            continue

        m = HEAD_RE.match(raw)
        if m:
            level, raw_head = len(m.group(1)), m.group(2).strip()
            # 锚点必须用**原始标题文本**过 slug()——渲染页就是这么算的：
            #   f'<h{level} id="{slug(text)}">'  ← text = m.group(2).strip()
            anchor = book.slug(raw_head)
            head = re.sub(r"\s+", " ", clean_math(clean_inline(raw_head))).strip()
            head = re.sub(r"[*`_]", "", head).strip()
            if level <= 3 and head:
                secs.append(cur)
                cur = {"anchor": anchor, "head": head, "parts": []}
                continue
            if head:
                cur["parts"].append(("h", head))
            continue

        if is_noise(raw):
            continue
        cur["parts"].append(("p", raw))
    secs.append(cur)

    out = []
    for sc in secs:
        buf = []
        for kind, text in sc["parts"]:
            if kind == "c":
                buf.append(text)
            else:
                buf.append(clean_math(clean_inline(text)))
        joined = re.sub(r"[ \t]+", " ", " ".join(buf))
        joined = re.sub(r"\s*\n\s*", " ", joined).strip()
        out.append((sc["anchor"], sc["head"], joined[:MAX_SEC_CHARS]))
    return out


def build():
    docs = idx.ordered_docs()
    doc_rows, sec_rows = [], []
    stats = {"docs": 0, "secs": 0, "chars": 0, "missing": 0}

    for c in docs:
        rel = c["rel"]
        path = os.path.join(idx.ROOT, rel)
        if not os.path.exists(path):
            stats["missing"] += 1
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            md_text = f.read()

        if c["rendered"]:
            url = os.path.relpath(c["rendered"], idx.OUT_DIR).replace(os.sep, "/")
            url = urllib.parse.quote(url, safe="/")
        else:
            # 没渲染页的文档：回退到总览页对应章节，绝不产生死链
            url = "#ch-%d" % c["idx"]
        doc_rows.append([rel, c["title"], url, c["idx"]])
        di = len(doc_rows) - 1

        for anchor, head, text in sections_of(md_text, c["title"]):
            if not head and len(text) < 2:
                continue
            sec_rows.append([di, anchor, head, text])
            stats["chars"] += len(text)
        stats["docs"] += 1

    return {"v": 1, "docs": doc_rows, "secs": sec_rows}, stats


def emit(payload) -> str:
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 三条转义都关系到「脚本能否被解析」，不是洁癖：
    #   </      → 若将来改成内联 <script>，会提前闭合元素
    #   U+2028/9 → 是合法 JSON 字符，但在 JS 里是行终止符，直接语法错误
    js = js.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    banner = ("/* 自动生成，请勿手改。来源：scripts/gen_search_index.py\n"
              "   全站全文搜索索引：docs=[篇目, 标题, 链接, 章节号]，\n"
              "   secs=[篇号, 锚点, 节标题, 正文]。\n"
              "   用 <script src> 注入（file:// 下 fetch 读不了本地 JSON）。 */\n")
    return banner + "window.__SEARCH__=" + js + ";\n"


def verify(payload):
    """自检：索引里每条 `docs/x.html#anchor` 都必须真的落地。

    这一步不能省。锚点是用 `slug()` 复算出来的，一旦渲染器的 id 生成规则变了、
    或某篇没被渲染，搜索就会「点进去停在页面顶部」——**页面不报错，只是不对**，
    这种静默失败只有全量比对才抓得到。
    """
    from collections import defaultdict

    docs = payload["docs"]
    bad_url, bad_anchor, checked = [], [], 0

    path_of = {}
    for di, (_rel, _title, url, _idx) in enumerate(docs):
        if url.startswith("#"):
            path_of[di] = None
            continue
        path = os.path.join(idx.OUT_DIR, urllib.parse.unquote(url))
        if os.path.exists(path):
            path_of[di] = path
        else:
            bad_url.append(url)
            path_of[di] = None

    by_doc = defaultdict(list)
    for di, anchor, _head, _text in payload["secs"]:
        if anchor:
            by_doc[di].append(anchor)

    for di, anchors in by_doc.items():
        path = path_of.get(di)
        if not path:
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            ids = set(re.findall(r'id="([^"]+)"', f.read()))
        for a in anchors:
            checked += 1
            if a not in ids:
                bad_anchor.append((docs[di][0], a))
    return bad_url, bad_anchor, checked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="打印索引统计")
    ap.add_argument("--verify", action="store_true",
                    help="全量校验每个锚点都能在渲染页里命中（失败退出码非 0）")
    args = ap.parse_args()

    payload, stats = build()
    text = emit(payload)
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    size = len(text.encode("utf-8"))
    print(f"written: {os.path.relpath(OUT_FILE, idx.ROOT)}  ({size / 1048576:.2f} MB)")
    if args.stats:
        print(f"  篇 {stats['docs']} · 节 {len(payload['secs'])} · "
              f"正文 {stats['chars'] / 1048576:.2f} MB 字符")
        if stats["missing"]:
            print(f"  ⚠ 源文件缺失 {stats['missing']} 篇（已跳过）")

    if args.verify:
        bad_url, bad_anchor, checked = verify(payload)
        print(f"  校验：{len(payload['docs'])} 篇链接 · {checked} 个小节锚点")
        if bad_url:
            print(f"  ✗ 失效链接 {len(bad_url)} 条：{bad_url[:5]}")
        if bad_anchor:
            print(f"  ✗ 锚点缺失 {len(bad_anchor)} 条：{bad_anchor[:5]}")
        if bad_url or bad_anchor:
            sys.exit(1)
        print("  ✓ 全部命中")


if __name__ == "__main__":
    main()
