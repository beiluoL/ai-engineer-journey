"""reranker.py：两阶段检索的第二阶段（07 章）。

关键纪律：rerank 改的是**顺序与分数**，不是召回集合；分数语义和余弦分数不同。
"""

from __future__ import annotations

import pytest

from rag.errors import RerankError
from rag.models import Chunk, ScoredChunk
from rag.reranker import (BaseReranker, FakeReranker, LLMReranker, NoopReranker,
                          SiliconFlowReranker, _parse_ranking)
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


class _ScriptedLLM:
    """按调用次序返回预设文本的 LLM 替身（不联网）。"""

    model_name = "scripted"

    def __init__(self, replies):
        self._replies = list(replies)
        self.prompts: list[str] = []

    def chat(self, messages: list[dict]) -> str:
        self.prompts.append(messages[-1]["content"])
        return self._replies.pop(0) if self._replies else ""


def test_llm_rerank_按模型给的顺序重排():
    items = _scored([("装饰器", 0.9), ("生成器省内存", 0.8), ("yield 惰性", 0.7)])
    llm = _ScriptedLLM(["1,2,0"])
    out = LLMReranker(llm).rerank("生成器为什么省内存", items, top_n=3)
    assert [s.chunk.text for s in out] == ["生成器省内存", "yield 惰性", "装饰器"]
    # 分数只表达名次：严格递减即可，不要求等于任何余弦分
    assert out[0].score > out[1].score > out[2].score


def test_llm_rerank_输出解析不出时降级为原顺序():
    items = _scored([("a", 0.9), ("b", 0.8)])
    out = LLMReranker(_ScriptedLLM(["我觉得都差不多吧"])).rerank("q", items, top_n=2)
    assert [s.chunk.text for s in out] == ["a", "b"]


def test_llm_rerank_编号越界或重复要过滤掉():
    items = _scored([("a", 0.9), ("b", 0.8), ("c", 0.7)])
    out = LLMReranker(_ScriptedLLM(["2,2,99,0"])).rerank("q", items, top_n=3)
    # 2 在前、0 在后，剩下没被点名的 1 垫底；越界的 99 被丢弃
    assert [s.chunk.text for s in out] == ["c", "a", "b"]


def test_llm_rerank_超出max_candidates的候选不会被丢掉():
    items = _scored([(f"doc{i}", 0.9 - i * 0.01) for i in range(5)])
    out = LLMReranker(_ScriptedLLM(["1,0"]), max_candidates=2).rerank("q", items, top_n=5)
    assert len(out) == 5
    assert {s.chunk.text for s in out} == {f"doc{i}" for i in range(5)}


def test_llm_rerank_调用失败要显式报错():
    class _Boom:
        model_name = "boom"

        def chat(self, messages):
            raise RuntimeError("网络炸了")

    with pytest.raises(RerankError):
        LLMReranker(_Boom()).rerank("q", _scored([("a", 0.9)]), top_n=1)


def test_解析编号序列的边界():
    assert _parse_ranking("0,2,4", 5) == [0, 2, 4]
    assert _parse_ranking("[0] [2]", 5) == [0, 2]
    assert _parse_ranking("", 5) is None
    assert _parse_ranking("abc", 5) is None
    assert _parse_ranking("7,8", 3) is None        # 全越界 → 等于没解析出来
