"""02 章：切分结果一览 —— 每块的长度、是否带重叠、中文标点切分效果。

对应命令：python demos/demo_02_chunk.py
"""

from __future__ import annotations

from common import head, note, rule

from rag.chunker import chunk_document, chunk_text, recursive_split
from rag.models import Document, META_START_CHAR, META_START_LINE
from rag.parsing import parse_file

SAMPLE = "data/python-generators.md"


def main() -> int:
    head("python demos/demo_02_chunk.py")
    doc = parse_file(SAMPLE)[0]
    chunks = chunk_document(doc, size=500, overlap=80)

    print(f"文档 {doc.source}：{len(doc.text)} 字符 → {len(chunks)} 个块"
          f"（chunk_size=500，overlap=80）")
    rule("块清单")
    print(f"{'chunk_id':<20}{'#':>3}{'长度':>7}{'起始字符':>10}{'起始行':>8}"
          f"{'重叠头':>8}{'压上块':>8}  前 24 字符")
    for c in chunks:
        meta = c.metadata
        flag = "是" if meta.get("overlaps_prev") else "-"
        print(f"{c.chunk_id:<20}{c.index:>3}{len(c.text):>7}"
              f"{meta.get(META_START_CHAR, 0):>10}{meta.get(META_START_LINE, 0):>8}"
              f"{meta.get('overlap_head', 0):>8}{flag:>8}  {c.text[:24]!r}")

    rule("相邻块到底重叠了什么（实测共享片段）")
    for a, b in zip(chunks, chunks[1:]):
        shared = 0
        for k in range(1, min(80, len(a.text), len(b.text)) + 1):
            if a.text[-k:] == b.text[:k]:
                shared = k                       # 上一块尾巴 == 下一块头就是重叠
        if shared:
            print(f"  块{a.index} 尾部 与 块{b.index} 头部 共享 {shared} 字符：{a.text[-shared:]!r}")
        else:
            print(f"  块{a.index} 与 块{b.index} 之间没有共享片段")

    rule("中文按标点切分：降级顺序 段落 → 行 → 。！？ → .")
    text = "第一句。第二句.第三句。第四句。"
    pieces = recursive_split(text, size=6, overlap=0)
    for i, p in enumerate(pieces):
        print(f"  [{i}] 长度={len(p):>2}  {p!r}")
    note("英文句点 '.' 排在中文句末标点之后：先按中文切，切不动才轮到英文句点")

    rule("overlap 的作用：相邻块共享一段，检索时不至于两边各剩半句")
    for p in chunk_text(doc.text[:900], size=200, overlap=40):
        print(f"  长度={len(p):>3}  {p[:52]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
