"""demo 公用装置：把 src/ 加进 sys.path，并提供终端风格的打印小工具。

每个 demo 的 stdout 就是截图的内容，所以这里统一：
    head(cmd)   —— 打印一行 `$ 命令`，让读者知道这段输出是哪条命令产生的
    rule(title) —— 分节线，方便在截图里定位
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

WIDTH = 96


def head(cmd: str) -> None:
    print(f"$ {cmd}")


def rule(title: str = "") -> None:
    if not title:
        print("-" * WIDTH)
    else:
        print(f"--- {title} " + "-" * max(WIDTH - len(title) - 5, 4))


def note(text: str) -> None:
    print(f"# {text}")
