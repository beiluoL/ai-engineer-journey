"""可观测性的测试（milestone 15）。

这类代码最容易错的地方不是算法，而是**口径**：
    - 计数会不会在并发下丢
    - 失败的请求有没有被记进耗时
    - 「含重试」和「单次调用」是不是两个不同的指标
所以测试基本上是围绕这三点写的。
"""

from __future__ import annotations

import asyncio
import os
import threading

import pytest

os.environ.setdefault("RAG_FAKE", "1")

from rag.embedding import BaseEmbeddingClient                      # noqa: E402
from rag.errors import EmbeddingError, RAGError                    # noqa: E402
from rag.llm import BaseLLMClient                                  # noqa: E402
from rag.metrics import (                                          # noqa: E402
    Names, MetricsRegistry, MeteredEmbeddingClient, MeteredLLMClient,
    bucketize, percentile, render_diff, render_report, summarize,
)


# --------------------------------------------------------------------------
# 统计函数
# --------------------------------------------------------------------------

def test_分位数在样本少时线性插值而不是取已有值():
    assert percentile([], 0.9) == 0.0
    assert percentile([5.0], 0.9) == 5.0
    # 两点 [0, 10] 的 p50 必须是 5：nearest-rank 会给出 0 或 10，那是错的
    assert percentile([0.0, 10.0], 0.5) == 5.0
    assert percentile([0.0, 10.0], 0.9) == 9.0


def test_摘要统计字段齐全():
    s = summarize("x", [1.0, 2.0, 3.0, 4.0], unit="ms")
    assert s.count == 4 and s.mean == pytest.approx(2.5)
    assert s.min == 1.0 and s.max == 4.0
    assert s.to_dict()["unit"] == "ms"


def test_空样本的摘要不炸():
    s = summarize("x", [], unit="ms")
    assert s.count == 0 and s.mean == 0.0


def test_分桶按边界切且总数守恒():
    values = [0.1, 0.25, 0.5, 0.95]
    rows = bucketize(values)
    assert sum(n for _, n in rows) == len(values)
    assert rows[0][1] == 1      # [0.0, 0.2)  → 0.1
    assert rows[1][1] == 1      # [0.2, 0.4)  → 0.25
    assert rows[2][1] == 1      # [0.4, 0.6)  → 0.5
    assert rows[3][1] == 0      # [0.6, 0.8)  → 空桶，别因为没数据就把边界挪了
    assert rows[4][1] == 1      # [0.8, 1.01) → 0.95


# --------------------------------------------------------------------------
# 注册表
# --------------------------------------------------------------------------

def test_计数与耗时各归各位():
    reg = MetricsRegistry()
    reg.inc(Names.REQUESTS)
    reg.inc(Names.REQUESTS, 2)
    reg.observe("t", 0.5)
    snap = reg.snapshot()
    assert snap["counters"][Names.REQUESTS] == 3
    assert snap["timings"]["t"]["count"] == 1
    assert snap["timings"]["t"]["mean"] == pytest.approx(0.5)


def test_并发计数不丢():
    """Web API 下 /ask 是 to_thread 跑的，多线程 inc 必须不丢。

    不加锁时 dict 的 += 是非原子的，这个用例会随机失败——
    所以这里把线程数开到 20、每线程 500 次，让丢计数无处可藏。
    """
    reg = MetricsRegistry()
    threads = [threading.Thread(target=lambda: [reg.inc("k") for _ in range(500)])
               for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert reg.counter("k") == 20 * 500


def test_计时器在异常时也要记():
    """失败的请求往往是最慢的那次，只记成功会把 p99 洗得很好看。"""
    reg = MetricsRegistry()
    with pytest.raises(RAGError):
        with reg.timer("boom"):
            raise RAGError("炸了")
    assert reg.snapshot()["timings"]["boom"]["count"] == 1


def test_分数为空时不产生空桶():
    reg = MetricsRegistry()
    reg.observe_scores(Names.RETRIEVE_SCORE, [])
    assert reg.snapshot()["scores"] == {}


def test_reset清空所有样本():
    reg = MetricsRegistry()
    reg.inc("a"); reg.observe("b", 1.0)
    reg.reset()
    snap = reg.snapshot()
    assert snap["counters"] == {} and snap["timings"] == {}


# --------------------------------------------------------------------------
# 计量壳
# --------------------------------------------------------------------------

class _DummyEmbedding(BaseEmbeddingClient):
    model_name = "dummy"
    dim = 3

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _BoomEmbedding(_DummyEmbedding):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("boom")


def test_计量壳转发结果并记批大小():
    reg = MetricsRegistry()
    wrapped = MeteredEmbeddingClient(_DummyEmbedding(), reg)
    assert wrapped.model_name == "dummy"
    assert wrapped.inner is not None
    out = asyncio.run(wrapped.embed(["a", "b", "c"]))
    assert len(out) == 3
    assert reg.counter(Names.EMBED_CALLS) == 1
    assert reg.counter(Names.EMBED_TEXTS) == 3      # 钱是按条算的，不是按批
    assert reg.snapshot()["timings"][Names.EMBED_LATENCY]["count"] == 1


def test_计量壳记失败且失败也要记耗时():
    reg = MetricsRegistry()
    wrapped = MeteredEmbeddingClient(_BoomEmbedding(), reg)
    with pytest.raises(EmbeddingError):
        asyncio.run(wrapped.embed(["x"]))
    assert reg.counter(Names.EMBED_ERRORS) == 1
    assert reg.snapshot()["timings"][Names.EMBED_LATENCY]["count"] == 1


class _ChunkedLLM(BaseLLMClient):
    model_name = "chunked"

    def chat(self, messages: list[dict]) -> str:
        return "甲乙丙"

    def iter_tokens(self, messages: list[dict]):
        yield from ["甲", "乙", "丙"]


class _BoomLLM(BaseLLMClient):
    model_name = "boom-llm"

    def chat(self, messages: list[dict]) -> str:
        raise RAGError("llm 炸了")


def test_计量壳记流式帧数():
    reg = MetricsRegistry()
    wrapped = MeteredLLMClient(_ChunkedLLM(), reg)
    assert "".join(wrapped.iter_tokens([])) == "甲乙丙"
    assert reg.counter(Names.LLM_CALLS) == 1
    assert reg.counter(Names.LLM_CHUNKS) == 3


def test_计量壳记LLM失败():
    reg = MetricsRegistry()
    wrapped = MeteredLLMClient(_BoomLLM(), reg)
    with pytest.raises(RAGError):
        wrapped.chat([])
    assert reg.counter(Names.LLM_ERRORS) == 1
    assert reg.snapshot()["timings"][Names.LLM_LATENCY]["count"] == 1


# --------------------------------------------------------------------------
# 报告渲染
# --------------------------------------------------------------------------

def test_报告渲染含判读且能跑在空快照上():
    assert "计数器" in render_report({})
    reg = MetricsRegistry()
    reg.inc(Names.REQUESTS, 4)
    reg.inc(Names.REFUSALS, 3)          # 拒答率 75% → 应触发判读
    # 9 次快 + 1 次很慢：p50 仍是 0.1，p99 接近 2.0 → 比值远大于 5，触发抖动判读
    for _ in range(9):
        reg.observe(Names.REQUEST_LATENCY, 0.1)
    reg.observe(Names.REQUEST_LATENCY, 2.0)
    reg.observe_scores(Names.RETRIEVE_SCORE, [0.1, 0.5, 0.9])
    text = render_report(reg.snapshot())
    assert "拒答率 75.0%" in text
    assert "抖动" in text
    assert "会被 min_score 拦掉" in text


# --------------------------------------------------------------------------
# 端到端：service 真的在记
# --------------------------------------------------------------------------

def _service(min_score: float = 0.2):
    """离线装配一个 service。

    min_score 是在 ContextAssembler 构造时定死的（不是每次 build 读 settings），
    所以要造「检索为空」只能换掉 assembler —— 这个事实本身就值得记一笔：
    改了 settings.min_score 却没重建 assembler，闸门其实是没变的。
    """
    from pathlib import Path

    from rag.assembler import ContextAssembler
    from rag.cli import build_components
    data_dir = Path(__file__).resolve().parents[1] / "data"
    _settings, _emb, _store, _ret, svc = build_components(
        profile="dev", fake=True, top_k=5, index_paths=[str(data_dir)])
    if min_score != 0.2:
        svc._assembler = ContextAssembler(min_score=min_score)
    return svc


def test_一次问答记下四段耗时与分数分布():
    svc = _service()
    svc.metrics.reset()          # 建索引那批 embedding 调用不算进问答指标
    svc.ask("生成器为什么能省内存？")
    snap = svc.metrics.snapshot()
    assert snap["counters"][Names.REQUESTS] == 1
    assert snap["counters"].get(Names.REFUSALS, 0) == 0
    for key in (Names.REQUEST_LATENCY, Names.RETRIEVE_LATENCY,
                Names.RERANK_LATENCY, Names.ASSEMBLE_LATENCY, Names.GENERATE_LATENCY):
        assert snap["timings"][key]["count"] == 1, f"{key} 没被记到"
    assert snap["scores"][Names.RETRIEVE_SCORE]["count"] > 0


def test_拒答请求一次LLM都不调():
    """失败语义 2 的省钱效果，用指标直接量化：llm.calls 必须是 0。"""
    svc = _service(min_score=1.01)         # 让所有召回都过不了闸门
    svc.metrics.reset()
    answer = svc.ask("生成器为什么能省内存？")
    snap = svc.metrics.snapshot()
    assert answer.refused is True
    assert snap["counters"][Names.REFUSALS] == 1
    assert snap["counters"].get(Names.LLM_CALLS, 0) == 0
    assert snap["timings"].get(Names.GENERATE_LATENCY) is None


def test_指标能从stats端点读到():
    from fastapi.testclient import TestClient

    from rag.api import create_app
    with TestClient(create_app(["data/"])) as c:
        c.post("/ask", json={"query": "生成器为什么能省内存？"})
        body = c.get("/stats").json()
    assert "metrics" in body
    assert body["metrics"]["counters"][Names.REQUESTS] >= 1


def test_落盘再读回_数字一致(tmp_path):
    reg = MetricsRegistry()
    reg.inc(Names.REQUESTS, 3)
    reg.observe(Names.REQUEST_LATENCY, 0.25)
    p = reg.save(tmp_path / "sub" / "m.json", meta={"fake": True})
    assert p.exists()

    loaded = MetricsRegistry.load(p)
    assert loaded["meta"] == {"fake": True}
    assert loaded["snapshot"]["counters"][Names.REQUESTS] == 3
    # 快照内部一律存秒（渲染时才 ×1000）。落盘也存秒，跨进程回读不会串量纲。
    assert loaded["snapshot"]["timings"][Names.REQUEST_LATENCY]["p50"] == 0.25


def test_落盘摘要不含原始样本(tmp_path):
    """只存摘要不存原始样本：文件要小，也避免把单条请求数据写到盘上。"""
    reg = MetricsRegistry()
    for i in range(50):
        reg.observe(Names.REQUEST_LATENCY, 0.1 + i * 0.01)
    p = reg.save(tmp_path / "m.json")
    text = p.read_text(encoding="utf-8")
    assert "0.1" in text or True          # 摘要里允许出现统计值
    assert len(text) < 4000               # 50 个样本若全落盘会远超这个量级
    assert MetricsRegistry.load(p)["snapshot"]["timings"][
        Names.REQUEST_LATENCY]["count"] == 50


def test_跨进程对比_变慢要能报出来():
    base = {"saved_at": "T0", "meta": {}, "snapshot": {
        "counters": {Names.REQUESTS: 10, Names.LLM_CALLS: 10},
        "timings": {Names.REQUEST_LATENCY: {"p50": 1000.0, "p90": 2000.0}},
        "scores": {}}}
    curr = {"saved_at": "T1", "meta": {}, "snapshot": {
        "counters": {Names.REQUESTS: 20, Names.LLM_CALLS: 20},
        "timings": {Names.REQUEST_LATENCY: {"p50": 1500.0, "p90": 3000.0}},
        "scores": {}}}
    text = render_diff(base, curr)
    assert "变慢 50%" in text        # p50 1000 → 1500
    assert "⚠ 需要关注" in text
    # 计数器折算成「每次请求」：10/10=1.0 vs 20/20=1.0 → 持平，不能被总量骗到
    assert "持平" in text


def test_跨进程对比_小幅波动不报警():
    base = {"snapshot": {"counters": {Names.REQUESTS: 10},
                         "timings": {Names.REQUEST_LATENCY: {"p50": 1000.0}}}}
    curr = {"snapshot": {"counters": {Names.REQUESTS: 10},
                         "timings": {Names.REQUEST_LATENCY: {"p50": 1050.0}}}}
    text = render_diff(base, curr)
    assert "无指标恶化" in text       # +5% 落在 20% 容忍带内
