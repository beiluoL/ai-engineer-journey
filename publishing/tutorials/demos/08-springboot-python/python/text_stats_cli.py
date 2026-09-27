"""一次性脚本：从 stdin 读一行 JSON，往 stdout 写一行 JSON。

运行（自测）：
    echo '{"text":"Spring Boot calls Python","top_k":3}' | python text_stats_cli.py

Java 侧用 ProcessBuilder 启动它，写 stdin、读 stdout。
约定三条，缺一条线上必踩坑：
  1. stdout 只允许有一行业务 JSON —— print() 调试日志必须走 stderr；
  2. 任何异常都要以非零退出码退出，Java 靠 exitValue() 判断成败；
  3. 用 sys.stdin.readline() 读，不要 input()，避免交互提示阻塞。
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter

STOP_WORDS = {
    "the", "is", "a", "an", "and", "or", "of", "to", "in", "on", "it",
    "that", "this", "for", "with", "as", "be", "are", "was", "were",
}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def analyze(text: str, top_k: int) -> dict:
    started = time.perf_counter()
    words = TOKEN_RE.findall(text)
    counter = Counter(w.lower() for w in words if w.lower() not in STOP_WORDS)
    return {
        "chars": len(text),
        "words": len(words),
        "top_words": [[w, c] for w, c in counter.most_common(top_k)],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "engine": "python-cli",
    }


def main() -> int:
    raw = sys.stdin.readline()
    if not raw.strip():
        print("empty stdin", file=sys.stderr)
        return 2

    try:
        payload = json.loads(raw)
        text = payload["text"]
        top_k = int(payload.get("top_k", 5))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"bad request: {exc}", file=sys.stderr)
        return 2

    print("start analyzing", file=sys.stderr)  # 调试日志走 stderr，不污染 stdout
    result = analyze(text, top_k)
    print(json.dumps(result, ensure_ascii=False))  # 唯一一行业务输出
    return 0


if __name__ == "__main__":
    sys.exit(main())
