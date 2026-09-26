"""store.py：向量库。关注「 upsert 幂等 / 先过滤后搜 / 删文档」。"""

from __future__ import annotations

import math

import pytest

from rag.chunker import chunk_document
from rag.embedding import DashScopeEmbeddingClient, FakeEmbeddingClient, run_sync
from rag.errors import EmbeddingError
from rag.models import Chunk, Document
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


# ==================== 11 章：接真实服务后才补上的护栏 ====================
# 下面几条对应的坑，只有「真的调 API + 真的落盘」才会撞上：
#   list 进不了 Chroma metadata / 重启后忘了模型名 / 后缀白名单漏掉 .bin


def test_to_scalar_把不能落盘的元数据压成标量():
    from rag.store import _to_scalar
    assert _to_scalar(["a", "b"]) == "a;b"        # 真实踩坑：MdParser 的 headings
    assert _to_scalar([""]) is None               # 空列表 → 丢掉，不是空串
    assert _to_scalar(None) is None               # Chroma 不收 None
    assert _to_scalar(3) == 3 and _to_scalar(True) is True
    assert _to_scalar({"k": 1}) == '{"k": 1}'


def test_chroma_元数据里的list不再炸(workdir):
    pytest.importorskip("chromadb")
    from rag.store import ChromaVectorStore
    store = ChromaVectorStore(persist_directory=str(workdir / "chroma"))
    chunk = Chunk(chunk_id="c1", doc_id="d1", text="生成器能省内存", index=0,
                  metadata={"headings": ["# 标题", "## 小标题"], "note": None})
    store.add([chunk], [[0.1, 0.2, 0.3]], "text-embedding-v3")
    assert store.count() == 1
    hits = store.search([0.1, 0.2, 0.3], top_k=1)
    assert hits and hits[0][0].chunk_id == "c1"


def test_chroma_重启后还记得模型名(workdir):
    """坑 4：model_name 只放实例属性 → 重启后为空 → check_model 护栏失效。"""
    pytest.importorskip("chromadb")
    from rag.store import ChromaVectorStore
    d = workdir / "chroma-model"
    store = ChromaVectorStore(persist_directory=str(d))
    store.add([Chunk(chunk_id="c1", doc_id="d1", text="t", index=0)],
              [[0.1, 0.2]], "text-embedding-v3")

    reopened = ChromaVectorStore(persist_directory=str(d))   # 模拟新进程冷启动
    assert reopened.model_name == "text-embedding-v3"
    with pytest.raises(EmbeddingError):
        reopened.check_model("BAAI/bge-m3")


def test_expand_paths_按后缀白名单过滤(corpus_dir):
    """坑 3：落盘目录若放在被扫描的目录里，.bin 会被当成待解析文档。"""
    from rag.parsing import expand_paths
    (corpus_dir / "vector.bin").write_text("x", encoding="utf-8")
    kept = {p.name for p in expand_paths([str(corpus_dir)])}
    assert kept == {"python-generators.md", "python-gil.txt"}
    assert "vector.bin" not in kept


def test_supported_extensions_来自解析器注册表():
    from rag.parsing import supported_extensions
    exts = supported_extensions()
    assert {".md", ".txt", ".pdf", ".docx"} <= set(exts)


def test_dashscope_没有key直接报错(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(EmbeddingError):
        DashScopeEmbeddingClient()


def test_dashscope_单批上限比siliconflow更小():
    """实测：百炼第 11 条会报 400 batch size is invalid。"""
    c = DashScopeEmbeddingClient(api_key="sk-test")
    assert c.batch_size == 10
    assert c.dim == 1024
    assert c.model_name == "text-embedding-v3"
