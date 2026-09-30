#!/usr/bin/env python3
"""03-web-crawler 可复现演示 —— python-practice/03-web-crawler

把「生成站点 → 起服务 → 爬取 → 存 CSV」串成一条命令，输出就是文档里的截图。
之所以不写成 demo.sh：起服务需要动态端口 + 关停，用 Python 的线程比 shell 干净。

运行：
    python3 demo.py
"""
from __future__ import annotations

import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import crawler as crawler_mod  # noqa: E402
import make_fixture_site  # noqa: E402
import serve as serve_mod  # noqa: E402

OUT = ROOT / "assets" / "books.csv"


def disp(text: str) -> int:
    """按终端显示宽度算长度：中文/全角算 2 格，英文算 1 格。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int, right: bool = False) -> str:
    """按显示宽度补空格 —— 直接用 f"{s:<20}" 遇到中文会歪。"""
    space = " " * max(0, width - disp(text))
    return space + text if right else text + space


def main() -> int:
    print("# 03 网站内容爬虫 —— 本地 fixture 站点 + 真实 HTTP 请求")
    print()

    print("① 生成 fixture 站点")
    written = make_fixture_site.build()
    print(f"   → .site/ 下 {len(written)} 个页面（{make_fixture_site.SEED} 号种子，每次内容一致）")
    print()

    print("② 起本地 HTTP 服务（端口交给系统选，避免撞端口）")
    server, port, _thread = serve_mod.serve_in_background()
    base = f"http://127.0.0.1:{port}/"
    print(f"   → {base}")
    print("   注：/page-2.html 的第 1 次访问会返回 503，这是故意的")
    print()

    try:
        print(f"③ 开始爬取（广度优先，白名单只跟 index 与 /page-N.html）")
        result = crawler_mod.crawl(base, delay=0.05, log=print)
    finally:
        server.shutdown()
        server.server_close()

    books = result.books
    print()
    print("④ 抓取结果")
    print(f"   访问页面 {result.visited} 个 ｜ 失败 {len(result.failed)} 个 ｜ 重试 {result.retries} 次")
    for url, reason in result.failed:
        print(f"     失败：{url.replace(base, '/')} → {reason}")
    print(f"   共解析出 {len(books)} 本书")

    if not books:
        print("\n没抓到数据，检查一下 fixture 站点是否生成成功。")
        return 1

    crawler_mod.write_csv(books, OUT)
    print(f"   写出 {OUT.relative_to(ROOT.parent.parent)}（utf-8-sig，Excel 直接双击不乱码）")
    print()

    print("⑤ 前 5 行预览")
    print("   " + pad("书名", 30) + pad("作者", 22) + pad("品类", 12)
          + pad("价格", 8, right=True) + pad("评分", 8, right=True) + pad("库存", 6, right=True))
    for b in books[:5]:
        print(
            "   " + pad(b.title, 30) + pad(b.author, 22) + pad(b.category, 12)
            + pad(f"{b.price:.1f}", 8, right=True)
            + pad(f"{b.rating:.1f}", 8, right=True)
            + pad(str(b.stock), 6, right=True)
        )
    print(f"   ...（共 {len(books)} 行）")
    print()

    print("⑥ 统计")
    by_cat = Counter(b.category for b in books)
    print("   品类分布：" + "  ".join(f"{k} {v} 本" for k, v in by_cat.most_common()))
    avg = sum(b.price for b in books) / len(books)
    print(f"   平均价格 {avg:.1f} 元 ｜ 最贵 {max(books, key=lambda b: b.price).title}"
          f"（{max(b.price for b in books):.0f} 元）")
    top = max(books, key=lambda b: b.rating)
    print(f"   评分最高 {top.title}（{top.rating}）")

    print()
    print(f"完成：{len(books)} 本书，来自 {result.visited - len(result.failed)} 个页面，全程本地 HTTP。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
