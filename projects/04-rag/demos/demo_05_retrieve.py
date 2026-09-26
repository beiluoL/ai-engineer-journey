"""05 章：同一个问题，三种检索模式的结果对比（vector / hybrid / mmr）。

为什么值得单独跑一次：三种模式的**召回集合**差别很大，而 top1 常常又是同一个
—— 只看 top1 会误以为"模式无所谓"。这里把三组 chunk_id 列表都打出来对比。
"""

from __future__ import annotations

from common import head, note, rule

from rag.cli import build_components
from rag.embedding import run_sync
from rag.retriever import Retriever
from rag.similarity import cosine_similarity

QUERIES = ["生成器为什么能省内存", "GIL 对多线程 CPU 密集任务有什么影响"]
FETCH_K = 20                      # 粗召回数量：hybrid 要两路各取这么多再融合


def _table(hits, mmr: bool = False, rel_of=None) -> None:
    for rank, h in enumerate(hits, start=1):
        # MMR 表多一列"相关度"：MMR 分数是 λ·相关 − (1−λ)·重复惩罚，
        # 它天然不随排名单调（第 3 名可以比第 4 名分数低），别误读成排序错了。
        extra = ""
        if mmr and rel_of is not None:
            extra = f" rel={rel_of(h):.4f}"
        print(f"    #{rank} {h.score:.4f}{extra}  {h.chunk.source.split('/')[-1]:<26}"
              f"chunk#{h.chunk.index}  {h.chunk.text[:30]!r}")


def main() -> int:
    head("python demos/demo_05_retrieve.py")
    settings, embedding, store, retriever, _svc = build_components(
        profile="dev", fake=True, top_k=5, index_paths=["data/"])
    assert isinstance(retriever, Retriever) and store.count() > 0

    for q in QUERIES:
        print(f"\n问题：{q}")
        rule("vector（只走向量路）")
        vec = retriever.retrieve(q, top_k=5, mode="vector", fetch_k=FETCH_K)
        _table(vec)

        rule("hybrid（向量 + 关键词，RRF 融合，rrf_k=60）")
        hybrid = retriever.retrieve(q, top_k=5, mode="hybrid", fetch_k=FETCH_K)
        _table(hybrid)

        rule("vector + mmr=True（λ=0.7，抑制近似重复、提高多样性）")
        mmr = retriever.retrieve(q, top_k=5, mode="vector", mmr=True, fetch_k=FETCH_K)
        qvec = run_sync(retriever.embedding_client.embed_one(q))

        def rel_of(h, _qvec=qvec):
            return cosine_similarity(_qvec, retriever.vector_store.vector_of(h.chunk_id))

        _table(mmr, mmr=True, rel_of=rel_of)

        rule("三种模式的差异统计")
        ids = {"vector": [h.chunk_id for h in vec],
               "hybrid": [h.chunk_id for h in hybrid],
               "mmr": [h.chunk_id for h in mmr]}
        for name in ("vector", "hybrid", "mmr"):
            print(f"    {name:<7} = {ids[name]}")
        vec_set, hyb_set = set(ids["vector"]), set(ids["hybrid"])
        print(f"    vector ⊆ hybrid ? {vec_set <= hyb_set}"
              f"（RRF 取两路并集，但融合结果仍要按 fetch_k={FETCH_K} 截断）")
        print(f"    与 vector 重合数：hybrid {len(vec_set & hyb_set)}/5，"
              f"mmr {len(vec_set & set(ids['mmr']))}/5")
        print(f"    首位是否相同：vector vs hybrid {ids['vector'][0] == ids['hybrid'][0]}，"
              f"vector vs mmr {ids['vector'][0] == ids['mmr'][0]}")

        note("RRF 只吃排名不吃分数 → 两路分数量纲不同也能安全融合；"
             "MMR 的 λ 越小越追求多样性")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
