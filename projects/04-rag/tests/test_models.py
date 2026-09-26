"""models.py：两个 id 的约定（01/02 章已发布，不要改）。"""

from __future__ import annotations

from rag.models import Chunk, Document, ScoredChunk


def test_document_id_来自内容哈希_同文本同_id():
    a = Document(doc_id="abc", source="a.md", text="一样的正文")
    b = Document(doc_id="abc", source="b.md", text="一样的正文")
    assert a.doc_id == b.doc_id and a.source != b.source


def test_document_字符数与行数():
    doc = Document(doc_id="d", source="d.md", text="a\nb\nc")
    assert doc.char_count == 5
    assert doc.line_count == 3


def test_chunk_id_由文档id加序号组成():
    doc = Document(doc_id="deadbeef", source="x.md", text="hello")
    chunk = Chunk(chunk_id=f"{doc.doc_id}-0", doc_id=doc.doc_id, text="hello", index=0)
    assert chunk.chunk_id == "deadbeef-0"


def test_chunk_source_从元数据取_取不到给占位():
    chunk = Chunk(chunk_id="c", doc_id="d", text="t", index=0,
                  metadata={"source": "kb/a.md"})
    assert chunk.source == "kb/a.md"
    assert Chunk(chunk_id="c", doc_id="d", text="t", index=0).source == "unknown"


def test_scored_chunk_便捷属性透传给_chunk():
    chunk = Chunk(chunk_id="c-1", doc_id="d", text="t", index=1, metadata={"source": "a.md"})
    sc = ScoredChunk(chunk=chunk, score=0.73)
    assert sc.chunk_id == "c-1"
    assert sc.source == "a.md"
    assert sc.score == 0.73
