"""把 demo 输出逐字写到 stdout 与 demos/out。"""

from __future__ import annotations

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
        text = f"  {key:<34} {value}"
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

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()
