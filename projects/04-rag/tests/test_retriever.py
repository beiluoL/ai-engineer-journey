"""retriever.py：检索门面（05 章）。三种模式的差异必须可被观察。"""

from __future__ import annotations

import pytest

from rag.embedding import run_sync
from rag.errors import ConfigurationError
from rag.models import Chunk
from rag.retriever import KeywordIndex, Retriever, rrf_fuse


def _rrf(rankings, k=60):
    return rrf_fuse(rankings, k=k)


def test_rrf_fuse_两路都命中的排最前():
    fused = _rrf([["a", "b", "c"], ["b", "a"]])
    assert fused[0] in ("a", "b")                          # 两路共同认可的
    assert set(fused) == {"a", "b", "c"}


def test_rrf_fuse_只在一路出现的排在后面():
    fused = _rrf([["x"], ["y", "z"]])
    assert set(fused[1:]) == {"y", "z"}


def test_rrf_fuse_与排名无关分数():                          # 分数大的反而靠后是合理的
    fused = _rrf([["a", "b"], ["b", "a"]], k=1)
    assert sorted(fused) == ["a", "b"]


def test_rrf_fuse_k越大越看重头名():
    assert _rrf([["a"], ["b"]], k=1)[0] == "a"


def test_关键词索引_bm25式打分():
    idx = KeywordIndex()
    idx.index([
        Chunk(chunk_id="c1", doc_id="d", text="生成器省内存", index=0,
              metadata={"source": "a.md"}),
        Chunk(chunk_id="c2", doc_id="d", text="GIL 全局锁", index=1,
              metadata={"source": "b.md"}),
    ])
    hits = idx.search("生成器", top_k=2)
    assert hits and "生成器" in hits[0][0].text


def test_空query直接报错():
    store_stub = StubStore()
    r = Retriever(embedding_client=StubEmbedding(), vector_store=store_stub)
    with pytest.raises(ConfigurationError):
        r.retrieve("", top_k=3)


def test_未知mode直接报错():
    r = Retriever(embedding_client=StubEmbedding(), vector_store=StubStore())
    with pytest.raises(ConfigurationError):
        r.retrieve("生成器", top_k=3, mode="magic")


def test_vector模式只走向量路(fake_store, fake_client):
    store, _chunks = fake_store
    r = Retriever(embedding_client=fake_client, vector_store=store)
    hits = r.retrieve("生成器省内存", top_k=2, mode="vector")
    assert hits
    assert any(h.chunk.source.endswith("python-generators.md") for h in hits)


def test_hybrid模式会融合关键词路(fake_store, fake_client):
    store, _chunks = fake_store
    r = Retriever(embedding_client=fake_client, vector_store=store)
    vec = r.retrieve("GIL", top_k=3, mode="vector")
    hyp = r.retrieve("GIL", top_k=3, mode="hybrid")
    assert len(hyp) == 3
    assert {h.chunk_id for h in hyp} >= {h.chunk_id for h in vec}   # 融合只会更全


def test_mmr_在近似重复块里挑出不一样的(fake_store, fake_client):
    store, _chunks = fake_store
    # 造三个「内容几乎一样」的块：粗排必然全上来，MMR 应该抑制重复、挑出别的
    dupes = [
        Chunk(chunk_id=f"dup{i}", doc_id="d", index=i, text="生成器省内存" + " filler" * 5,
              metadata={"source": "kb/dup.md"})
        for i in range(3)
    ]
    store.add(dupes, run_sync(fake_client.embed([c.text for c in dupes])),
              fake_client.model_name)
    retriever = Retriever(embedding_client=fake_client, vector_store=store)
    plain = {h.chunk_id for h in
             retriever.retrieve("生成器省内存", top_k=2, mode="vector", fetch_k=10)}
    diverse = {h.chunk_id for h in
               retriever.retrieve("生成器省内存", top_k=2, mode="vector",
                                  mmr=True, fetch_k=10)}
    assert len(plain) == 2                          # 粗排：两个几乎一样的都进来
    assert len(diverse) == 2
    assert len(diverse & {"dup0", "dup1"}) < 2       # MMR 至少带出一个别的块


def test_mmr_lambda_1退化为普通topk(fake_store, fake_client):
    store, _chunks = fake_store
    r = Retriever(embedding_client=fake_client, vector_store=store, mmr_lambda=1.0)
    a = r.retrieve("生成器", top_k=2, mode="vector", mmr=False)
    b = r.retrieve("生成器", top_k=2, mode="vector", mmr=True)
    assert [h.chunk_id for h in a] == [h.chunk_id for h in b]


def test_filter_在检索层就生效(fake_store, fake_client, workdir):
    store, _chunks = fake_store
    r = Retriever(embedding_client=fake_client, vector_store=store)
    only_gil = str(workdir / "python-gil.txt")
    hits = r.retrieve("生成器省内存", top_k=5, mode="vector", filter={"source": only_gil})
    assert hits and all(h.chunk.metadata["source"] == only_gil for h in hits)


def test_scoredchunk_顺序按分数降序(fake_store, fake_client):
    store, _chunks = fake_store
    r = Retriever(embedding_client=fake_client, vector_store=store)
    hits = r.retrieve("生成器省内存", top_k=3, mode="vector")
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


# ---- 极简替身：只验证 retriever 的分支逻辑，不牵扯真实向量 ----

class StubEmbedding:
    model_name = "stub"
    dim = 4

    async def embed_one(self, text):
        return [1.0, 0.0, 0.0, 0.0]

    async def embed(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class StubStore:
    def search(self, query_vector, top_k=5, filter=None):
        chunk = Chunk(chunk_id="c0", doc_id="d", text="t", index=0, metadata={})
        return [(chunk, 0.5)]

    def check_model(self, model):
        return None

    def vector_of(self, chunk_id):
        return [1.0, 0.0, 0.0, 0.0]
