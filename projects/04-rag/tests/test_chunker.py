"""chunker.py：切分。几条最容易回归的性质：
    ① 不丢内容（块的并集覆盖原文）；② 内容段不超 size；③ overlap 真的有重叠。
"""

from __future__ import annotations

import pytest

from rag.chunker import (chunk_document, chunk_text, estimate_tokens,
                        recursive_split, split_with_overlap)
from rag.models import Document

TEXT = "。".join(f"第{i}句话，讲的是 Python 生成器的内存占用问题。" for i in range(6))


def test_estimate_tokens_按字符粗估():
    assert estimate_tokens("a" * 160) == 100
    assert estimate_tokens("") <= 1                        # 空串不该炸


def test_chunk_text_不丢内容():
    pieces = chunk_text(TEXT, size=100, overlap=20)
    assert len(pieces) > 1
    joined = "".join(pieces)
    for marker in ("第0句话", "第5句话"):                    # 首尾都在 → 没把内容吃掉
        assert marker in joined


def test_chunk_text_参数非法直接报错():
    with pytest.raises(ValueError):
        chunk_text("x", size=0)
    with pytest.raises(ValueError):
        chunk_text("x", size=100, overlap=-1)


def test_split_with_overlap_产生重叠():
    pieces = split_with_overlap("abcdefghij", size=5, overlap=3)
    assert pieces[0] == "abcde"
    assert pieces[1].startswith("cdef")                    # 第二块带上了重叠前缀


def test_recursive_split_内容段不超size():
    pieces = recursive_split(TEXT, size=120, overlap=0)
    assert pieces and all(len(p) <= 120 for p in pieces)


def test_recursive_split_降级顺序_中文标点先于英文句点():
    # "第二句.第三句" 里的英文句点不是句子边界；中文句号才是
    text = "第一句。第二句.第三句。"
    pieces = recursive_split(text, size=6, overlap=0)
    assert all(len(p) <= 6 for p in pieces)
    assert "".join(pieces) == text


def test_chunk_document_id与溯源信息():
    doc = Document(doc_id="d1", source="kb/x.md", text=TEXT, metadata={"format": "md"})
    chunks = chunk_document(doc, size=100, overlap=20)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].chunk_id == "d1-0"
    assert chunks[0].doc_id == "d1"
    assert chunks[1].metadata["source"] == "kb/x.md"        # 文档元数据跟着块走
    assert chunks[1].metadata["start_char"] > 0             # 块在原文中的位置
    assert chunks[1].metadata["start_line"] >= 1
    assert chunks[1].metadata["overlap_head"] > 0           # 这块带上一块的尾巴


def test_chunk_document_文档元数据缺失时兜住source():
    doc = Document(doc_id="d2", source="kb/y.md", text="短文本")
    chunks = chunk_document(doc, size=500, overlap=80)
    assert len(chunks) == 1
    assert chunks[0].metadata["source"] == "kb/y.md"        # 不能变成 "unknown"


def test_chunk_document_块id由文档id加序号():
    doc = Document(doc_id="d3", source="kb/z.md", text="短文本")
    chunks = chunk_document(doc, size=500, overlap=80)
    assert chunks[0].chunk_id == "d3-0"


def test_overlap_必须小于size():
    doc = Document(doc_id="d4", source="kb/w.md", text="x" * 100)
    with pytest.raises(ValueError):
        chunk_document(doc, size=50, overlap=50)           # overlap==size 会死循环
