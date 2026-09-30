#!/usr/bin/env python3
"""生成一个本地「图书商城」fixture 站点 —— python-practice/03-web-crawler

任务卡：python-practice/03-web-crawler/README.md

为什么要造一个本地站点，而不是直接爬某个真网站：
1. **可复现** —— 真网站明天改版，今天写的选择器就全废了；本地站点永远长这样
2. **有礼貌** —— 练习爬虫不该拿别人的服务器当靶子，更不该给对方制造流量
3. **能控制异常** —— 可以刻意造出 503（限流）、404（死链），逼你写重试逻辑

生成的站点结构（写在 .site/ 下，已被 .gitignore 忽略）：

    index.html       首页，链到三页列表 + 一个无关页
    page-1.html      6 本书（列表页，带「下一页」）
    page-2.html      6 本书 ← 服务器会故意对它的第 1 次请求返回 503
    page-3.html      6 本书，页脚有个指向 /missing.html 的死链
    about.html       与图书无关的页面（爬虫应该跳过它）

运行：
    python3 make_fixture_site.py        # 生成 .site/
"""
from __future__ import annotations

import html
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / ".site"

SEED = 42

# (书名, 作者, 品类, 价格区间)
BOOKS: list[tuple[str, str, str, tuple[int, int]]] = [
    ("流畅的 Python", "Luciano Ramalho", "技术", (98, 139)),
    ("深入理解计算机系统", "Randal Bryant", "技术", (128, 169)),
    ("设计数据密集型应用", "Martin Kleppmann", "技术", (89, 119)),
    ("重构：改善既有代码的设计", "Martin Fowler", "技术", (79, 109)),
    ("Python 编程：从入门到实践", "Eric Matthes", "技术", (69, 99)),
    ("算法导论", "Thomas Cormen", "技术", (118, 158)),
    ("活着", "余华", "文学", (28, 45)),
    ("百年孤独", "加西亚·马尔克斯", "文学", (39, 59)),
    ("围城", "钱锺书", "文学", (25, 42)),
    ("平凡的世界", "路遥", "文学", (45, 69)),
    ("白夜行", "东野圭吾", "文学", (32, 49)),
    ("撒哈拉的故事", "三毛", "文学", (26, 39)),
    ("万历十五年", "黄仁宇", "历史", (35, 55)),
    ("枪炮、病菌与钢铁", "贾雷德·戴蒙德", "历史", (48, 72)),
    ("人类简史", "尤瓦尔·赫拉利", "历史", (42, 68)),
    ("穷查理宝典", "查理·芒格", "商业", (68, 98)),
    ("原则", "瑞·达利欧", "商业", (55, 85)),
    ("商业模式新生代", "亚历山大·奥斯特瓦德", "商业", (59, 89)),
]

PER_PAGE = 6

PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
</head>
<body>
  <header><h1>山间书局 · 在线书单</h1></header>
  <main>
{body}
  </main>
  <footer>
    <nav>{nav}</nav>
    <p>本页面由 make_fixture_site.py 生成，仅用于爬虫练习。</p>
  </footer>
</body>
</html>
"""

BOOK_TPL = """    <article class="book" data-category="{category}">
      <h3 class="title">{title}</h3>
      <p class="author">作者：{author}</p>
      <p><span class="price">{price}</span> 元 · 评分 <span class="rating">{rating}</span> · <span class="stock">库存 {stock}</span></p>
    </article>"""


def build(root: Path = SITE) -> list[Path]:
    """生成站点文件，返回写出的路径列表。固定 seed，输出可复现。"""
    rng = random.Random(SEED)
    n_pages = (len(BOOKS) + PER_PAGE - 1) // PER_PAGE
    written: list[Path] = []
    root.mkdir(parents=True, exist_ok=True)

    def write(name: str, title: str, body: str, nav: str) -> None:
        path = root / name
        path.write_text(
            PAGE_TPL.format(title=title, body=body, nav=nav), encoding="utf-8"
        )
        written.append(path)

    # 首页
    links = "\n".join(
        f'    <li><a href="page-{i}.html">第 {i} 页</a></li>' for i in range(1, n_pages + 1)
    )
    write(
        "index.html",
        "山间书局 · 首页",
        f"  <p>共 {len(BOOKS)} 本书，分 {n_pages} 页展示。</p>\n  <ul>\n{links}\n"
        '    <li><a href="about.html">关于我们</a></li>\n  </ul>',
        '<a href="index.html">首页</a>',
    )

    # 列表页
    for page in range(1, n_pages + 1):
        chunk = BOOKS[(page - 1) * PER_PAGE : page * PER_PAGE]
        cards = []
        for title, author, category, (lo, hi) in chunk:
            cards.append(
                BOOK_TPL.format(
                    category=category,
                    title=html.escape(title),
                    author=html.escape(author),
                    price=f"{rng.randint(lo, hi)}.00",
                    rating=f"{rng.uniform(3.9, 4.9):.1f}",
                    stock=rng.randint(0, 60),
                )
            )
        prev_link = (
            f'<a href="page-{page - 1}.html">上一页</a> · ' if page > 1 else ""
        )
        # 刻意让最后一页也渲染「下一页」链接（真实站点常见的翻页 off-by-one bug），
        # 于是它会指向并不存在的 page-4.html —— 正好用来演示 404 该怎么处理。
        next_link = f' · <a href="page-{page + 1}.html">下一页</a>'
        write(
            f"page-{page}.html",
            f"山间书局 · 第 {page} 页",
            "\n".join(cards),
            f'<a href="index.html">首页</a> · {prev_link}第 {page}/{n_pages} 页'
            f"{next_link}",
        )

    # 无关页：爬虫应该靠 URL 白名单跳过它
    write(
        "about.html",
        "山间书局 · 关于",
        "  <p>一家只卖纸质书的小店，成立于 2019 年。</p>\n"
        "  <p>联系电话：000-0000-0000（演示用假号码）</p>",
        '<a href="index.html">回首页</a>',
    )
    return written


def main() -> int:
    written = build()
    print(f"写出 {len(written)} 个页面 → .site/")
    for p in written:
        print(f"  {p.name:<16} {p.stat().st_size:>6} 字节")
    print(f"\n站点共 {len(BOOKS)} 本书，分 {len(written) - 2} 页列表 + 首页 + 关于页")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
