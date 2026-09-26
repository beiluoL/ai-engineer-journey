"""09 章：整条链路上线跑一次 —— RAGService.ask()。

离线全链路：索引 → 检索 → 精排 → 组装 → FakeLLMClient 生成。
重点看三段失败语义里的第 2 条：检索为空时不许调 LLM（省钱，也更诚实）。
"""

from __future__ import annotations

from common import head, note, rule

from rag.assembler import ContextAssembler
from rag.cli import build_components
from rag.llm import FakeLLMClient
from rag.models import META_END_LINE, META_START_LINE
from rag.pipeline import RAGService
from rag.reranker import NoopReranker

Q1 = "生成器为什么能省内存？"
Q2 = "我们公司今年的 KPI 怎么分解？"          # 知识库里没有


class CountingLLM:
    """包一层计数器：用来证明「检索为空时一次都没调 LLM」。"""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return self.inner.chat(messages)


def main() -> int:
    head("python demos/demo_09_pipeline.py")
    settings, embedding, store, retriever, service = build_components(
        profile="dev", fake=True, top_k=3, index_paths=["data/"])
    print(f"profile=dev  top_k={settings.top_k}  hybrid={settings.hybrid}  "
          f"enable_rerank={settings.enable_rerank}")
    print(f"向量库：{store.count()} 个 chunk（{embedding.model_name}）")

    print(f"\n问题：{Q1}")
    rule("① ask() 内部：检索 → 精排 → 组装")
    scored = retriever.retrieve(Q1, top_k=settings.top_k,
                                mode="hybrid" if settings.hybrid else "vector")
    for rank, h in enumerate(scored, start=1):
        ln = h.chunk.metadata.get(META_START_LINE, 0)
        ln_end = h.chunk.metadata.get(META_END_LINE, 0)
        print(f"    检索 #{rank}  {h.score:.4f}  {h.chunk.source}#L{ln}-{ln_end}")
    print(f"    精排：注入的是 NoopReranker（只截断不改分）")
    print(f"    组装：budget={settings.effective_budget()} token，"
          f"min_score={settings.min_score}")

    rule("② 组装好的【参考资料】（就是发给模型的那段 system 内容）")
    ctx = ContextAssembler(min_score=settings.min_score).build(
        Q1, scored, settings.effective_budget())
    for line in ctx.context_text.splitlines()[:4]:
        print(f"  | {line}")
    print("    ...")
    print(f"    （共 {ctx.context_tokens} token / 用了 {ctx.n_used} 条）")

    rule("③ 最终答案 RAGAnswer")
    answer = service.ask(Q1)
    print(f"    answer         = {answer.answer[:160]} ...")
    print(f"    refused        = {answer.refused}")
    print(f"    context_tokens = {answer.context_tokens} / budget "
          f"{settings.effective_budget()}")

    rule("④ citations：答案里的编号 ↔ 可回原文档的定位键")
    for c in answer.citations:
        print(f"    [{c.no}] {c.anchor()}  chunk_index={c.chunk_index}")

    print(f"\n问题：{Q2}")
    rule("⑤ 失败语义 2：检索为空 → 拒答，且一次 LLM 都不调")
    loose = retriever.retrieve(Q2, top_k=3, mode="vector")
    print(f"    默认 min_score={settings.min_score} 下也能召回 {len(loose)} 条"
          f"（词面沾边而已）→ 光靠模型自觉拒答不稳")
    llm = CountingLLM(FakeLLMClient())
    strict = RAGService(
        retriever=retriever,
        reranker=NoopReranker(),
        assembler=ContextAssembler(min_score=0.8),     # 抬到 0.8 → 召回为空
        llm=llm,
        settings=settings,
    )
    out = strict.ask(Q2)
    print(f"    min_score=0.8 → 用 {len(out.used_chunks)} 条资料，"
          f"retrieved_sources={out.retrieved_sources}")
    print(f"    answer  = {out.answer}")
    print(f"    refused = {out.refused}    llm.calls = {llm.calls}")
    print("    → 没资料就不许编；而且这一次 LLM 调用次数是 0")

    rule("⑥ 换一个知识库里真有的：token 和字符的比例")
    answer2 = service.ask("token 和字符换算大概是什么比例？")
    print(f"    answer  = {answer2.answer[:160]} ...")
    print(f"    citations = {[c.anchor() for c in answer2.citations]}")

    note("离线链路里 LLM 也是 Fake 的：换 SiliconFlowLLMClient 只需改 cli 的装配，"
         "RAGService 一行不动")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
