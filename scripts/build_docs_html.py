#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量把仓库里的 Markdown 文档转换成渲染后的 HTML，供 publishing/html/index.html 索引。

为什么要有这个脚本（而不是手工跑 200 次单文件转换）：
1. 索引里的每一条目都要能点到「渲染后的页面」，手工维护映射表必然腐烂。
2. 转换规则必须保持一致——同样的 CSS、同样的图片策略、同样的链接改写。
3. 200+ 篇文档靠人点是不可能的。

产物布局（关键约定）：
    publishing/html/docs/<源文档相对路径>.html
即输出目录**镜像**源目录结构。这不是洁癖，是硬约束：转换用的是 --relative-images
（图片按相对路径引用，339 张图 56.7 MB 绝不能 base64 内嵌），一旦镜像结构乱了，
浏览器里所有图都会 404。

链接改写：--rewrite-md-links 会把站内 `../README.md` 改成 `../README.html`，
锚点（#xxx）保留。因为输出树与源树同构，相对层级天然一致。

用法：
    python3 scripts/build_docs_html.py                 # 转换全部（已存在且较新的会跳过）
    python3 scripts/build_docs_html.py --force          # 忽略时间戳，全部重转
    python3 scripts/build_docs_html.py llm-fundamentals  # 只转换某个目录/文件的子串
    python3 scripts/build_docs_html.py 07-延伸阅读 --force
"""
import os
import sys
import re
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_to_book_html as conv  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(ROOT, "publishing", "html", "docs")

EXCLUDE_DIRS = {".git", ".workbuddy", "node_modules", "__pycache__",
                ".venv", "venv", "site-packages", ".pytest_cache",
                ".mypy_cache", ".obsidian", "html"}


def iter_md():
    """枚举所有「算文档」的 .md（与 gen_doc_index.py 的口径保持一致）。"""
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
        for fn in sorted(fns):
            if fn.lower().endswith(".md"):
                yield os.path.join(dp, fn)


def out_path(src):
    rel = os.path.relpath(src, ROOT)
    return os.path.join(OUT_ROOT, rel[:-3] + ".html")


def fixup_paths(page: str, src_dir: str, dst_dir: str) -> str:
    """把产物里指向「源树资源」的相对路径，改写成「从产物目录出发」的相对路径。

    为什么必须有这一步：产物在 publishing/html/docs/<...>/ 下，而图片、demos 输出
    这些真实文件还在源目录里。docs 树只镜像了 .html，没有（也不可能）复制 56.7 MB
    的图。所以凡是「源树里存在、但不是文档」的目标（图片、.txt 证据文件…），
    都要重新算一次相对路径指回源树，否则浏览器里全部 404。

    指向别的文档的链接（.html / 原 .md）不动：它们本来就在 docs 树内部。
    """
    attr_re = re.compile(r'(src|href)="([^"]+)"')
    doc_ext = (".html",)

    def repl(m):
        kind, url = m.group(1), m.group(2)
        if url.startswith(("http", "mailto:", "data:", "#", "/")):
            return m.group(0)
        target = url.split("#")[0]
        if not target:
            return m.group(0)
        if target.lower().endswith(doc_ext):
            return m.group(0)  # 站内文档，docs 树内相对路径已正确
        cand = os.path.normpath(os.path.join(src_dir, target))
        if os.path.exists(cand):
            return f'{kind}="{os.path.relpath(cand, dst_dir).replace(os.sep, "/")}"'
        return m.group(0)

    return attr_re.sub(repl, page)


def split_embedded(page: str):
    """把页面切成 (数据块之前, 数据块, 数据块之后)。

    内嵌原始 Markdown 的 JSON 里会出现 `href="..."` `[x](y.md)` 这类字面量；
    如果跟着页面一起过 fixup_paths，markdown 正文会被当成站内链接改写，
    源码视图里就会显示成被篡改过的路径。所以必须把这一段摘出来单独放回。
    """
    i = page.find(conv.MD_SRC_START)
    j = page.find(conv.MD_SRC_END)
    if i < 0 or j < 0:
        return page, "", ""
    j += len(conv.MD_SRC_END)
    return page[:i], page[i:j], page[j:]


def home_href_for(dst_dir, chno=None):
    """从产物目录回到 publishing/html/index.html 的相对路径（带该文档的章节锚点）。

    带锚点是有意的：从第 47 章点回总览，应该落回总览里的第 47 章，
    而不是被扔回页面顶部从头再找一遍。
    """
    root = os.path.join(ROOT, "publishing", "html", "index.html")
    href = os.path.relpath(root, dst_dir).replace(os.sep, "/")
    return f"{href}#ch-{chno}" if chno else href


def convert_one(src, force=False, chapter_of=None):
    dst = out_path(src)
    if not force and os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return "skip"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, encoding="utf-8") as f:
        md_text = f.read()
    src_dir = os.path.dirname(os.path.abspath(src))
    dst_dir = os.path.dirname(dst)
    rel = os.path.relpath(src, ROOT).replace(os.sep, "/")
    body = conv.md_to_html(md_text, src_dir)
    title = None
    m = re.search(r"^#\s+(.*)$", md_text, re.M)
    if m:
        title = m.group(1).strip()
    chno = (chapter_of or {}).get(rel)
    page = conv.build_page(
        title or os.path.basename(src), body,
        home_href=home_href_for(dst_dir, chno),
        home_tip=f"返回《文档总览》第 {chno} 章" if chno else "返回文档总览",
        md_text=md_text, md_path=rel, md_name=os.path.basename(src))
    head, data, tail = split_embedded(page)
    page = (fixup_paths(head, src_dir, dst_dir) + data
            + fixup_paths(tail, src_dir, dst_dir))
    with open(dst, "w", encoding="utf-8") as f:
        f.write(page)
    return "ok"


def build_portable():
    """用 base64 内嵌模式重建 *.portable.html，让便携版也带目录 / 进度条 / 上下章。

    为什么不复用 convert_one：那条路强制 RELATIVE_IMAGES=True（339 张图 56.7 MB
    全走相对路径），而便携版存在的全部意义就是图片内嵌、拷走断网也能双击看。
    PORTABLE 映射直接 import gen_doc_index，避免两处各维护一份清单。
    """
    import gen_doc_index as idx
    n = 0
    chmap = idx.chapter_map()
    for rel, port in idx.PORTABLE.items():
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print(f"  跳过便携版（源文档不存在）: {rel}")
            continue
        dst = os.path.join(OUT_ROOT, port)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        conv.RELATIVE_IMAGES = False
        conv.REWRITE_MD_LINKS = False
        md_text = open(src, encoding="utf-8").read()
        body = conv.md_to_html(md_text, os.path.dirname(os.path.abspath(src)))
        m = re.search(r"^#\s+(.*)$", md_text, re.M)
        chno = chmap.get(rel.replace(os.sep, "/"))
        page = conv.build_page(
            m.group(1).strip() if m else port, body,
            home_href=home_href_for(os.path.dirname(dst), chno),
            home_tip=f"返回《文档总览》第 {chno} 章" if chno else "返回文档总览",
            md_text=md_text, md_path=rel.replace(os.sep, "/"),
            md_name=os.path.basename(src))
        with open(dst, "w", encoding="utf-8") as f:
            f.write(page)
        n += 1
    return n


def fix_portable():
    """把 docs 树里 *.portable.html 的「源树资源」链接重新算一遍相对路径。

    背景（2026-10-01 收编时踩到）：那两篇 base64 自包含便携版原本躺在
    publishing/html/ 根目录，那时页面里的 `08-alignment-rlhf.md` 之类站内链接
    是相对 publishing/html/ 算的——本来就是死链，只是压根不在 docs 树里、
    verify() 扫不到所以没人发现。收进 docs/ 镜像树后它们和渲染版同构了，
    链接应该改成回指源树。这一步必须做，否则进 docs 树就变成一页带 30 多条
    死链的样本。

    幂等：目标在源树里不存在时 fixup_paths 原样返回，反复跑结果一致。
    内嵌的源码数据块同样要摘出来单独放回（否则 markdown 正文里的链接会被改写）。
    """
    n = 0
    for dp, dns, fns in os.walk(OUT_ROOT):
        for fn in fns:
            if not fn.endswith(".portable.html"):
                continue
            path = os.path.join(dp, fn)
            src_dir = os.path.dirname(path)                    # 便携版所在（docs 树内）
            src_tree = os.path.join(ROOT, os.path.relpath(src_dir, OUT_ROOT))
            if not os.path.isdir(src_tree):
                continue
            text = open(path, encoding="utf-8").read()
            head, data, tail = split_embedded(text)
            fixed = (fixup_paths(head, src_tree, src_dir) + data
                     + fixup_paths(tail, src_tree, src_dir))
            if fixed != text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(fixed)
                n += 1
    return n


def verify():
    """自校验：产物里所有指向 .html 的相对链接都必须真实存在。

    这一步不能省——链接改写是大范围自动行为，一旦某个 .md 没被转换（比如被
    EXCLUDE_DIRS 漏掉），整棵链接树就会出现死链，而索引页面本身不会报错。

    注意先剥掉 <script>/<style>：页面现在内嵌了原始 Markdown 的 JSON，
    里面的 `href="x.md"` 是**markdown 正文的字面量**，不是这个页面的链接关系。
    """
    bad, total = [], 0
    strip_re = re.compile(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", re.I)
    attr_re = re.compile(r'(?:src|href)="([^"]+)"')
    for dp, dns, fns in os.walk(OUT_ROOT):
        for fn in fns:
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dp, fn)
            text = strip_re.sub("", open(path, encoding="utf-8", errors="ignore").read())
            for u in attr_re.findall(text):
                if u.startswith(("http", "mailto:", "data:", "#")):
                    continue
                tgt = u.split("#")[0]
                if not tgt:
                    continue
                total += 1
                if not os.path.exists(os.path.normpath(os.path.join(dp, tgt))):
                    bad.append((os.path.relpath(path, ROOT), u))
    return total, bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv

    conv.RELATIVE_IMAGES = True
    conv.REWRITE_MD_LINKS = True

    import gen_doc_index as idx
    chapter_of = idx.chapter_map()

    targets = []
    for src in iter_md():
        rel = os.path.relpath(src, ROOT)
        if args and not any(f in rel for f in args):
            continue
        targets.append(src)

    stats = {"ok": 0, "skip": 0}
    t0 = time.time()
    for src in targets:
        st = convert_one(src, force=force, chapter_of=chapter_of)
        stats[st] += 1

    built = build_portable()
    fixed = fix_portable()
    print(f"便携版重建：{built} 个（base64 内嵌），链接重算：修正 {fixed} 个文件")
    checked, bad = verify()
    print(f"转换完成：新生成 {stats['ok']} 篇，跳过（已是最新）{stats['skip']} 篇"
          f"，耗时 {round(time.time() - t0, 1)}s")
    n_html = sum(1 for _ in glob_files(OUT_ROOT, ".html"))
    print(f"产物目录：{os.path.relpath(OUT_ROOT, ROOT)}（共 {n_html} 个 HTML）")
    print(f"链接校验：检查 {checked} 条 .html 链接，失效 {len(bad)} 条")
    for s, u in bad[:20]:
        print(f"  死链: {s} -> {u}")
    return 1 if bad else 0


def glob_files(root, ext):
    for dp, dns, fns in os.walk(root):
        for fn in fns:
            if fn.endswith(ext):
                yield fn


if __name__ == "__main__":
    sys.exit(main())
