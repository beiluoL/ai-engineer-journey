"""命令行入口：`python -m rag.cli`

    # 离线建索引（FakeEmbeddingClient，不联网）
    python -m rag.cli --index data/ --fake

    # 离线问答
    python -m rag.cli --ask "生成器为什么能省内存" --fake

    # 换真实 embedding（从环境变量读 SILICONFLOW_API_KEY）
    python -m rag.cli --index data/
    python -m rag.cli --ask "..." --top-k 5

接入层只在这一处按 profile 组装依赖（09 §4），之后每个请求只调 service.ask()。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# `python -m rag.cli` 时 sys.path 里只有 cwd，src/ 需要自己补上
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from .assembler import ContextAssembler                        # noqa: E402
from .embedding import FakeEmbeddingClient, SiliconFlowEmbeddingClient  # noqa: E402
from .errors import RAGError                                   # noqa: E402
from .evaluation import build_default_eval_cases, evaluate     # noqa: E402
from .llm import FakeLLMClient                                 # noqa: E402
from .models import META_HEADINGS                              # noqa: E402
from .pipeline import IngestionPipeline, RAGAnswer, RAGService  # noqa: E402
from .parsing import PARSER_CLASSES, expand_paths, parse_file  # noqa: E402
from .reranker import FakeReranker, NoopReranker, SiliconFlowReranker  # noqa: E402
from .retriever import Retriever                               # noqa: E402
from .settings import RAGSettings                              # noqa: E402
from .store import InMemoryVectorStore                         # noqa: E402

QUIET_META = ("format", "size_bytes", "parsed_at", META_HEADINGS, "code_ranges")


def build_embedding_client_from_env():
    """挑一个「本机真的能跑起来」的 embedding provider。

    默认 SiliconFlow（bge-m3），但机器上没有它的 key、百炼的 key 却在时，
    直接报「api_key 为空」只会让人以为环境坏了。所以按 key 探测降级：
        有 SILICONFLOW_API_KEY → SiliconFlow bge-m3
        否则有 DASHSCOPE_API_KEY → 百炼 text-embedding-v3（同为 1024 维）
        都没有 → 交给客户端自己报那句明确的错

    换 provider 在本项目里应该是「改环境变量」而不是「改代码」，
    这条约束就是这么来的。
    """
    from .embedding import DashScopeEmbeddingClient, SiliconFlowEmbeddingClient

    if os.environ.get("SILICONFLOW_API_KEY"):
        return SiliconFlowEmbeddingClient(api_key=os.environ["SILICONFLOW_API_KEY"])
    if os.environ.get("DASHSCOPE_API_KEY"):
        return DashScopeEmbeddingClient(api_key=os.environ["DASHSCOPE_API_KEY"])
    return SiliconFlowEmbeddingClient(api_key="")


def build_components(profile: str = "dev", fake: bool = False, top_k: int = 5,
                     index_paths: list[str] | None = None, quiet: bool = False,
                     llm=None):
    """按 profile 组装依赖，返回 (settings, embedding_client, store, retriever, service)。

    fake=True → FakeEmbeddingClient + NoopReranker，全链路不联网；
    否则 → SiliconFlow embedding + FakeReranker（真实服务需要 SILICONFLOW_API_KEY）。

    index_paths 不为空时，在**同一个进程内**先建索引再服务
    （内存向量库不跨进程，这也是 demo 里一次跑完的原因）。

    llm 用来覆盖「生成侧」：默认值是 FakeLLMClient，Web API 会传真实的
    DeepSeekLLMClient 进来 —— 检索侧(fake)与生成侧(真实)本来就该能各自开关。
    """
    settings = RAGSettings.for_profile(profile).validate().replace(top_k=top_k)

    if fake:
        embedding_client = FakeEmbeddingClient()
        reranker = NoopReranker()
    else:
        embedding_client = build_embedding_client_from_env()
        # rerank 是可选增强：有 key 才走真实接口，否则退回 FakeReranker 保持可跑
        reranker = (SiliconFlowReranker(api_key=os.environ.get(
            "SILICONFLOW_API_KEY", "")) if os.environ.get("SILICONFLOW_API_KEY")
            else FakeReranker())

    store = InMemoryVectorStore()
    retriever = Retriever(embedding_client=embedding_client, vector_store=store)
    service = RAGService(
        retriever=retriever,
        reranker=reranker,
        assembler=ContextAssembler(min_score=settings.min_score),
        llm=llm if llm is not None else FakeLLMClient(),
        settings=settings,
    )
    if index_paths:
        files = expand_paths(index_paths)
        if files:
            pipeline = IngestionPipeline(list(PARSER_CLASSES), embedding_client,
                                         store, retriever)
            report = pipeline.ingest(files)
            if not quiet:      # demo 里一个进程要装配多次，静默装配免得刷屏
                print(f"索引 {report.files_total} 个文件：成功 {report.files_ok}，"
                      f"失败 {len(report.files_failed)}，切出 {report.chunks_stored} 个 chunk")
    return settings, embedding_client, store, retriever, service


def cmd_index(paths: list[str], fake: bool, profile: str) -> int:
    settings, embedding_client, store, retriever, _service = build_components(
        profile=profile, fake=fake)
    files = expand_paths(paths)
    if not files:
        print(f"没有找到任何文件：{paths}")
        return 1

    pipeline = IngestionPipeline(list(PARSER_CLASSES), embedding_client, store, retriever)
    report = pipeline.ingest(files)

    print(f"索引 {report.files_total} 个文件：成功 {report.files_ok}，"
          f"失败 {len(report.files_failed)}，切出 {report.chunks_stored} 个 chunk")
    print("-" * 96)
    print(f"{'doc_id':<18}{'source':<38}{'format':<8}{'字符数':>7}{'行数':>6}")
    print("-" * 96)
    for path in files:
        try:
            docs = parse_file(path)
        except RAGError as e:
            print(f"{'(解析失败)':<18}{str(path):<38}{'-':<8}{'-':>7}{'-':>6}")
            print(f"{'':<18}原因: {e}")
            continue
        for doc in docs:
            meta = doc.metadata
            print(f"{doc.doc_id:<18}{doc.source:<38}{meta.get('format', '-'):<8}"
                  f"{len(doc.text):>7}{doc.line_count:>6}")
            flat = ", ".join(f"{k}={v}" for k, v in meta.items() if k not in QUIET_META)
            print(f"{'':<18}metadata : {flat or '-'}")
            headings = meta.get(META_HEADINGS) or []
            if headings:
                titles = " · ".join(f"L{h['line']} {h['title']}" for h in headings[:4])
                print(f"{'':<18}headings : {titles}")
            if meta.get("code_ranges"):
                print(f"{'':<18}code     : {len(meta['code_ranges'])} 个代码围栏（切分时不可拆）")
    print("-" * 96)
    print(f"向量库 count() = {store.count()}；"
          f"embedding 模型 = {store.model_name or '-'}；chunk_size={settings.chunk_size}，"
          f"overlap={settings.chunk_overlap}")
    return 0


def cmd_ask(question: str, fake: bool, profile: str, top_k: int, show_context: bool,
            index_paths: list[str] | None = None) -> int:
    _settings, _emb, store, _retr, service = build_components(
        profile=profile, fake=fake, top_k=top_k, index_paths=index_paths)
    if store.count() == 0:
        print("向量库是空的：先跑一次 `python -m rag.cli --index data/ --fake`，"
              "或者把 --index 和 --ask 一起传")
        return 1
    try:
        answer: RAGAnswer = service.ask(question)
    except RAGError as e:
        print(f"问答失败: {e}")
        return 1

    print(f"问：{question}")
    print(f"答：{answer.answer}")
    print(f"[引用] context_tokens={answer.context_tokens}，"
          f"used_chunks={len(answer.used_chunks)}")
    for c in answer.citations:
        print(f"  [{c.no}] {c.anchor()}  chunk_index={c.chunk_index}  start_char={c.start_char}")
    if show_context:
        print("-" * 96)
        print("[组装后的参考资料]")
        print("\n\n".join(sc.chunk.text for sc in answer.used_chunks) or "(空)")
    return 0


def cmd_eval(profile: str, fake: bool, index_paths: list[str] | None = None) -> int:
    _settings, _emb, store, _retr, service = build_components(
        profile=profile, fake=fake, index_paths=index_paths)
    if store.count() == 0:
        print("向量库是空的：先跑一次 `python -m rag.cli --index data/ --fake`")
        return 1
    cases = build_default_eval_cases()
    report = evaluate(service, cases)
    print(f"跑 {len(cases)} 条 EvalCase（profile={profile}）")
    print(f"hit_rate@3   = {report.hit_rate_at_3:.3f}")
    print(f"hit_rate@5   = {report.hit_rate_at_5:.3f}")
    print(f"mrr          = {report.mrr:.3f}")
    print(f"context_hit  = {report.context_hit_rate:.3f}")
    print(f"keyword_pass = {report.keyword_pass_rate:.3f}")
    print(f"refusal_pass = {report.refusal_pass_rate:.3f}")
    if report.failed_cases:
        print("失败明细：")
        for line in report.failed_cases:
            print(f"  - {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m rag.cli",
        description="Personal RAG 命令行入口（加 --fake 全链路离线）",
    )
    ap.add_argument("--index", nargs="+", metavar="PATH",
                    help="索引本地文件 / 目录（md/txt）；与 --ask / --eval 同传时同进程建好索引")
    ap.add_argument("--ask", metavar="QUESTION", help="提问一次")
    ap.add_argument("--eval", action="store_true", help="跑内置评测集")
    ap.add_argument("--context", action="store_true", help="打印组装后的参考资料")
    ap.add_argument("--fake", action="store_true", help="全离线：Fake + NoopReranker")
    ap.add_argument("--profile", default="dev", help="dev / test")
    ap.add_argument("--top-k", type=int, default=5, help="最终交给组装的条数")
    args = ap.parse_args(argv)

    # --index 可以和 --ask / --eval 同传：同一个进程内先建索引再服务
    if args.ask:
        return cmd_ask(args.ask, args.fake, args.profile, args.top_k, args.context,
                       args.index)
    if args.eval:
        return cmd_eval(args.profile, args.fake, args.index)
    if args.index:
        return cmd_index(args.index, args.fake, args.profile)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
