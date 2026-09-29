"""demo 输出器：让**终端看到的内容**和 ``demos/out/<demo>_terminal.txt`` 逐字节一致。

为什么要自己写一个而不是用管道 ``| tee``：
- ``tee`` 依赖 shell，Windows 上跑不了，CI 里也容易丢退出码；
- demo 里还有 ``time.perf_counter()`` 之类的真实测量，重定向会影响缓冲；
- 统一在 Python 里写两份，能保证两份输出**永远一致**，不会因为某次忘了加
  ``2>&1`` 就漏掉报错信息。

用法::

    from _emit import Printer
    out = Printer("demo_04_lora")
    out.section("M04 · LoRA")
    out.kv("最大绝对误差", "3.55e-15")
    out.table(["r", "loss"], [[1, 2.3], [8, 1.9]])
    out.close()
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "out"
WIDTH = 78


def _fmt(value, spec: str = "") -> str:
    if spec:
        try:
            return format(value, spec)
        except (ValueError, TypeError):
            return str(value)
    return str(value)


class Printer:
    """同时写 stdout 和 txt 文件的打印器（两份内容严格相同）。"""

    def __init__(self, demo_name: str) -> None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.demo_name = demo_name
        self.path = OUT_DIR / f"{demo_name}_terminal.txt"
        self.fh = open(self.path, "w", encoding="utf-8")

    # ---------------- 基础 ----------------

    def line(self, text: str = "") -> None:
        """写一行（stdout + 文件）。"""
        sys.stdout.write(text + "\n")
        self.fh.write(text + "\n")
        self.fh.flush()

    __call__ = line

    def blank(self) -> None:
        self.line("")

    def rule(self, ch: str = "-") -> None:
        self.line(ch * WIDTH)

    def section(self, title: str) -> None:
        """带章节标题的结构化输出。"""
        self.blank()
        self.line("=" * WIDTH)
        self.line(f"  {title}")
        self.line("=" * WIDTH)

    def subsection(self, title: str) -> None:
        self.blank()
        self.line(f"── {title} " + "─" * max(0, WIDTH - len(title) - 4))

    def kv(self, key: str, value, note: str = "", width: int = 38) -> None:
        """``键 ...... 值   注释``（键左对齐到固定宽度）。"""
        text = _fmt(value)
        line = f"  {key:<{width}} {text}"
        if note:
            line += f"   {note}"
        self.line(line)

    def bullets(self, items, prefix: str = "  · ") -> None:
        for it in items:
            self.line(f"{prefix}{it}")

    # ---------------- 表格 ----------------

    def table(
        self,
        headers: list[str],
        rows: list[list],
        aligns: "list[str] | None" = None,
        indent: str = "  ",
    ) -> None:
        """等宽表格（headers/rows 都用 str() 渲染，宽度按内容自适应）。"""
        cols = len(headers)
        aligns = aligns or ["<"] * cols
        cells = [[str(h) for h in headers]] + [[_fmt(c) if not isinstance(c, str) else c for c in row] for row in rows]
        widths = [max(len(r[i]) for r in cells) for i in range(cols)]

        def _pad(values: list[str], al: list[str]) -> str:
            parts = []
            for v, w, a in zip(values, widths, al):
                parts.append(f"{v:{a}{w}}")
            return "  ".join(parts)

        self.line(indent + _pad(cells[0], ["<"] * cols))
        self.line(indent + "  ".join("-" * w for w in widths))
        for row in cells[1:]:
            self.line(indent + _pad(row, aligns))

    # ---------------- 收尾 ----------------

    def close(self) -> None:
        self.fh.flush()
        self.fh.close()

    def __enter__(self) -> "Printer":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
