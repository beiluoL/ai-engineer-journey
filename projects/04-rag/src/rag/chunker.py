"""文档切分（对应 milestone 02）。

为什么必须切（02 §1）：
    1. 上下文窗口有限 —— 检索到 10 篇 2 万字文档，prompt 直接爆炸；
    2. 检索粒度 = 答案粒度 —— 用户问 overlap 是干嘛的，理想命中的是那一小段；
    3. Embedding 的语义稀释 —— 长文档压成一个向量，那是"全文大意"，对不上小问题。

三种策略（02 §3.2）：固定长度 / 递归分隔符（默认）/ 语义切分（进阶）。
本文件实现第一种与第二种，第三种需要先把所有块向量化，成本太高，留作练习。

一个容易搞混的单位：`chunk_size=500` 的 500 是**字符**，不是 token。
token 估算沿用 02 §3.3 的 `len(text) / 1.6`（中英混排的经验值）。
"""

from __future__ import annotations

from .models import (
    META_CODE_RANGES,
    META_END_CHAR,
    META_SOURCE,
    META_END_LINE,
    META_START_CHAR,
    META_START_LINE,
    Chunk,
    Document,
)

# 递归分隔符的降级顺序（02 §3.2 / 坑 3）：
# 段落之间 → 行之间 → 中文句末 → 英文句末。
# 中文标点必须排在英文 "." 前面 —— 按空格或裸 "." 切中文只会得到一堆碎句。
DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", "。", "！", "？", ".")


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（02 §3.3），只用于 sizing，不用于计费判断。"""
    return max(1, int(len(text) / 1.6))


def line_number_of(text: str, offset: int) -> int:
    """字符偏移 → 行号（1 起）。组装 [1] (source: x.md#L12-40) 时的展示层换算。"""
    return text.count("\n", 0, max(offset, 0)) + 1


def split_with_overlap(text: str, size: int, overlap: int) -> list[str]:
    """固定长度切分：步长 = size - overlap（02 §4 设计稿）。"""
    if overlap >= size:
        raise ValueError(f"overlap({overlap}) 必须小于 size({size})，否则步长 <= 0 会死循环")
    step = size - overlap
    pieces: list[str] = []
    for start in range(0, len(text), step):
        piece = text[start:start + size]
        if piece.strip():
            pieces.append(piece)
        if start + size >= len(text):
            break
    return pieces


# ---------------------------------------------------------------------------
# 内部：带偏移的切分
#
# 设计稿里的 chunk_document 用 doc.text.find(piece, cursor) 反查位置，
# 但加了 overlap 前缀后 find 可能找不到（或找错位置）。所以内部一律用
# (文本, 内容起点, 内容终点) 三元组切分，偏移量从头就是准的。
# 对外暴露的 recursive_split / chunk_text 仍然返回纯文本，签名与文档一致。
# ---------------------------------------------------------------------------


def _split_keep_offsets(text: str, sep: str) -> list[tuple[str, int, int]]:
    """按 sep 切分，同时保留每段的 (文本, 起点, 终点)。空段会被丢掉。"""
    out: list[tuple[str, int, int]] = []
    start = 0
    while start <= len(text):
        i = text.find(sep, start)
        if i < 0:
            if start < len(text):
                out.append((text[start:], start, len(text)))
            break
        if i > start:
            out.append((text[start:i], start, i))
        start = i + len(sep)
    return out


def _atomic_units(text: str, code_ranges) -> list[tuple[str, int, int, bool]]:
    """把 Markdown 代码块切成「不可再分」的原子单元，其余文本是可再分片段。

    返回 (文本, 起点, 终点, 是否原子)。原子单元基本就是代码块（02 §4 思路 3：
    围栏内的文本按 \\n 切，绝不按句号拦腰斩断）。
    """
    units: list[tuple[str, int, int, bool]] = []
    cursor = 0
    for s, e in code_ranges:
        if s > cursor:
            units.append((text[cursor:s], cursor, s, False))
        if s < e:
            units.append((text[s:e], s, e, True))
        cursor = max(e, cursor)
    if cursor < len(text):
        units.append((text[cursor:], cursor, len(text), False))
    return [(t, s, e, atom) for t, s, e, atom in units if s < e and t.strip()]


def _force_split_offsets(text: str, size: int, overlap: int):
    """所有分隔符都切不动时的兜底：按字符硬切（带 overlap）。"""
    if not text.strip():
        return []
    out: list[tuple[str, int, int]] = []
    step = max(size - overlap, 1)
    for start in range(0, len(text), step):
        end = min(start + size, len(text))
        piece = text[start:end]
        if piece.strip():
            out.append((piece, start, end))
        if end >= len(text):
            break
    return out


def _merge_units(units: list[tuple[str, int, int, bool]], size: int):
    """贪心合并：把小段攒成不超过 size 的块。

    返回 [(内容起点, 内容终点), ...]，任一段都已是原子段或已短于 size。
    合并失败（有原子段比 size 还大，塞不进去）返回 None，交给下一级分隔符。
    """
    merged: list[tuple[int, int]] = []
    cur_start = cur_end = None
    for _text, s, e, atom in units:
        if (e - s) > size:
            # 代码块比 chunk_size 大，或者这一级分隔符剩下的片段本身就超长：
            # 都只能换更小一级的分隔符，最差兜底字符硬切。绝不能原样吐出超长块，
            # 那会让下游的「每块 ≤ size」约定失效（预算、top_k 全部失准）。
            return None
        if cur_start is None:
            cur_start, cur_end = s, e
            continue
        # 段与段之间可能夹着被丢掉的空行，补一个分隔符的长度
        gap = 1 if s > cur_end else 0
        if (cur_end - cur_start) + gap + (e - s) > size:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = s, e
        else:
            cur_end = e
    if cur_start is not None:
        merged.append((cur_start, cur_end))
    return merged


def _apply_overlap(text: str, ranges, overlap: int) -> list[tuple[str, int, int]]:
    """给相邻块补 overlap：把上一块尾部 overlap 个字符接到下一块开头。

    只在头部补、不补尾部是刻意的（02 §3.3）：这样边界上的内容会完整地出现在
    「后一个块」里，检索时至少有一个块是完整的，不会两边各剩半句。
    """
    out: list[tuple[str, int, int]] = []
    prev_content_end: int | None = None
    for start, end in ranges:
        head_start = start
        if prev_content_end is not None:
            head_start = max(0, min(start, prev_content_end) - overlap)
        chunk_text = text[head_start:end]
        if chunk_text.strip():
            out.append((chunk_text, start, end))
        prev_content_end = end
    return out


def _split_with_offsets(
    text: str,
    size: int,
    overlap: int,
    separators: tuple[str, ...] | list[str] | None = None,
    code_ranges=None,
) -> list[tuple[str, int, int]]:
    """递归分隔符切分，内部版：优先大边界，降级到强制切，全程保留字符偏移。"""
    if not text.strip():
        return []
    if len(text) <= size:
        return [(text, 0, len(text))]

    seps: tuple[str, ...] = tuple(separators) if separators else DEFAULT_SEPARATORS
    units = (_atomic_units(text, code_ranges) if code_ranges
             else [(text, 0, len(text), False)])

    for sep in seps:
        if sep not in text:
            continue
        parts: list[tuple[str, int, int, bool]] = []
        for unit_text, s, e, atom in units:
            if atom or len(unit_text) <= size:
                parts.append((unit_text, s, e, True))
            else:
                # 子段偏移量是相对 unit_text 的；unit_text 本身是 text[s:e]，
                # 所以子段起点可以直接当绝对偏移用（unit_text[s2:e2] == text[s + s2 : s + e2]）
                for sub_text, s2, e2 in _split_keep_offsets(unit_text, sep):
                    parts.append((sub_text, s2, e2, False))
        splittable = [p for p in parts if not p[3]]
        if len(splittable) < 2:
            continue                              # 这个分隔符切不动，降级到下一级
        merged = _merge_units(parts, size)
        if merged is None:
            continue                              # 有原子段放不下，换下一级
        result = _apply_overlap(text, merged, overlap)
        if result:
            return result

    return _force_split_offsets(text, size, overlap)


def recursive_split(
    text: str,
    size: int = 500,
    overlap: int = 80,
    separators: list[str] | None = None,
) -> list[str]:
    """递归分隔符切分（02 §4 设计稿签名，返回纯文本列表）。"""
    return [piece for piece, _s, _e in
            _split_with_offsets(text, size, overlap, separators)]


def chunk_text(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    """对外主入口。size 的单位是字符，overlap 同理（02 §3.3）。"""
    if size <= 0 or overlap < 0:
        raise ValueError("size 必须为正，overlap 不能为负")
    return recursive_split(text, size, overlap)


def chunk_document(
    doc: Document,
    size: int = 500,
    overlap: int = 80,
) -> list[Chunk]:
    """Document → list[Chunk]，逐块带上溯源信息（02 §3.1 / §4 设计稿）。

    chunk_id = f"{doc_id}-{index}"：内容哈希做前缀，文档一改块 ID 全变，
    重建索引是安全的覆盖式操作（和 01 章的幂等设计一脉相承）。
    """
    if size <= 0 or overlap < 0:
        raise ValueError("size 必须为正，overlap 不能为负")
    if overlap >= size:
        raise ValueError(f"overlap({overlap}) 必须小于 size({size})，否则切分会死循环")

    code_ranges = doc.metadata.get(META_CODE_RANGES) or None
    pieces = _split_with_offsets(doc.text, size, overlap, None, code_ranges)

    chunks: list[Chunk] = []
    prev_content_end: int | None = None
    for i, (piece, start, end) in enumerate(pieces):
        # start 是「真实内容」的起点；piece 可能比它长（前面带了 overlap 前缀）
        overlap_head = len(piece) - (end - start)
        metadata = {
            **doc.metadata,
            # source 是溯源的命脉：文档元数据里万一没带（手工构造 Document 就会），
            # 这里兜一层，绝不让它以 "unknown" 的形式流到 citations 里。
            META_SOURCE: doc.metadata.get(META_SOURCE, doc.source),
            META_START_CHAR: start,
            META_END_CHAR: end,
            META_START_LINE: line_number_of(doc.text, start),
            META_END_LINE: line_number_of(doc.text, end),
            "overlap_head": overlap_head,
            "tokens": estimate_tokens(piece),
        }
        if prev_content_end is not None and start < prev_content_end:
            metadata["overlaps_prev"] = True
        chunks.append(Chunk(
            chunk_id=f"{doc.doc_id}-{i}",
            doc_id=doc.doc_id,
            text=piece,
            index=i,
            metadata=metadata,
        ))
        prev_content_end = end
    return chunks
