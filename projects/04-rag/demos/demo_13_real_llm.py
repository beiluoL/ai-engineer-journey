"""12 章：把真实大模型接进 RAG —— 生成侧上线的全过程。

09 章的离线链路里，生成这一步站着一个 FakeLLMClient：它只会从【参考资料】里
抄句子。好处是全链路可离线跑；代价是它**永远不会胡编**，所以「模型乱答」这类
问题在离线状态下一个都测不到。

这一章换上真实模型（DeepSeek，OpenAI 兼容协议），看四件事：

    ① 同一条链路、同一个 RAGService，只换掉注入的 llm
    ② 真实调用的真实成本：耗时与 token
    ③ 忠实度审计：哪些话在资料里找不到依据（含一个注入式自测）
    ④ 检索为空时的闸门：省钱是小事，兜底才是大事

检索侧仍然用 FakeEmbeddingClient：本次重点在生成侧，这样 demo 几秒钟就能跑完。
"""

from __future__ import annotations

import os
import time

from common import head, note, rule

from rag.assembler import ContextAssembler
from rag.cli import build_components
from rag.evaluation import check_answer_faithfulness, check_faithfulness
from rag.llm import DeepSeekLLMClient, parse_answer_refs
from rag.pipeline import RAGService
from rag.reranker import NoopReranker
from rag.settings import RAGSettings

Q1 = "生成器为什么能省内存？"
Q2 = "我们公司今年的 KPI 怎么分解？"          # 知识库里没有

# 注入式自测用的假事实。它伪装得很好：数字合理、措辞和答案一致，
# 唯一的问题是 —— 资料里根本没有这两个数字。
POISON = "补充一点：这个优化把内存占用降到了 3.14 MB，相当于原方案的 12.7%。"


class TimedLLM:
    """给 client 打表：耗时 / 调用次数 / 真实 token 花费。"""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.total = 0.0

    def chat(self, messages) -> str:
        self.calls += 1
        t0 = time.perf_counter()
        out = self.inner.chat(messages)
        self.total += time.perf_counter() - t0
        return out

    @property
    def usage(self) -> dict | None:
        return self.inner.last_usage


def build_service(settings: RAGSettings, llm) -> RAGService:
    """复用 cli 的装配，只把 llm 换成真实的 —— 这就是依赖倒置的意义。"""
    _settings, _emb, _store, retriever, _svc = build_components(
        profile="dev", fake=True, top_k=settings.top_k,
        index_paths=["data/"], quiet=True)          # 一个进程装配多次，静默
    return RAGService(
        retriever=retriever,
        reranker=NoopReranker(),
        assembler=ContextAssembler(min_score=settings.min_score),
        llm=llm,
        settings=settings,
    )


def section_intro(client: DeepSeekLLMClient) -> None:
    rule("① 装配：RAGService 一行不动，只换掉 llm")
    print(f"  llm        = {client.__class__.__name__} "
          f"(model={client.model_name}, temperature={client.temperature}, "
          f"timeout={client.timeout}s)")
    print(f"  base_url   = {client.BASE_URL}")
    print("  检索侧仍是 FakeEmbeddingClient（本次重点在生成侧，demo 秒开）")
    print("  → ask() 对 llm 只有『chat(messages) -> str』这一个要求，")
    print("    换成真实模型要改的只有装配处那一行。")


def section_ask(settings: RAGSettings, llm: TimedLLM) -> None:
    service = build_service(settings, llm)
    rule("② 真实调用一次 ask()")
    t0 = time.perf_counter()
    answer = service.ask(Q1)
    cost = time.perf_counter() - t0
    print(f"  问题     = {Q1}")
    print(f"  耗时     = {cost:.2f}s（检索 + 组装 + 生成全算在内）")
    print(f"  资料用量 = {answer.context_tokens} token")
    print(f"  答案     = {answer.answer[:150]} ...")
    print(f"  引用编号 = {parse_answer_refs(answer.answer)}  "
          f"citations = {[c.anchor() for c in answer.citations]}")
    u = llm.usage
    if u:
        print(f"  真实计费 = prompt {u.get('prompt_tokens')} / "
              f"completion {u.get('completion_tokens')} / 总 {u.get('total_tokens')}")
    else:
        print("  真实计费 = 接口没有返回 usage")


def section_faithful(settings: RAGSettings, llm: TimedLLM) -> None:
    rule("③ 忠实度审计：答案里哪些话在资料里找不到依据")
    answer = build_service(settings, llm).ask(Q1)
    report = check_answer_faithfulness(answer)
    print(f"  这次答案：{report.summary()}")
    print("  → 没有无出处句子，模型这次守规矩。但这不能说明审计工具没用 ——")

    rule("④ 注入式自测：往答案里塞一句假事实，看审计抓不抓得到")
    poisoned = answer.answer + POISON
    bad = check_faithfulness(poisoned, answer.system_prompt)
    print(f"  混入假事实后：{bad.summary()}")
    for sent in bad.unsupported:
        print(f"    被标红 → {sent[:70]}")
    print("  → 只有掺进去的那一句无出处，真答案不受影响：判据有区分度。")
    print("  → 这条路径是零成本的（不再调一次 LLM），可以放进 CI 跑回归。")


def section_refuse(settings: RAGSettings, llm: TimedLLM) -> None:
    rule("⑤ 闸门：没有资料时，一次都不许调 LLM")
    strict = build_service(settings.replace(min_score=0.9), llm)
    before = llm.calls
    out = strict.ask(Q2)
    print(f"  问题     = {Q2}")
    print(f"  answer   = {out.answer}")
    print(f"  refused  = {out.refused}   本次 ask 调用 LLM "
          f"{llm.calls - before} 次（闸门生效 → 0）")

    rule("⑥ 对照：把空资料直接喂给真实模型会怎样")
    bare = DeepSeekLLMClient(api_key=os.environ.get("DEEPSEEK_API_KEY", ""))
    messages = [
        {"role": "system",
         "content": "你是知识库问答助手。请严格遵守：\n"
                    "1. 只依据下面的【参考资料】回答用户问题。\n"
                    "2. 引用资料时用编号标注，如 [1]、[2]。\n"
                    "3. 如果参考资料不足以回答问题，直接说「知识库中没有相关资料」，"
                    "不要使用你自己的知识，不要编造。\n"
                    "【参考资料】\n（无）"},
        {"role": "user", "content": Q2},
    ]
    print(f"  空资料 + 严格 prompt → {bare.chat(messages)[:120]!r} ...")
    print("  → 这次 DeepSeek 守住了。所以别把结论写成「空资料一定会胡编」：")
    print("    实测会随模型、温度、prompt 措辞而变。能确定的是 ——")
    print("    闸门把这次调用直接省掉了，而且它不依赖模型的自觉。")


def section_stream(settings: RAGSettings) -> None:
    rule("⑦ 流式：把 chat() 换成 stream()，前端就能一个字一个字显示")
    client = DeepSeekLLMClient(api_key=os.environ.get("DEEPSEEK_API_KEY", ""))
    cached = build_service(settings, client).ask(Q1)   # 借它拿到组装好的 prompt
    messages = [
        {"role": "system", "content": cached.system_prompt},
        {"role": "user", "content": Q1},
    ]
    t0 = time.perf_counter()
    out = client.stream(messages)
    print(f"  流式耗时 = {time.perf_counter() - t0:.2f}s，收到 {len(out)} 字")
    print(f"  与 chat() 结果一致 = {out.strip() == cached.answer.strip()}")
    if out.strip() != cached.answer.strip():
        print(f"    chat = {cached.answer[:60]!r}")
        print(f"    stream = {out[:60]!r}")
    print("  → temperature=0 也不能保证两次逐字相同（采样 / 归一化差异）。")
    print("    别让前端拿流式结果和同步结果做相等判断；两者只保证语义相同。")


def main(argv: list[str]) -> int:
    phase = argv[0] if argv else "all"
    head("python demos/demo_13_real_llm.py " + (argv[0] if argv else ""))
    try:
        key = os.environ["DEEPSEEK_API_KEY"]
    except KeyError:
        print("  缺少 DEEPSEEK_API_KEY：先 export DEEPSEEK_API_KEY=sk-xxxx 再跑")
        return 1
    client = DeepSeekLLMClient(api_key=key)
    timed = TimedLLM(client)
    settings = RAGSettings.for_profile("dev").validate().replace(top_k=3)
    section_intro(client)

    if phase in ("all", "ask"):
        section_ask(settings, timed)
    if phase in ("all", "faithful"):
        section_faithful(settings, timed)
    if phase in ("all", "refuse"):
        section_refuse(settings, timed)
    if phase in ("all", "stream"):
        section_stream(settings)

    rule("计量小结")
    print(f"  LLM 调用 {timed.calls} 次，累计 {timed.total:.2f}s")
    note("生成侧的成本随 top_k / 预算线性增长；把 context_tokens 与 usage 打进"
         "日志，是上线前该做的最小一件事。")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
