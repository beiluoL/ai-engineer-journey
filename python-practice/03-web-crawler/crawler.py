#!/usr/bin/env python3
"""网站内容爬虫 —— python-practice/03-web-crawler

任务卡：python-practice/03-web-crawler/README.md

流程：发请求 → 解析 HTML → 抽取字段 → 翻页 → 存 CSV。

真正要练的不是「怎么取到一个页面」，而是这些**工程细节**：

- 超时：`timeout=(连接超时, 读取超时)`，不设的话网络一卡就永久挂住
- 重试：5xx / 429 才重试，4xx（比如 404）重试一万次也没用
- 礼貌：每次请求之间 sleep，别把人家服务器打死
- 白名单：只跟该跟的链接（`about.html` 这种无关页直接跳过）
- 去重：同一个 URL 只访问一次，否则会爬进死循环
- 解析失败不能静默：字段缺失要能被发现，而不是安静地写一行空值进 CSV

运行（配合 serve.py）：
    python3 serve.py &                                   # 起站点
    python3 crawler.py --base http://127.0.0.1:8123 --out assets/books.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# 只爬首页和 /page-N.html —— 白名单比黑名单安全得多
ALLOW_RE = re.compile(r"^/(?:page-\d+\.html)?$")

USER_AGENT = "python-practice-crawler/1.0 (+educational; respects robots)"

RETRY_STATUS = {429, 500, 502, 503, 504}  # 值得重试的状态码
MAX_RETRY = 3


@dataclass
class Book:
    title: str
    author: str
    category: str
    price: float
    rating: float
    stock: int
    source: str  # 来自哪个页面 URL —— 出问题时能回溯


@dataclass
class CrawlResult:
    books: list[Book]
    visited: int
    failed: list[tuple[str, int | str]]  # (url, 状态码或错误信息)
    retries: int


def make_session(trust_env: bool = False) -> requests.Session:
    """建一个会话。

    trust_env=False 是关键：默认情况下 requests 会读环境变量里的
    HTTP_PROXY / HTTPS_PROXY。本机只要装过任何代理软件，访问 127.0.0.1
    就可能被代理吞掉，报一堆莫名其妙的 ConnectionError。
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.trust_env = trust_env
    return session


def fetch(session: requests.Session, url: str, log) -> tuple[int, str, int]:
    """带重试的 GET。返回 (状态码, 文本, 重试次数)；彻底失败时状态码为 0。"""
    delay = 0.5
    retries = 0
    for attempt in range(1, MAX_RETRY + 1):
        try:
            # connect / read 分开设：连不上要快速失败，但大页面要给足读取时间
            resp = session.get(url, timeout=(3, 10))
        except requests.RequestException as exc:
            retries += 1
            log(f"       ↩ 网络错误 {type(exc).__name__}（第 {attempt} 次）")
            if attempt == MAX_RETRY:
                return 0, "", retries
            time.sleep(delay)
            delay *= 2
            continue

        if resp.status_code in RETRY_STATUS and attempt < MAX_RETRY:
            retries += 1
            log(f"       ↩ {resp.status_code} 服务端说「稍后再来」，等 {delay:.1f}s 重试")
            time.sleep(delay)
            delay *= 2
            continue

        return resp.status_code, decode_body(resp), retries
    return 0, "", retries


def decode_body(resp: requests.Response) -> str:
    """别直接信 resp.text —— HTTP 头里没声明 charset 时它会按 ISO-8859-1 解，
    中文就变成 `æµçç Python` 这种乱码。这里先看响应头有没有 charset，
    没有再做编码探测（requests 自带 charset_normalizer）。
    """
    ctype = resp.headers.get("Content-Type", "").lower()
    if "charset=" in ctype:
        return resp.text
    return resp.content.decode(resp.apparent_encoding or "utf-8", errors="replace")


def parse_books(html: str, url: str, log) -> list[Book]:
    """从列表页 HTML 里抽书。选择器全部基于 CSS class，比正则稳健得多。"""
    soup = BeautifulSoup(html, "html.parser")
    books: list[Book] = []
    for card in soup.select("article.book"):
        try:
            title = card.select_one(".title").get_text(strip=True)
            author = card.select_one(".author").get_text(strip=True).removeprefix("作者：")
            price = float(card.select_one(".price").get_text(strip=True))
            rating = float(card.select_one(".rating").get_text(strip=True))
            stock_txt = card.select_one(".stock").get_text(strip=True)
            stock = int(re.sub(r"\D", "", stock_txt) or 0)
            category = card.get("data-category", "未分类")
        except (AttributeError, ValueError) as exc:
            # 解析失败必须暴露，否则 CSV 里会安静地少几本书
            log(f"    ⚠ 跳过一张卡片（{type(exc).__name__}: {exc}）")
            continue
        books.append(Book(title, author, category, price, rating, stock, url))
    return books


def extract_links(html: str, base: str) -> tuple[list[str], int]:
    """抽出站内、且在白名单里的链接。返回 (保留的链接, 被过滤掉的数量)。"""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base).netloc
    links: list[str] = []
    skipped = 0
    for a in soup.select("a[href]"):
        absolute = urljoin(base, a["href"])
        parsed = urlparse(absolute)
        if parsed.netloc != host or not ALLOW_RE.match(parsed.path):
            skipped += 1                     # 外站 / 白名单外（比如 /about.html）
            continue
        if absolute not in links:
            links.append(absolute)
    return links, skipped


def crawl(base: str, delay: float = 0.2, max_pages: int = 20,
          trust_env: bool = False, log=print) -> CrawlResult:
    """广度优先爬取。"""
    session = make_session(trust_env)
    queue: list[str] = [base]
    seen: set[str] = set()
    books: list[Book] = []
    failed: list[tuple[str, int | str]] = []
    retries = 0

    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        path = urlparse(url).path or "/"
        log(f"  [{len(seen):>2}] GET {path}")
        status, html, retried = fetch(session, url, log)
        retries += retried

        if status == 0:
            failed.append((url, "网络不可达"))
            log("       ⊘ 放弃（重试已用尽）")
            continue
        if status == 404:
            failed.append((url, 404))
            log("       ⊘ 404，跳过（死链，重试没有意义）")
            continue
        if status != 200:
            failed.append((url, status))
            log(f"       ⊘ {status}，跳过")
            continue

        found = parse_books(html, url, log)
        books.extend(found)
        links, skipped = extract_links(html, url)
        new_links = [link for link in links if link not in seen]
        log(
            f"       ✓ 200（{len(html) / 1024:.1f} KB）解析出 {len(found)} 本书，"
            f"新发现 {len(new_links)} 个链接（白名单过滤掉 {skipped} 个）"
        )

        queue.extend(new_links)
        time.sleep(delay)  # 礼貌间隔

    return CrawlResult(books, len(seen), failed, retries)


def write_csv(books: list[Book], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(books[0]).keys()))
        writer.writeheader()
        for b in books:
            writer.writerow(asdict(b))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取 fixture 书站并导出 CSV")
    parser.add_argument("--base", default="http://127.0.0.1:8123/", help="起始 URL")
    parser.add_argument("--out", type=Path, default=Path("assets/books.csv"))
    parser.add_argument("--delay", type=float, default=0.2, help="每次请求间隔秒数")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--trust-env", action="store_true",
                        help="信任环境变量里的代理设置（默认关闭）")
    args = parser.parse_args(argv)

    print(f"开始爬取 {args.base}")
    result = crawl(args.base, args.delay, args.max_pages, args.trust_env)
    if not result.books:
        print("没有抓到任何数据。是不是忘了先跑 serve.py？", file=sys.stderr)
        return 1

    write_csv(result.books, args.out)
    print(f"\n写出 {args.out}（{len(result.books)} 行）")
    print(f"访问 {result.visited} 个页面，失败 {len(result.failed)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
