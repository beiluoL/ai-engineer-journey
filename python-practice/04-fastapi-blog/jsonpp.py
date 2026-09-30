#!/usr/bin/env python3
"""把 stdin 的 JSON 美化输出，且**不把中文转义**。

两个细节，都是被截图逼出来的：

1. `python3 -m json.tool` 默认 ensure_ascii=True，中文会变成 \\u4e2d\\u6587，
   演示输出完全没法读 —— 所以要自己写一行 ensure_ascii=False。
2. `json.dumps(indent=2)` 会把 `"tags": ["自动化", "pandas"]` 拆成 5 行。
   一个对象动辄 11 行，一屏就没了。所以这里对**短数组**做内联展开。

用法：
    curl -s http://127.0.0.1:8130/posts/1 | python3 jsonpp.py
    curl -s http://127.0.0.1:8130/posts   | python3 jsonpp.py --lines

--lines：列表接口一行一条（几十条记录逐字段展开会有几百行）。
"""
from __future__ import annotations

import json
import sys

INLINE_ARRAY_MAX = 4   # 元素 ≤ 4 且都是标量的数组，打在一行里


def render(obj: object, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        rows = [
            f'{pad}  {json.dumps(k, ensure_ascii=False)}: {render(v, indent + 1)}'
            for k, v in obj.items()
        ]
        return "{\n" + ",\n".join(rows) + f"\n{pad}}}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if len(obj) <= INLINE_ARRAY_MAX and all(
            not isinstance(x, (dict, list)) for x in obj
        ):
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in obj) + "]"
        rows = [f"{pad}  {render(x, indent + 1)}" for x in obj]
        return "[\n" + ",\n".join(rows) + f"\n{pad}]"
    return json.dumps(obj, ensure_ascii=False)


raw = sys.stdin.read()
if not raw.strip():
    sys.exit(0)  # 204 之类的空响应，什么都不打印

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(raw, end="")  # 不是 JSON 就原样吐出（比如纯文本错误页）
    sys.exit(0)

if "--lines" in sys.argv and isinstance(data, list):
    for item in data:
        print(json.dumps(item, ensure_ascii=False))
else:
    print(render(data))
