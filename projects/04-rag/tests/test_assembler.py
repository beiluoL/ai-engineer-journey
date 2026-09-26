"""assembler.py：组装成「可追源的 prompt」（08 章）。

三条纪律逐条验证：编号与引用同源、低于阈值的丢掉、预算不够就截断（不硬塞）。
"""

from __future__ import annotations

from rag.assembler import ContextAssembler, RAG_SYSTEM_RULES
from rag.chunker import chunk_document
from rag.models import Chunk, Document, ScoredChunk


def _hits():
    docs = [Document(doc_id=f"d{i}", source=f"kb/{i}.md", text=body,
                     metadata={"format": "md"})
            for i, body in enumerate(["生成器省内存的一段话。",
                                      "GIL 是一把全局锁的一段话。",
                                      "token 与字符换算的一段话。"])]
    chunks = [c for d in docs for c in chunk_document(d, size=500, overlap=0)]
    return [ScoredChunk(chunk=c, score=s)
            for c, s in zip(chunks, (0.9, 0.8, 0.7))]


def test_system规则三条齐备():
    # 三条规则：只依据资料 / 编号引用 / 资料不足要明说「知识库中没有相关资料」
    assert "只依据" in RAG_SYSTEM_RULES
    assert "编号" in RAG_SYSTEM_RULES
    assert "知识库中没有相关资料" in RAG_SYSTEM_RULES


def test_编号_citation_与正文同源():
    ctx = ContextAssembler().build("q", _hits(), 4000)
    body_nos = [int(line[1]) for line in ctx.context_text.splitlines()
                if line.startswith("[") and line[1].isdigit()]
    assert body_nos == list(range(1, len(ctx.citations) + 1))
    assert [c.no for c in ctx.citations] == body_nos
    assert ctx.n_used == len(ctx.used_chunks) == len(ctx.citations)


def test_每条资料都带source_for_溯源():
    ctx = ContextAssembler().build("q", _hits(), 4000)
    assert "(source: kb/0.md" in ctx.context_text
    assert ctx.citations[0].source == "kb/0.md"
    assert ctx.citations[0].anchor().startswith("kb/0.md#L")


def test_低于min_score的不进prompt():
    hits = _hits()
    ctx = ContextAssembler(min_score=0.85).build("q", hits, 4000)
    assert [round(h.score, 2) for h in ctx.used_chunks] == [0.9]   # 分数是有序的，装不下就停


def test_预算不够就截断_不硬塞():
    ctx = ContextAssembler().build("q", _hits(), 0)
    assert ctx.used_chunks == [] and ctx.context_text == "" and ctx.context_tokens == 0

    ctx = ContextAssembler().build("q", _hits(), 1)
    assert len(ctx.used_chunks) <= 1                      # 塞不下就停，绝不切一半拼上去


def test_预算够时全装下():
    ctx = ContextAssembler().build("q", _hits(), 10_000)
    assert len(ctx.used_chunks) == len(_hits())


def test_去重_内容相同的块只装一次():
    hits = _hits()
    dup = hits + [hits[0]]                                 # 同一块被两个检索路召回
    ctx = ContextAssembler().build("q", dup, 4000)
    assert ctx.n_used == len(hits)


def test_assemble_是build的别名():
    a = ContextAssembler()
    assert a.assemble("q", _hits(), 4000).context_text == a.build("q", _hits(), 4000).context_text


def test_空输入不炸():
    ctx = ContextAssembler().build("q", [], 4000)
    assert ctx.n_used == 0 and ctx.context_text == ""


def test_块没有行号时用字符区间兜底():
    chunk = Chunk(chunk_id="c", doc_id="d", text="内容", index=0, metadata={"source": "a.md"})
    ctx = ContextAssembler().build("q", [ScoredChunk(chunk=chunk, score=0.9)], 1000)
    assert "(source: a.md#char-0-2)" in ctx.context_text
