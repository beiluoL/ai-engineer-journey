"""demo_06 —— Java 面试助手：一个最小可用的「检索 + 生成」应用。

这条 demo 把前面几步串成一个闭环：
    data/java_interview.json（本地知识）
        → 字符二元组相似度检索（不联网、无 embedding 依赖）
        → 命中条目塞进 prompt 当上下文
        → DeepSeek 生成回答

两部分都要求真实：
- Part A：检索质量**可测量**。我手工写了 8 条「转述query」构成一个 mini 评测集，
  每条标注必须命中哪些关键词，统计 recall@1 / recall@3。
  用转述而不是原句提问，是为了避免「字符串一模一样」造成的虚假满分。
- Part B：一次真实 LLM 调用，验证「检索到的上下文 + 生成」这条链路能端到端跑通。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PIPELINES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINES))

from _common import Tee, Timer, fmt_table, rule  # noqa: E402
from llm_client import call_chat  # noqa: E402

DATA = PIPELINES.parent / "data" / "java_interview.json"

# mini 评测集：query 是原问题的「转述」，must 是正确答案条目里必须出现的关键词组合。
EVAL_SET = [
    {"query": "聊聊 ConcurrentHashMap 是怎么做到并发安全的", "must": ["ConcurrentHashMap", "线程安全"]},
    {"query": "volatile 能保证复合操作的原子性么", "must": ["volatile", "原子性"]},
    {"query": "说说线程池刚初始化的时候要配哪些参数", "must": ["线程池", "参数"]},
    {"query": "任务太多被线程池拒绝了怎么办", "must": ["拒绝策略"]},
    {"query": "一个 class 从字节码到能被 new 出来经历了什么", "must": ["类加载"]},
    {"query": "JDK8 的 HashMap 底层数据结构长什么样", "must": ["HashMap", "底层原理"]},
    {"query": "synchronized 和 ReentrantLock 该怎么选", "must": ["ReentrantLock"]},
    {"query": "为什么 Redis 的读写延迟能那么低", "must": ["Redis"]},
]

FINAL_QUERY = "请解释 ThreadLocal 为什么容易引发内存泄漏，以及正确的处理姿势。"


def bigrams(text: str) -> set[str]:
    """字符二元组。中文没有空格分词，二元组是零依赖场景下最划算的粗糙表示。"""
    cleaned = "".join(ch for ch in text if not ch.isspace())
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def load_corpus() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def retrieve(corpus: list[dict], query: str, top_k: int = 3) -> list[tuple[int, float]]:
    """返回 [(索引, 分数)]，分数 = query 二元组被文档覆盖的比例。"""
    q = bigrams(query)
    scored = []
    for idx, item in enumerate(corpus):
        doc = bigrams(item["instruction"] + item["output"])
        if not q:
            continue
        scored.append((idx, len(q & doc) / len(q)))
    scored.sort(key=lambda t: -t[1])
    return scored[:top_k]


def main() -> None:
    with Tee("demo_06_java_interview_app") as out:
        out.print(rule("demo_06：Java 面试助手（检索 + 生成）"))
        out.print("")

        corpus = load_corpus()
        out.print(f"本地知识库：{DATA.name}  共 {len(corpus)} 条")
        out.print("检索方式：字符二元组相似度（无 embedding、不联网，纯本地算术）")
        out.print("")

        out.print(rule("Part A：检索质量评测（8 条转述 query）"))
        rows = []
        hit1 = hit3 = 0
        with Timer() as t_retr:
            for case in EVAL_SET:
                top = retrieve(corpus, case["query"], top_k=3)
                top1_idx = top[0][0]
                ins1 = corpus[top1_idx]["instruction"]
                ok1 = all(k in ins1 for k in case["must"])
                ok3 = any(all(k in corpus[i]["instruction"] for k in case["must"]) for i, _ in top)
                hit1 += int(ok1)
                hit3 += int(ok3)
                rows.append([
                    case["query"][:18],
                    ins1[:22],
                    f"{top[0][1]:.2f}",
                    "Y" if ok1 else "N",
                    "Y" if ok3 else "N",
                ])
        out.lines(fmt_table(
            ["query(截断)", "Top1命中条目(截断)", "分数", "R@1", "R@3"],
            rows,
        ))
        out.print("")
        n = len(EVAL_SET)
        out.print(f"   recall@1 = {hit1}/{n} = {hit1 / n:.2%}")
        out.print(f"   recall@3 = {hit3}/{n} = {hit3 / n:.2%}")
        out.print(f"   全库 {len(corpus)} 条检索总耗时 = {t_retr.seconds * 1000:.1f} ms")
        out.print("   注：这是刻意用最朴素的词面相似度，结果代表『零成本基线』，")
        out.print("       换成 embedding 检索（P04 已实践）通常还能再上一截。")
        out.print("")

        out.print(rule("Part B：端到端问答（检索到的上下文 + 生成）"))
        out.print(f"   提问：{FINAL_QUERY}")
        hits = retrieve(corpus, FINAL_QUERY, top_k=2)
        out.print("   检索到的参考条目：")
        context_parts = []
        for i, score in hits:
            item = corpus[i]
            out.print(f"     - [{score:.2f}] {item['instruction']}")
            context_parts.append(f"参考：{item['instruction']}\n{item['output']}")
        context = "\n\n".join(context_parts)
        out.print("")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是资深 Java 面试官。优先依据下面提供的参考资料作答；"
                    "资料不足时再用自己的知识补充，但不要编造 API 或参数。"
                    "回答控制在 150 字以内。"
                ),
            },
            {"role": "user", "content": f"{context}\n\n问题：{FINAL_QUERY}"},
        ]
        result = call_chat(messages, temperature=0.3, max_tokens=400)
        out.print(f"   model={result.model}  finish_reason={result.finish_reason}")
        out.print(f"   tokens(prompt/completion) = "
                  f"{result.usage.prompt_tokens}/{result.usage.completion_tokens}")
        out.print(f"   latency = {result.latency_s:.3f} s")
        out.print("")
        out.print(rule("生成的回答"))
        out.print(f"   {result.content}")
        out.print("")

        out.save_json({
            "corpus_size": len(corpus),
            "recall_at_1": hit1 / n,
            "recall_at_3": hit3 / n,
            "retrieval_ms": round(t_retr.seconds * 1000, 2),
            "detail": [
                {"query": c["query"], "top1": rows[i][1], "score": rows[i][2],
                 "recall1": rows[i][3] == "Y", "recall3": rows[i][4] == "Y"}
                for i, c in enumerate(EVAL_SET)
            ],
            "final_query": FINAL_QUERY,
            "usage": result.usage.as_dict(),
            "latency_s": round(result.latency_s, 4),
            "answer": result.content,
        })


if __name__ == "__main__":
    main()
