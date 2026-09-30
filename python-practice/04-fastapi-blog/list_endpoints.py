#!/usr/bin/env python3
"""从 OpenAPI schema（stdin）里列出所有端点 —— python-practice/04-fastapi-blog

用法：
    curl -s http://127.0.0.1:8130/openapi.json | python3 list_endpoints.py

存在的意义：FastAPI 会自动生成 OpenAPI 文档，这份 schema 就是 /docs 页面
和所有代码生成器的数据源。能把它打印出来，说明「自动文档」不是宣传语。
"""
from __future__ import annotations

import json
import sys

schema = json.load(sys.stdin)
info = schema["info"]
paths = schema["paths"]
n_ops = sum(len(ops) for ops in paths.values())

print(f"  标题   : {info['title']} v{info['version']}")
print(f"  端点数 : {n_ops} 个（全部由装饰器自动注册，没写一行文档）")
print()
for path, ops in sorted(paths.items()):
    for method, op in ops.items():
        print(f"  {method.upper():<7}{path:<22}{op.get('summary', '')}")
