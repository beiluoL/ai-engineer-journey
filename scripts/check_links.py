#!/usr/bin/env python3
"""仓库体检：检查 Markdown / HTML 里的相对链接与图片是否真实存在。

用法:
    python3 scripts/check_links.py            # 检查整个仓库
    python3 scripts/check_links.py projects   # 只检查某个目录
    python3 scripts/check_links.py --strict   # 有错就退出码 1（CI 用）

为什么要有这个脚本：
文档一旦超过几万行，人眼维护的目录/交叉引用必然漂移。
每次改完文档或发 PR 前跑一次，能把「死链」这类静默腐烂挡在门外。
"""
import os
import re
import sys

SKIP_DIRS = {".git", ".workbuddy", ".obsidian", ".venv", "node_modules", "__pycache__"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
# 代码块与行内代码里的 [x](y) 不是链接，先抹掉再扫，否则像
# `REGISTRY[name](**args)` 这种代码会被误报成死链。
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "data:", "#", "//"))


def scan(roots):
    bad_links, bad_imgs, ok = [], [], 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if not name.endswith((".md", ".html")):
                    continue
                path = os.path.join(dirpath, name)
                text = open(path, encoding="utf-8", errors="ignore").read()
                text = strip_code(text)

                for m in LINK_RE.finditer(text):
                    target = m.group(1).strip().split("#")[0].strip()
                    if not target or is_external(target):
                        continue
                    full = os.path.normpath(os.path.join(dirpath, target))
                    if os.path.exists(full):
                        ok += 1
                    else:
                        bad_links.append((path, target))

                for m in IMG_RE.finditer(text):
                    target = m.group(1).strip()
                    if is_external(target):
                        continue
                    full = os.path.normpath(os.path.join(dirpath, target))
                    if not os.path.exists(full):
                        bad_imgs.append((path, target))
    return ok, bad_links, bad_imgs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    roots = args or ["."]

    ok, bad_links, bad_imgs = scan(roots)
    print(f"扫描目录: {', '.join(roots)}")
    print(f"有效相对链接: {ok}")

    if bad_links:
        print(f"\n死链 {len(bad_links)} 处:")
        for src, tgt in bad_links[:50]:
            print(f"  {src} -> {tgt}")
    if bad_imgs:
        print(f"\n坏图 {len(bad_imgs)} 处:")
        for src, tgt in bad_imgs[:50]:
            print(f"  {src} -> {tgt}")

    if not bad_links and not bad_imgs:
        print("\nOK: 没有死链，没有坏图")
        return 0

    print(f"\nFAIL: {len(bad_links)} 死链 / {len(bad_imgs)} 坏图")
    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
