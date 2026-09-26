"""01 章：摄入链路真的跑一遍 —— 打印每份文档的 doc_id / source / 元数据 / 字符数。

对应命令：python -m rag.cli --index data/ --fake
"""

from __future__ import annotations

from common import head, note, rule

from rag.models import META_HEADINGS
from rag.parsing import PARSER_CLASSES, expand_paths, parse_file

# source 已经在表格第一列里，metadata 行不再重复打印
QUIET = ("source", "format", "size_bytes", "parsed_at", META_HEADINGS, "code_ranges")


def main() -> int:
    head("python -m rag.cli --index data/ --fake")
    files = expand_paths(["data/"])
    print(f"索引 {len(files)} 个文件（parser 注册表："
          f"{', '.join(c.__name__ for c in PARSER_CLASSES)}）")
    rule()

    total_chars = 0
    for path in files:
        try:
            docs = parse_file(path)
        except Exception as e:                      # noqa: BLE001 - 摄入失败不炸整批
            print(f"(解析失败) {path}: {e}")
            continue
        for doc in docs:
            total_chars += len(doc.text)
            print(f"{doc.doc_id:<18}{doc.source:<38}{doc.metadata.get('format', '-'):<8}"
                  f"{len(doc.text):>7}{doc.line_count:>6}")
            flat = ", ".join(f"{k}={v}" for k, v in doc.metadata.items() if k not in QUIET)
            print(f"{'':<18}metadata : {flat or '-'}")
            headings = doc.metadata.get(META_HEADINGS) or []
            if headings:
                titles = " · ".join(f"L{h['line']} {h['title']}" for h in headings[:4])
                print(f"{'':<18}headings : {titles}")
    rule()
    # doc_id = sha256(正文)[:16]：内容变了 id 就变，重复摄入是覆盖不是翻倍
    print(f"合计 {total_chars} 字符；同一文件再跑一次会得到同样的 doc_id（幂等）")
    note("语料目录：projects/04-rag/data/（6 个真实 md/txt 文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
