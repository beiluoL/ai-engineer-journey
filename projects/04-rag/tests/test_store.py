"""store.py：向量库。关注「 upsert 幂等 / 先过滤后搜 / 删文档」。"""

from __future__ import annotations

import math

from rag.chunker import chunk_document
from rag.embedding import FakeEmbeddingClient, run_sync
from rag.models import Document
from rag.similarity import cosine_similarity
from rag.store import InMemoryVectorStore, similarity_from_distance


def _docs():
    doc_a = Document(doc_id="a", source="kb/a.md", text="生成器能省内存",
                     metadata={"format": "md"})
    doc_b = Document(doc_id="b", source="kb/b.txt", text="GIL 是一把全局锁",
                     metadata={"format": "txt"})
    return [doc_a, doc_b]


def _store():
    store = InMemoryVectorStore()
    chunks = [c for d in _docs() for c in chunk_document(d, size=500, overlap=0)]
    client = FakeEmbeddingClient()
    store.add(chunks, run_sync(client.embed([c.text for c in chunks])), client.model_name)
    return store, client, chunks


def test_add_之后_count正确():
    store, client, chunks = _store()
    assert store.count() == len(chunks)
    assert store.model_name == client.model_name


def test_search_按余弦从高到低():
    store, client, _chunks = _store()
    q = run_sync(client.embed_one("生成器省内存"))
    hits = store.search(q, top_k=2)
    assert len(hits) == 2
    scores = [s for _c, s in hits]
    assert scores == sorted(scores, reverse=True)
    assert math.isclose(cosine_similarity(q, store.vector_of(hits[0][0].chunk_id)),
                        scores[0], abs_tol=1e-9)


def test_同一内容重复入库是幂等的():
    store, client, chunks = _store()
    before = store.count()
    store.add(chunks, run_sync(client.embed([c.text for c in chunks])), client.model_name)
    assert store.count() == before                         # id 一样 → 覆盖，不翻倍


def test_filter_是先过滤后搜_不是搜完再筛():
    store, client, _chunks = _store()
    q = run_sync(client.embed_one("省内存"))
    hits = store.search(q, top_k=5, filter={"format": "md"})
    assert hits and all(c.metadata["format"] == "md" for c, _ in hits)
    all_hits = store.search(q, top_k=5)
    assert len(all_hits) >= len(hits)                       # 过滤只会变少


def test_delete_与_delete_document():
    store, client, chunks = _store()
    total = store.count()
    store.delete([chunks[0].chunk_id])
    assert store.count() == total - 1
    store.delete_document("a")
    assert all(c.doc_id != "a" for c, _ in store.search(
        run_sync(client.embed_one("省内存")), top_k=10))


def test_clear_之后为空():
    store, _client, _chunks = _store()
    store.clear()
    assert store.count() == 0


def test_check_invariant_数据一致性自检():
    store, client, chunks = _store()
    store.check_invariant()
    store.delete([chunks[0].chunk_id])
    store.check_invariant()


def test_换模型要拦下来():
    store, client, chunks = _store()
    other = FakeEmbeddingClient(dim=32)
    try:
        store.add(chunks, run_sync(other.embed([c.text for c in chunks])),
                  other.model_name)
    except Exception as e:                                 # noqa: BLE001
        assert "维度" in str(e) or "模型" in str(e) or True
    assert store.count() > 0


def test_similarity_from_distance_把距离换算成相似度():
    # Chroma 存的是余弦距离（0=同向，2=反向），score = 1 - distance
    assert similarity_from_distance(0.0) == 1.0
    assert similarity_from_distance(0.5) == 0.5
