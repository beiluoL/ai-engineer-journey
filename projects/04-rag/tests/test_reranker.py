"""reranker.py：两阶段检索的第二阶段（07 章）。

关键纪律：rerank 改的是**顺序与分数**，不是召回集合；分数语义和余弦分数不同。
"""

from __future__ import annotations

import pytest

from rag.errors import RerankError
from rag.models import Chunk, ScoredChunk
from rag.reranker import BaseReranker, FakeReranker, NoopReranker, SiliconFlowReranker
from rag.retriever import Retriever


def _scored(pairs):
    """pairs = [(文本, 余弦分), ...] → list[ScoredChunk]（模拟粗排结果）"""
    out = []
    for i, (text, score) in enumerate(pairs):
        chunk = Chunk(chunk_id=f"c{i}", doc_id="d", text=text, index=i,
                      metadata={"source": "kb/a.md"})
        out.append(ScoredChunk(chunk=chunk, score=score))
    return out


def test_base_是抽象类():
    with pytest.raises(TypeError):
        BaseReranker()


def test_noop_不改顺序只截断():
    items = _scored([("短", 0.9), ("中", 0.8), ("长", 0.7)])
    out = NoopReranker().rerank("q", items, top_n=2)
    assert [s.score for s in out] == [0.9, 0.8]            # 原顺序保留


def test_fake_能改顺序并覆写分数():
    items = _scored([("生成器能省内存", 0.91), ("GIL 是一把锁", 0.89)])
    out = FakeReranker().rerank("生成器", items, top_n=2)
    assert out[0].chunk.text == "生成器能省内存"             # 关键词命中高的浮上来
    assert out[0].score != 0.91                            # 分数被精排语义覆写


def test_fake_不修改传入列表():
    items = _scored([("生成器能省内存", 0.91), ("GIL 是一把锁", 0.89)])
    before = [s.chunk.chunk_id for s in items]
    FakeReranker().rerank("生成器", items, top_n=1)
    assert [s.chunk.chunk_id for s in items] == before


def test_fake_空输入返回空():
    assert FakeReranker().rerank("生成器", [], top_n=5) == []


def test_top_n_比候选多时不报错():
    items = _scored([("生成器能省内存", 0.9)])
    assert len(FakeReranker().rerank("生成器", items, top_n=10)) == 1


def test_siliconflow_没有key直接报错():
    with pytest.raises(RerankError):
        SiliconFlowReranker(api_key="")


def test_fake_排序稳定可复现():
    items = _scored([("生成器省内存", 0.5), ("yield 让函数边算边吐", 0.4)])
    assert [s.chunk.text for s in FakeReranker().rerank("生成器", items, top_n=2)] == \
        [s.chunk.text for s in FakeReranker().rerank("生成器", items, top_n=2)]


def test_rerank_插进链路_只改变顺序不改集合(fake_store, fake_client):
    store, _chunks = fake_store
    retriever = Retriever(embedding_client=fake_client, vector_store=store)
    hits = retriever.retrieve("生成器省内存", top_k=3)
    recalled = {h.chunk_id for h in hits}
    after = FakeReranker().rerank("生成器省内存", hits, top_n=2)
    assert len(after) == 2 and {s.chunk_id for s in after} <= recalled
