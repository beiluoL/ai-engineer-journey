"""11 章：接真实服务 —— 百炼 embedding + Chroma 持久化，并验证「重启后数据还在」。

为什么值得单独跑一次：
    前面 10 章的所有向量都来自 FakeEmbeddingClient（离线、确定、免费）。
    接真实服务的那一刻，才会撞上那些单测永远照不到的坑 ——
        单批上限不是你想的 32（百炼是 10）
        Markdown 的 headings 是 list，Chroma 的 metadata 不收 list
        不同厂商的 base_url / 环境变量都不一样
        换模型 = 换向量空间 = 必须重建索引
    这一章把它们逐个踩平，并留下可复现的证据。

用法（两个进程，模拟「写入 → 进程退出 → 再次启动」）：
    python demos/demo_12_real_service.py ingest
    python demos/demo_12_real_service.py query
不带参数则一次跑完全流程。
"""

from __future__ import annotations

import gc
import sys
import time
from pathlib import Path

from common import head, note, rule

from rag.chunker import chunk_document
from rag.embedding import DashScopeEmbeddingClient, FakeEmbeddingClient, run_sync
from rag.errors import EmbeddingError
from rag.parsing import expand_paths, parse_file
from rag.similarity import cosine_similarity
from rag.store import ChromaVectorStore

# 落盘目录**不要**放在 data/ 里：摄入侧会递归扫描 data/，
# 把 Chroma 的 .bin/.sqlite3 当成待解析的文档（11 章坑 3）。
PERSIST_DIR = "chroma_db/rag_chunks"
COLLECTION = "rag_chunks"

# 刻意选的查询：跟语料几乎不共享字面词，只能靠语义命中
QUERY = "Java 的 Stream 和 Python 的生成器有什么对应关系"

PROBE_TEXTS = [
    "生成器只在被调用的那一刻算出一个值，算完就丢",   # 与查询语义同族
    "GIL 是 CPython 的一把全局解释器锁",              # 同文档、不同话题
]

def build_chunks() -> list:
    """data/ 下所有文档 → chunks（复用 01/02 章的解析与切分）。"""
    chunks: list = []
    for path in expand_paths(["data/"], skip_report=True):
        for doc in parse_file(path):
            chunks.extend(chunk_document(doc, size=500, overlap=80))
    return chunks


def _tree(root: Path, prefix: str = "", max_rows: int = 10) -> list[str]:
    """把落盘目录拍成一小棵树（只显示结构，避免截图过长）。"""
    rows: list[str] = []
    dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    files = sorted((p for p in root.iterdir() if p.is_file()), key=lambda p: p.name)
    for d in dirs[:3]:
        rows.append(f"{prefix}{d.name}/")
        inner = sorted(f for f in d.iterdir() if f.is_file())
        for f in inner[:2]:
            rows.append(f"{prefix}    {f.name}  ({f.stat().st_size // 1024} KB)")
        if len(inner) > 2:
            rows.append(f"{prefix}    … 还有 {len(inner) - 2} 个文件")
    for f in files[:max_rows]:
        rows.append(f"{prefix}{f.name}")
    return rows


def section_intro(client: DashScopeEmbeddingClient) -> None:
    print()
    note("真实 embedding 客户端（百炼 compatible-mode / OpenAI 协议）")
    print(f"  class      = {type(client).__name__}")
    print(f"  model      = {client.model_name}")
    print(f"  dim        = {client.dim}")
    print(f"  batch_size = {client.batch_size}   ← 百炼的单批上限是 10，不是 32")
    print(f"  env        = {type(client).ENV_VAR}")


def do_ingest(client: DashScopeEmbeddingClient) -> ChromaVectorStore:
    chunks = build_chunks()
    texts = [c.text for c in chunks]
    print(f"  把 data/ 下 {len(set(c.source for c in chunks))} 篇文档切成 "
          f"{len(chunks)} 个 chunk，待向量化")

    rule("批量 embed：一次请求处理一批，而不是一条一请求")
    n_batches = (len(texts) + client.batch_size - 1) // client.batch_size
    print(f"  {len(texts)} 条文本 / batch_size={client.batch_size} "
          f"→ 约 {n_batches} 次 HTTP 往返"
          f"（若逐条请求就要 {len(texts)} 次）")
    started = time.perf_counter()
    vectors = run_sync(client.embed(texts))
    elapsed = time.perf_counter() - started
    print(f"  实际发起了 {client.request_count} 次请求，"
          f"总耗时 {elapsed:.2f}s，每批平均 "
          f"{sum(client.latencies) / len(client.latencies):.3f}s")
    print(f"  返回 {len(vectors)} 个向量，每个 {len(vectors[0])} 维，"
          f"顺序与输入一致（按 index 还原）")

    store = ChromaVectorStore(persist_directory=PERSIST_DIR,
                              collection_name=COLLECTION)
    rule("写入 Chroma（落盘，不是内存）")
    print(f"  persist_directory = {PERSIST_DIR}")
    store.add(chunks, vectors, client.model_name)
    print(f"  store.count() = {store.count()}   "
          f"store.model_name = {store.model_name!r}")
    rule("落盘的产物（Chroma 自己管理的目录）")
    root = Path(PERSIST_DIR)
    for row in _tree(root):
        print(f"  {row}")
    note("这些文件是派生数据：源文档没变就不该提交进 git（已在 .gitignore 里）")
    return store


def do_query(store: ChromaVectorStore, client: DashScopeEmbeddingClient) -> None:
    rule(f"检索：{QUERY!r}")
    qv = run_sync(client.embed_one(QUERY))
    hits = store.search(qv, top_k=3)
    for rank, (chunk, score) in enumerate(hits, start=1):
        print(f"  #{rank}  score={score:.4f}  {Path(chunk.source).name}#{chunk.index}")
        print(f"       {chunk.text[:46]!r}")
    note("查询与语料几乎没有共享字面词，能命中靠的是语义 —— 这正是 Fake 替身做不到的")

    rule("语义对比：真实模型 vs Fake 替身（同一个查询）")
    chunks = build_chunks()
    fake = FakeEmbeddingClient()
    fq = run_sync(fake.embed_one(QUERY))
    fvecs = run_sync(fake.embed([c.text for c in chunks]))
    f_best = max(range(len(fvecs)), key=lambda i: cosine_similarity(fvecs[i], fq))
    print(f"  real top1 = {Path(hits[0][0].source).name}#{hits[0][0].index}  "
          f"score={hits[0][1]:.4f}")
    print(f"  fake top1 = {Path(chunks[f_best].source).name}#{chunks[f_best].index}")
    note("Fake 靠字面匹配，这条查询的字面线索太弱，排序立刻失真")

    rule("护栏：换模型必须先重建索引（向量空间互不相通）")
    print(f"  重新打开后 store.model_name = {store.model_name!r}"
          f"  ← 从落盘的 {PERSIST_DIR}/_model 读回来的")
    print(f"  该文件内容 = {Path(PERSIST_DIR, '_model').read_text(encoding='utf-8')!r}")
    try:
        store.check_model("BAAI/bge-m3")
        print("  没有拦住 —— 这道护栏失效了，两个模型的向量会混用")
    except EmbeddingError as e:
        print(f"  EmbeddingError: {e}")


def do_batch_probe(client: DashScopeEmbeddingClient) -> None:
    """故意发一批超限的请求，把厂商的真实报错留在文档里。"""
    rule("先探一下单批上限：故意发 11 条（batch_size 临时改成 11）")
    client.batch_size = 11
    try:
        run_sync(client.embed([f"第 {i} 条文本，用于探测批量上限。" for i in range(11)]))
        print("  没报错 —— 那上限可能比 10 大，值得回头调大 batch_size")
    except Exception as e:                     # noqa: BLE001 - 就是要看厂商报什么
        detail = getattr(e, "response", None)
        body = detail.text[:180] if detail is not None else str(e)
        print(f"  {type(e).__name__}: {body}")
    client.batch_size = type(client).DEFAULT_BATCH_SIZE   # 复原
    note("结论：batch_size 不是全局常数，是「厂商 × 模型」的硬约束（百炼 = 10）")


def main(argv: list[str]) -> int:
    phase = argv[0] if argv else "all"
    head("python demos/demo_12_real_service.py " + (argv[0] if argv else ""))

    try:
        client = DashScopeEmbeddingClient()
    except EmbeddingError as e:
        print(f"  初始化失败：{e}")
        print("  先 export DASHSCOPE_API_KEY=sk-xxxx 再跑本 demo")
        return 1
    section_intro(client)

    if phase == "batch":
        do_batch_probe(client)
        return 0

    store: ChromaVectorStore | None = None
    if phase in ("all", "ingest"):
        store = do_ingest(client)

    if phase in ("all", "query"):
        rule("模拟重启：释放连接后重新打开同一个落盘目录")
        del store                          # type: ignore[assignment]
        gc.collect()                       # 让进程内的 Chroma 连接真正释放
        store = ChromaVectorStore(persist_directory=PERSIST_DIR,
                                  collection_name=COLLECTION)
        print(f"  进程重新打开 {PERSIST_DIR}，store.count() = {store.count()}"
              f"  ← 数据还在，这就是持久化")
        do_query(store, client)            # type: ignore[arg-type]
        del store
        gc.collect()

    print()
    note("接真实服务的完整链路：解析 → 切分 → 真实向量 → Chroma 落盘 → 重启可查")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
