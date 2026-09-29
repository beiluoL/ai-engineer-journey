"""Demo 公共工具：把 stdout 同时写进 ``demos/out/<name>.txt``。

每个 demo 都是「真实运行 + 真实落盘」：终端看到的、文档贴的、截图渲染的，
必须是同一份数字。所以统一用 :class:`Tee` 双写。
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "demos" / "out"


class Tee:
    """同时写多个流的 stdout 替身。"""

    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            s.write(data)
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()


def run(out_name: str, main) -> int:
    """打开 ``demos/out/<out_name>``，把 main() 的 stdout 双写进去。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / out_name
    with path.open("w", encoding="utf-8") as fh, contextlib.redirect_stdout(Tee(sys.stdout, fh)):
        return main()
