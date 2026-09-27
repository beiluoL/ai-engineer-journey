"""真实可观测性报告：慢在哪 / 召回有没有退化 / 钱花在哪（15 章）。

    python demos/demo_16_metrics.py            # 真实 embedding + 真实 DeepSeek
    python demos/demo_16_metrics.py --fake     # 全离线（看计量壳本身对不对）

14 章回答的是「答得准不准」，这一章回答的是另一组问题：
    1. 慢在哪 —— 检索 / 精排 / 组装 / 生成 四段各占多少毫秒
    2. 召回有没有退化 —— 相似度分数的分布，有多少落在会被 min_score 拦掉的桶里
    3. 钱花在哪 —— embedding / LLM 各调了多少次，拒答省下了几次
这三条光看日志答不上来：日志是逐条事件，而它们是聚合分布。
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import WIDTH, head, rule  # noqa: E402

from rag.cli import build_components  # noqa: E402
from rag.llm import DeepSeekLLMClient  # noqa: E402
from rag.metrics import Names, render_report  # noqa: E402

QUESTIONS = [
    "生成器为什么能省内存？",
    "装饰器是怎么在不改原函数代码的前提下加功能的？",
    "GIL 到底是什么，为什么多线程跑不满多核？",
    "token 和字符是什么关系，为什么算钱要按 token？",
    "temperature 调高会发生什么？",
    "稠密检索和关键词检索各擅长什么？",
]

# 知识库里没有的问题：用来验证「拒答一次 LLM 都不调」这条省钱语义
OUT_OF_KB = "2026 年世界杯冠军是哪支球队？"


def stage_bar(snapshot: dict) -> None:
    """把一次请求内的四段耗时画成占比条。

    画条而不是列数字，是因为要回答的问题是「慢在哪」——
    一眼看出哪一段最长，比读四个毫秒数快得多。
    """
    timings = snapshot["timings"]
    stages = [
        ("检索", Names.RETRIEVE_LATENCY),
        ("精排", Names.RERANK_LATENCY),
        ("组装", Names.ASSEMBLE_LATENCY),
        ("生成", Names.GENERATE_LATENCY),
    ]
    rows = [(label, timings[k]["mean"] * 1000) for label, k in stages if k in timings]
    total = sum(ms for _, ms in rows) or 1.0
    print(f"  {'段':<6}{'均值':>9}{'占比':>8}   分布")
    for label, ms in sorted(rows, key=lambda r: -r[1]):
        ratio = ms / total
        bar = "█" * max(int(ratio * 40), 1)
        print(f"  {label:<6}{ms:>8.1f}ms{ratio:>7.1%}   {bar}")
    print(f"  {'合计':<6}{total:>8.1f}ms")
    top = max(rows, key=lambda r: r[1]) if rows else ("", 0)
    print(f"  → 最长的一段是「{top[0]}」（{top[1]:.1f}ms，占 {top[1] / total:.0%}）；"
          f"优化要从这一段下手")


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    head(f"python demos/demo_16_metrics.py {'--fake' if fake else ''}")
    print(f"  模式：{'全离线 Fake' if fake else '真实 embedding（百炼）+ 真实 DeepSeek'}")
    print(f"  问题：{len(QUESTIONS)} 条库内问题 + 1 条库外问题（验证拒答省钱）")

    llm = None
    if not fake:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            print("请设置环境变量 DEEPSEEK_API_KEY")
            return 1
        llm = DeepSeekLLMClient(api_key=key)

    _settings, _emb, store, retriever, service = build_components(
        profile="dev", fake=fake, index_paths=["data/"], quiet=True, llm=llm)
    print(f"  索引完成：{store.count()} chunks")

    rule("① 建索引也要花钱：索引阶段的 embedding 调用")
    snap = service.metrics.snapshot()
    print(f"  embedding 调用次数 : {snap['counters'].get(Names.EMBED_CALLS, 0):.0f} 次")
    print(f"  embedding 文本条数 : {snap['counters'].get(Names.EMBED_TEXTS, 0):.0f} 条")
    print(f"  embedding 失败次数 : {snap['counters'].get(Names.EMBED_ERRORS, 0):.0f} 次")
    embed_ms = snap["timings"].get(Names.EMBED_LATENCY, {}).get("mean", 0) * 1000
    print(f"  embedding 平均耗时 : {embed_ms:.1f} ms/批")
    print("  → calls 按批计、texts 按条计：花钱看的是 texts。")
    print("    真实 embedding 有单批上限（百炼 10 条），所以 calls≈texts/10；")
    print("    Fake 一批打完所以 calls=1 —— 别拿离线数去估线上成本，比值会变。")

    rule("② 跑一轮问答，看完整指标")
    service.metrics.reset()          # 把索引阶段的样本清掉，只留问答的
    t0 = time.perf_counter()
    for q in QUESTIONS:
        service.ask(q)
    print(f"  {len(QUESTIONS)} 次问答，总耗时 {time.perf_counter() - t0:.1f}s")
    print()
    print(render_report(service.metrics.snapshot()))

    rule("③ 慢在哪：四段耗时占比")
    stage_bar(service.metrics.snapshot())

    rule("④ 库外问题：拒答到底省没省到钱，拿分数说话")
    st = service.settings
    scored = retriever.retrieve(OUT_OF_KB, top_k=st.top_k,
                                mode="hybrid" if st.hybrid else "vector")
    top_scores = "、".join(f"{sc.score:.3f}" for sc in scored[:3]) or "（空）"
    print(f"  问题：{OUT_OF_KB}")
    print(f"  top3 召回分数：{top_scores}    min_score={st.min_score}")
    before_llm = service.metrics.counter(Names.LLM_CALLS)
    answer = service.ask(OUT_OF_KB)
    delta = service.metrics.counter(Names.LLM_CALLS) - before_llm
    print(f"  回答：{answer.answer[:50]}")
    print(f"  refused = {answer.refused}      llm.calls 增量 = {delta:.0f}")
    if delta == 0:
        print("  → 闸门拦住了：生成侧一次没调，这一问省下一整次 LLM 的钱。")
        if scored:
            print(f"    注意粗召回看着都够格（最高 {max(s.score for s in scored):.3f} > "
                  f"{st.min_score}），最后却没进 prompt ——")
            print("    中间还有 rerank 重打分这一道，决定成败的是重打分后的分数。")
    else:
        print(f"  → 闸门没拦住：召回分数仍高于 min_score={st.min_score}，资料照样进了 prompt，")
        print("    「没有相关资料」是 LLM 自己看出来的，不是闸门挡的 —— 钱一分没省。")
        print("    min_score 必须按这个 embedding 的分数分布重新校准：")
        print("    余弦的绝对量级在不同模型间不可比，0.2 在别的模型上可能是个死门槛，")
        print("    在这里却形同虚设。上面「落在最低桶占 0%」就是同一个事实的另一面。")

    rule("⑤ 并发下计数不丢（4 线程同时问）")
    before = service.metrics.counter(Names.REQUESTS)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: service.ask(QUESTIONS[0]), range(4)))
    after = service.metrics.counter(Names.REQUESTS)
    print(f"  rag.requests：{before:.0f} → {after:.0f}（增量 {after - before:.0f}）")
    print("  → 增量必须正好等于线程数。少一个就说明计数在并发下丢了")
    print("    （dict 的 += 不是原子操作，MetricsRegistry 里那把锁就是为这个加的）。")

    rule("⑥ 口径纪律")
    print("  · rag.request.latency  = 端到端（含检索、含拒答）")
    print("  · rag.generate.latency = 生成段（语义 3 重试两次就记两次）")
    print("  · llm.latency          = 单次 LLM 调用（不含重试），与上面那个不是一回事")
    print("  · rag.retrieve.score   = 截断之后、min_score 过滤之前 —— 这才是 top_k 拿到的质量")
    print("  · 指标只累加不自动清零，进程重启归零；跨进程对比要自己落盘")

    rule()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
