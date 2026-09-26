"""07 章：两阶段检索的第二阶段 —— 精排（rerank）。

场景：向量路粗召回 top-5 → FakeReranker 精排到 top-2。
要看两件事：① 顺序变了没有（rerank 的意义就是改顺序，只截断等于没加）；
② 分数是谁在说话（粗排是余弦 0~1，精排是关键词覆盖度，量纲完全不同）。
"""

from __future__ import annotations

from common import head, note, rule

from rag.cli import build_components
from rag.reranker import FakeReranker

QUERY = "生成器为什么能省内存"


def main() -> int:
    head("python demos/demo_07_rerank.py")
    settings, _emb, store, retriever, service = build_components(
        profile="dev", fake=True, top_k=5, index_paths=["data/"])

    recalled = retriever.retrieve(QUERY, top_k=5, mode="vector")
    print(f"\n问题：{QUERY}   （向量库 {store.count()} 个 chunk）")

    rule("① 粗排：向量路 top-5（余弦相似度，量纲 0~1）")
    for rank, h in enumerate(recalled, start=1):
        print(f"    #{rank} score={h.score:.4f}  {h.chunk.source.split('/')[-1]:<24}"
              f"chunk#{h.chunk.index}  {h.chunk.text[:28]!r}")

    reranker = FakeReranker()
    top2 = reranker.rerank(QUERY, recalled, top_n=2)

    rule("② 精排：FakeReranker 重打分，取 top-2（覆盖度 − 长度惩罚，量纲 0~1）")
    for rank, h in enumerate(top2, start=1):
        print(f"    #{rank} score={h.score:.4f}  {h.chunk.source.split('/')[-1]:<24}"
              f"chunk#{h.chunk.index}  {h.chunk.text[:28]!r}")

    rule("③ 前后对照")
    before = [(h.chunk_id, h.score) for h in recalled]
    after = [(h.chunk_id, h.score) for h in top2]
    same_order = [b[0] for b in before] == [a[0] for a in after]
    print(f"    顺序是否完全不变：{same_order}"
          f"（不变 = 精排白加了，只起截断作用）")
    if after[0][0] == before[0][0]:
        print("    第 1 名没变（这个 query 的词粗排也全命中，换个长 query 更容易看出差别）")
    else:
        old_rank = [i for i, (c, _) in enumerate(before, start=1) if c == after[0][0]][0]
        print(f"    精排把第 {old_rank} 名 [{after[0][0]}] 提到了第 1")
    for rank, (cid, score) in enumerate(after, start=1):
        old = [i for i, (c, _) in enumerate(before, start=1) if c == cid]
        old_txt = f"第 {old[0]} 名" if old else "（不在粗排 top-5 内）"
        print(f"    #{rank} {cid}  精排 {score:+.4f}   粗排 {old_txt}")

    rule("④ 同一个粗排结果，NoopReranker 只截断不改分")
    from rag.reranker import NoopReranker
    noop = NoopReranker().rerank(QUERY, recalled, top_n=2)
    for rank, h in enumerate(noop, start=1):
        print(f"    #{rank} score={h.score:.4f}  {h.chunk_id}"
              f"（分数沿用粗排，和 ① 完全一致：{h.score == recalled[rank - 1].score}）")

    note("bi-encoder 负责快而全的粗召回；cross-encoder 负责慢而准的精排，"
         "两者不是替代品，是接力")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
