"""``demos/`` 共用脚手架。

贯穿 pipelines/ 全部 demo 的三条约定
-----------------------------------
1. **真实落盘**：每个 demo 的终端输出同步写入 ``demos/out/<name>_terminal.txt``，
   作为后续渲染 PNG 截图的素材。截图必须来自真实运行，禁止伪造。
2. **结构化旁路**：另存 ``<name>_result.json``，便于脚本与文档复用同一份数字。
3. **统一计时**：避免每个 demo 各写一套 ``perf_counter`` 导致口径不一致。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"


class Timer:
    """``with Timer() as t: ...`` 之后读 ``t.seconds``。"""

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        self.seconds = 0.0
        return self

    def __exit__(self, *exc) -> bool:
        self.seconds = time.perf_counter() - self.start
        return False


class Tee:
    """同时写 stdout 与文件；并保证演示里的每一行都能被截图复现。"""

    def __init__(self, name: str) -> None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.path = OUT_DIR / f"{name}_terminal.txt"
        self._fh = self.path.open("w", encoding="utf-8")

    def print(self, *args) -> None:
        text = " ".join(str(a) for a in args)
        print(text)
        self._fh.write(text + "\n")
        self._fh.flush()

    def lines(self, iterable) -> None:
        for line in iterable:
            self.print(line)

    def save_json(self, payload) -> Path:
        path = OUT_DIR / f"{self.name}_result.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "Tee":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False


def rule(title: str = "", width: int = 72) -> str:
    """分节标题行。为空则返回纯分隔线。"""
    if title:
        return f"== {title} " + "-" * max(0, width - len(title) - 4)
    return "-" * width


def fmt_table(headers, rows) -> list[str]:
    """极简等宽表格。不引第三方依赖，够用即止。"""
    cols = [[str(h) for h in headers]] + [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in cols) for i in range(len(headers))]
    out: list[str] = []
    for idx, row in enumerate(cols):
        out.append("  " + "  ".join(c.ljust(w) for c, w in zip(row, widths)))
        if idx == 0:
            out.append("  " + "  ".join("-" * w for w in widths))
    return out


__all__ = ["OUT_DIR", "Tee", "Timer", "fmt_table", "rule"]
