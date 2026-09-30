"""把 demo 输出逐字写到 stdout 与 demos/out（和 P08/P09 同一套约定）。

为什么坚持落盘：文档里的每个数字都必须能追溯到**某一次真实运行**，
而不是我从脑子里编出来的。``demos/out/*.txt`` 就是证据链的第一环，
后面渲染成终端截图、再被引进 milestone 文档。
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "out"
WIDTH = 78


class Printer:
    def __init__(self, name: str) -> None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.path = OUT_DIR / f"{name}_terminal.txt"
        self.handle = self.path.open("w", encoding="utf-8")

    def line(self, text: str = "") -> None:
        sys.stdout.write(text + "\n")
        self.handle.write(text + "\n")
        self.handle.flush()

    __call__ = line

    def section(self, title: str) -> None:
        self.line()
        self.line("=" * WIDTH)
        self.line(f"  {title}")
        self.line("=" * WIDTH)

    def subsection(self, title: str) -> None:
        self.line()
        self.line(f"── {title} " + "─" * max(0, WIDTH - len(title) - 4))

    def kv(self, key: str, value, note: str = "") -> None:
        text = f"  {key:<36} {value}"
        if note:
            text += f"   {note}"
        self.line(text)

    def table(self, headers: list[str], rows: list[list], aligns: "list[str] | None" = None) -> None:
        cells = [[str(cell) for cell in headers]] + [[str(cell) for cell in row] for row in rows]
        widths = [max(len(row[index]) for row in cells) for index in range(len(headers))]
        aligns = aligns or ["<"] * len(headers)
        self.line("  " + "  ".join(f"{cell:<{width}}" for cell, width in zip(cells[0], widths)))
        self.line("  " + "  ".join("-" * width for width in widths))
        for row in cells[1:]:
            self.line("  " + "  ".join(
                f"{cell:{align}{width}}" for cell, width, align in zip(row, widths, aligns)
            ))

    def close(self) -> None:
        self.handle.close()

    @contextlib.contextmanager
    def capture(self):
        """把调用方自己的 ``print`` 也原样记进这份输出。

        M11 要展示 ``run_pipeline`` 的真实过程输出，但那段代码是直接 ``print`` 的
        （它得能独立当 CLI 用）。这里把 stdout 临时截下来、结束后逐行回放，
        顺序不变、内容不改 —— 比让 pipeline 反过来依赖 Printer 干净得多。
        """
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            yield
        for line in buffer.getvalue().splitlines():
            self.line(line)

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()
