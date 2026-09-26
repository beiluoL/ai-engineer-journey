"""04 章：InMemoryVectorStore 真的存进去、搜出来，并演示 metadata 过滤。"""

from __future__ import annotations

from common import head, note, rule

from rag.chunker import chunk_document
from rag.embedding import FakeEmbeddingClient, run_sync
from rag.parsing import expand_paths, parse_file
from rag.store import InMemoryVectorStore

QUERY = "生成器为什么能省内存"


def main() -> int:
    head("python demos/demo_04_store.py")
    client = FakeEmbeddingClient()
    store = InMemoryVectorStore()

    chunks = []
    for path in expand_paths(["data/"]):
        for doc in parse_file(path):
            chunks.extend(chunk_document(doc, size=500, overlap=80))

    print(f"切出 {len(chunks)} 个 chunk，批量 embed 后一次 add 进 InMemoryVectorStore")
    rule("add()")
    store.add(chunks, run_sync(client.embed([c.text for c in chunks])), client.model_name)
    print(f"store.count() = {store.count()}   "
          f"store.model_name = {store.model_name!r}")

    rule("重复 add 同一个列表（内容哈希 id 一样）→ 幂等，不翻倍")
    store.add(chunks, run_sync(client.embed([c.text for c in chunks])), client.model_name)
    print(f"store.count() = {store.count()}")

    rule(f"search(生成器为什么能省内存, top_k=2)")
    qv = run_sync(client.embed_one(QUERY))
    for rank, (chunk, score) in enumerate(store.search(qv, top_k=2), start=1):
        print(f"  #{rank}  score={score:.4f}  {chunk.source}#{chunk.index}")
        print(f"       {chunk.text[:56]!r}")

    rule("search(..., filter={'format': 'txt'})：先过滤后搜，不是搜完再筛")
    txt_hits = store.search(qv, top_k=3, filter={"format": "txt"})
    all_hits = store.search(qv, top_k=3)
    print(f"  不过滤 top3：{[c.source.split('/')[-1] for c, _ in all_hits]}")
    print(f"  过滤 txt 后：{[c.source.split('/')[-1] for c, _ in txt_hits]} "
          f"（score {[round(s, 4) for _, s in txt_hits]}）")
    print(f"  过滤结果全部是 txt：{all(c.metadata['format'] == 'txt' for c, _ in txt_hits)}")
    print("  → 过滤是把候选集合先缩小，再在里面按余弦排序；")
    print("    不是先取 top_k 再丢弃不匹配的（那样 top_k 会被无关文档占满）")

    rule("check_invariant()：自检 chunk 与向量数量一致")
    store.check_invariant()
    print("  一致，没有漂掉的向量")

    rule("delete_document()：删掉一整篇文档")
    victim = all_hits[0][0].doc_id
    store.delete_document(victim)
    print(f"  删除 doc_id={victim} 后 store.count() = {store.count()}")
    tail = store.search(qv, top_k=3)
    if tail:
        print(f"  再搜一次 top1 = {tail[0][0].source.split('/')[-1]} "
              f"（score {tail[0][1]:.4f}）")
    note("内存向量库不跨进程：--index 与 --ask 必须同进程，否则第二次进程搜不到东西")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
