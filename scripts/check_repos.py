#!/usr/bin/env python3
"""学习资源体检：检查文档里推荐的 GitHub 仓库，是否还活着、还值得读。

用法:
    python3 scripts/check_repos.py                      # 扫整个仓库
    python3 scripts/check_repos.py llm-fundamentals python-practice
    python3 scripts/check_repos.py --strict             # 有死链/归档就退出码 1
    python3 scripts/check_repos.py --json out.json      # 顺便导出机器可读结果
    python3 scripts/check_repos.py --delay 1.5          # 被限流时放慢（见下）

为什么要有这个脚本：
`check_links.py` 只验证**站内相对链接**；对外推荐的 GitHub 仓库它一概不看。
而「推荐清单」是最容易腐烂的东西——库会归档、会搬 org、会进维护模式，
但你写下的那行链接永远不会自己变。这个脚本把这类腐烂变成一次可复现的运行输出。

探测手段（全部不需要 API token，避免 60 次/小时 的匿名配额）：
  · 仓库首页 HTML  → 是否 200 / 星标数 / `"isArchived":true` / 是否 302 到新地址
  · commits.atom   → 最近一次提交日期（Atom feed 公开且不限流）
  · 首页内嵌 README → 是否出现 "maintenance mode"（如 AutoGen 的徽章）

注意：本机 `raw.githubusercontent.com` 不可达，所以 README 只能从首页 HTML 里取，
不要再改回 raw 地址。

限流长什么样：连续扫两三百次请求后，GitHub 会节流当前出口 IP，
症状是 **`github.com` 整站返回 502**（而 `api.github.com` 仍正常），
持续几分钟到十几分钟。这不是仓库坏了，也不是脚本坏了——
此时应停下、把 `--delay` 调大、过一会儿再跑，**不要**把结果当成死链写进文档。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".workbuddy", ".obsidian", ".venv", "node_modules", "__pycache__"}

# 这些是 github.com 的保留路径，不是用户名
RESERVED = {
    "about", "apps", "collections", "contact", "customer-stories", "enterprise",
    "explore", "features", "issues", "join", "login", "marketplace", "new",
    "notifications", "organizations", "orgs", "pricing", "pulls", "search",
    "security", "settings", "site", "sponsors", "topics", "trending", "watching",
}
REPO_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
# 占位/示例地址，不是真推荐
PLACEHOLDER_RE = re.compile(r"^(your|yourname|your-name|example|xxx|foo|bar|user|owner)[-_]?|<|\{|\$")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

STALE_DAYS = 540          # 一年半没提交就算停滞
STATUS_ORDER = ["DEAD", "ARCHIVED", "MAINT", "STALE", "MOVE", "NET", "OK"]


def http(url: str, timeout: int = 25, retries: int = 3):
    """返回 (最终URL, 文本)；失败返回 (None, 原因)。

    `原因` 是整数时表示 HTTP 错误码，是字符串时表示网络层失败。
    网络层失败要重试：连扫几十个仓库时 GitHub 会临时拒连，
    不重试就会把「被限流」误报成「仓库已死」——这是本工具最容易骗人的地方。
    """
    last = "net:未知"
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.geturl(), resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                last = exc.code
                time.sleep(1.5 * (attempt + 1))
                continue
            return None, exc.code
        except Exception as exc:
            last = f"net:{type(exc).__name__}"
            time.sleep(1.5 * (attempt + 1))
    return None, last


def probe(repo: str) -> dict:
    """探测一个仓库，返回状态字典。"""
    out = {"repo": repo, "stars": None, "last": None, "moved_to": None,
           "archived": False, "maintenance": False, "note": ""}

    final, html = http(f"https://github.com/{repo}")
    # http() 失败时统一返回 (None, 原因)：整数=HTTP 错误码，字符串=网络层失败。
    # 这里必须先判 final，否则下面的 rstrip 会在 None 上崩。
    if final is None:
        out["status"] = "NET" if isinstance(html, str) else "DEAD"
        out["note"] = str(html)
        return out
    if not isinstance(html, str):
        out["status"] = "DEAD"
        out["note"] = f"非预期响应 {html!r}"
        return out

    if final.rstrip("/").lower() != f"https://github.com/{repo}".lower():
        out["moved_to"] = final.rstrip("/").replace("https://github.com/", "")

    m = re.search(r'id="repo-stars-counter-star"[^>]*title="([\d,]+)"', html)
    if m:
        out["stars"] = int(m.group(1).replace(",", ""))
    out["archived"] = '"isArchived":true' in html
    out["maintenance"] = "maintenance mode" in html.lower()

    # Atom feed 也要重试。它失败时 `last` 会留空，表格里就出现一个
    # 看起来像真实值的 "-"——「取不到」和「真的没有」必须区分开，
    # 否则这张要贴进文档当证据的表会悄悄少一个数据点。
    atom_err = "未能取到提交日期"
    for attempt in range(3):
        _, atom = http(f"https://github.com/{repo}/commits.atom", timeout=20)
        if isinstance(atom, str) and atom:
            m = re.search(r"<updated>([0-9]{4}-[0-9]{2}-[0-9]{2})", atom)
            if m:
                out["last"] = m.group(1)
                break
            atom_err = "atom 无 updated 字段"
        else:
            atom_err = f"atom 取回失败({atom})"
        time.sleep(1.2 * (attempt + 1))
    if out["last"] is None:
        out["note"] = atom_err

    if out["archived"]:
        out["status"] = "ARCHIVED"
    elif out["maintenance"]:
        out["status"] = "MAINT"
        out["note"] = "README 声明维护模式"
    elif out["moved_to"]:
        out["status"] = "MOVE"
        out["note"] = f"→ {out['moved_to']}"
    elif out["last"] and days_since(out["last"]) > STALE_DAYS:
        out["status"] = "STALE"
        out["note"] = f"已 {days_since(out['last'])} 天无提交"
    else:
        out["status"] = "OK"
    return out


def days_since(day: str) -> int:
    import datetime
    d = datetime.date(*map(int, day.split("-")))
    return (datetime.date.today() - d).days


def collect(roots) -> tuple[dict[str, list], list[str], int]:
    """扫描 markdown/html，返回 ({repo: [出处]}, 排序后的仓库名, 扫过的文件数)。"""
    files: list[str] = []
    for root in roots:
        if os.path.isfile(root):                 # 传单文件就只扫这一个，别把整个目录带上
            files.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.endswith((".md", ".html")):
                    files.append(os.path.join(dirpath, name))

    found: dict[str, list] = {}
    for path in sorted(set(files)):
        text = open(path, encoding="utf-8", errors="ignore").read()
        for owner, name_ in REPO_RE.findall(text):
            if owner.lower() in RESERVED or PLACEHOLDER_RE.match(owner):
                continue
            repo = f"{owner}/{name_.removesuffix('.git')}"
            rel = os.path.relpath(path, ROOT)
            found.setdefault(repo, [])
            if rel not in found[repo]:
                found[repo].append(rel)
    return found, sorted(found), len(set(files))


def main() -> int:
    ap = argparse.ArgumentParser(description="学习资源（GitHub 仓库）链接体检")
    ap.add_argument("paths", nargs="*", help="要扫描的目录或文件，默认整个仓库")
    ap.add_argument("--strict", action="store_true",
                    help="出现死链 / 归档 / 迁移时退出码 1")
    ap.add_argument("--json", dest="json_out", help="把结果另存为 JSON")
    ap.add_argument("--only", help="只探测匹配该子串的仓库（调试用）")
    ap.add_argument("--delay", type=float, default=0.6,
                    help="每次探测之间的间隔秒数（默认 0.6）。"
                         "被 GitHub 限流时调大它——连续扫几百个仓库会触发节流，"
                         "表现为 github.com 整站 502，而不是某个仓库 404。")
    args = ap.parse_args()

    roots = args.paths or [ROOT]
    found, repos, n_files = collect(roots)
    if args.only:
        repos = [r for r in repos if args.only.lower() in r.lower()]

    print(f"扫描 {n_files} 篇文档，抽到 {len(repos)} 个 GitHub 仓库\n")
    print(f"{'状态':<9}{'星标':>8}  {'最近提交':<11}{'仓库':<44}备注")
    print("-" * 108)

    results = []
    for repo in repos:
        r = probe(repo)
        r["refs"] = found.get(repo, [])
        results.append(r)
        time.sleep(args.delay)   # 请求间隔：太密会被 GitHub 临时拒连

    # 二次补测：连续扫几十个仓库时 GitHub 会偶发拒连。
    # 不补测就会把「被限流」写成「这个仓库有问题」——那是彻头彻尾的假消息，
    # 而这张表是要被贴进文档当证据的。
    net = [i for i, r in enumerate(results) if r["status"] == "NET"]
    if net:
        print(f"（首轮有 {len(net)} 个仓库被拒连，正在二次补测…）\n")
        for i in net:
            time.sleep(2.0)
            again = probe(results[i]["repo"])
            again["refs"] = results[i]["refs"]
            results[i] = again

    results.sort(key=lambda r: (STATUS_ORDER.index(r["status"]), -(r["stars"] or 0)))
    for r in results:
        stars = f"{r['stars']:,}" if r["stars"] else "-"
        print(f"{r['status']:<9}{stars:>8}  {r['last'] or '-':<11}{r['repo']:<44}{r['note']}")

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    bad = [r for r in results if r["status"] in ("DEAD", "ARCHIVED", "MOVE", "NET")]
    print("-" * 108)
    print("汇总：" + "  ".join(f"{k} {counts[k]}" for k in STATUS_ORDER if k in counts))
    if bad:
        print("\n需要处理：")
        for r in bad:
            where = "、".join(r["refs"][:2]) or "?"
            print(f"  [{r['status']}] {r['repo']}  ← {where}  {r['note']}")
    else:
        print("没有死链、归档或已迁移的仓库。")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        print(f"\n已导出 {args.json_out}")

    if args.strict and bad:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
