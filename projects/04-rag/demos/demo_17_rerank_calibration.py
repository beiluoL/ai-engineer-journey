"""真实 reranker A/B + min_score 阈值校准（16 章）。

    python demos/demo_17_rerank_calibration.py          # 真实 embedding + 真实 DeepSeek 精排
    python demos/demo_17_rerank_calibration.py --fake   # 全离线（只看代码路径通不通）

15 章的可观测性报告甩出一个结论：min_score=0.2 对百炼 embedding **形同虚设**
（30 个召回样本最低 0.228，一条都没拦）。这一章接着回答两个问题：

    1. 精排到底有没有用 —— noop / fake / llm 三种实现在同一批真实召回上做 A/B
    2. 阈值该怎么定 —— 按正负样本扫描出 precision/recall 曲线，而不是拍脑袋

评估刻意**只测检索侧**：rerank 影响的是「哪些片段进了 prompt」，
跟生成质量无关。让 30 条 × 3 种配置都去真实生成一遍，既慢又贵，
还会把「生成抖动」混进「检索差异」里（14 章已经证明同一问题连问 5 次有 4 种答案）。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import WIDTH, head, rule  # noqa: E402

from rag.cli import build_components  # noqa: E402
from rag.evaluation import EvalCase, _source_name  # noqa: E402
from rag.llm import DeepSeekLLMClient  # noqa: E402
from rag.reranker import FakeReranker, LLMReranker, NoopReranker  # noqa: E402

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "eval_cases.json"
TOP_K = 5
FETCH_K = 20


def load_cases() -> list[EvalCase]:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return [EvalCase(**item) for item in data]


def retrieval_metrics(runs: list[list]) -> dict:
    """runs: 每条 case 一个列表，元素是最终进 prompt 的候选 source 名（已排序）。"""
    n = len(runs)
    hits3 = hits5 = 0
    rr = 0.0
    for i, sources in enumerate(runs):
        want = _source_name(CASES[i].expected_source)
        ranks = [j + 1 for j, s in enumerate(sources) if s == want]
        if ranks:
            rr += 1.0 / ranks[0]
            hits5 += 1
            if ranks[0] <= 3:
                hits3 += 1
    return {"hit@3": hits3 / n if n else 0, "hit@5": hits5 / n if n else 0,
            "mrr": rr / n if n else 0}


def main() -> None:
    fake = "--fake" in sys.argv
    head("python demos/demo_17_rerank_calibration.py" + (" --fake" if fake else ""))

    llm = None
    if not fake:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            print("缺少 DEEPSEEK_API_KEY；改用 --fake 跑离线版本")
            return
        llm = DeepSeekLLMClient(api_key=api_key)

    CASES.extend(load_cases())
    answerable = [c for c in CASES if not c.should_refuse]
    print(f"评测集：{len(CASES)} 条（可回答 {len(answerable)} + 应拒答 "
          f"{len(CASES) - len(answerable)}），fetch_k={FETCH_K} top_k={TOP_K}")
    print(f"检索侧：{'FakeEmbedding（离线）' if fake else '百炼 text-embedding-v3（真实）'}")

    # ---- 装配一次，索引一次；三种 reranker 共用同一批粗召回 ----
    t0 = time.perf_counter()
    settings, _emb, store, retriever, _svc = build_components(
        profile="dev", fake=fake, top_k=TOP_K, index_paths=["data/"], quiet=True, llm=llm)
    print(f"建索引：{store.count()} 个 chunk，耗时 {time.perf_counter() - t0:.1f}s")

    mode = "hybrid" if settings.hybrid else "vector"
    t0 = time.perf_counter()
    raw: list[list] = []
    for c in CASES:
        raw.append(retriever.retrieve(c.question, top_k=FETCH_K, mode=mode,
                                      mmr=settings.mmr))
    print(f"粗召回 {len(CASES)} 条 × {FETCH_K} 候选，耗时 {time.perf_counter() - t0:.1f}s")

    # ================= ① 三种 reranker A/B =================
    rule("① 精排 A/B：noop / fake-keyword / llm-listwise（同一批粗召回）")
    print(f"{'reranker':<16}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}{'单次耗时':>12}")
    print("-" * WIDTH)
    variants: list[tuple[str, object]] = [("noop", NoopReranker()),
                                          ("fake-keyword", FakeReranker())]
    if not fake:
        variants.append(("llm-listwise", LLMReranker(llm=llm)))
    else:
        print("# 离线模式跳过 llm-listwise（它要真调 DeepSeek）")

    scored_by_variant: dict[str, list] = {}
    for name, rr_ in variants:
        runs: list[list] = []
        kept: list[list] = []          # 每条 case 最终进 prompt 的 (source, score)
        t_start = time.perf_counter()
        for c, cands in zip(CASES, raw):
            top = rr_.rerank(c.question, cands, top_n=TOP_K)[:TOP_K]
            kept.append([(_source_name(s.chunk.metadata.get("source", "")), s.score)
                         for s in top])
            runs.append([src for src, _ in kept[-1]])
        elapsed = (time.perf_counter() - t_start) / max(len(CASES), 1)
        scored_by_variant[name] = kept
        m = retrieval_metrics(runs)
        print(f"{name:<16}{m['hit@3']:>8.3f}{m['hit@5']:>8.3f}{m['mrr']:>8.3f}"
              f"{elapsed * 1000:>10.0f}ms")
    print("  → 三种实现的分数**量纲不同**，只有 hit/MRR 这种排序指标能横向比，")
    print("    分数本身不能（07 章坑 1：rerank 分数与余弦分数语义不同）。")

    # 降级次数是真实信号：LLM 精排不是「调一次就完事」，要盯它有没有按格式答
    for name, rr_ in variants:
        if isinstance(rr_, LLMReranker):
            print(f"  → llm-listwise 降级 {rr_.degraded}/{len(CASES)} 次"
                  f"（模型没返回编号序列，退回原顺序）")
            for q in rr_.degraded_queries[:3]:
                print(f"      降级样本：{q}")

    # ================= ② 阈值扫描：余弦量纲 =================
    rule("② 阈值扫描：关掉 rerank 时，分数是余弦相似度")
    scan(CASES, scored_by_variant["noop"], title="余弦量纲")

    # ================= ③ 阈值扫描：rerank 量纲 =================
    rule("③ 阈值扫描：开着 fake-keyword 精排时，分数是关键词覆盖度")
    scan(CASES, scored_by_variant["fake-keyword"], title="关键词量纲")

    # ================= ④ 结论 =================
    rule("④ 口径纪律")
    print("做法：  ① 阈值必须绑定「分数是谁产生的」——换 embedding 或换 reranker")
    print("        就要重新扫一遍，跨模型复用阈值等于没设阈值；")
    print("        ② 只看 hit/MRR 排序指标横向比实现，分数绝对值不跨实现比；")
    print("        ③ 阈值扫描用「进 prompt 的那几条」而不是全库候选，")
    print("          因为 min_score 只在截断之后才生效。")


def scan(cases: list[EvalCase], kept: list[list], title: str) -> None:
    """对 (source, score) 列表按阈值扫描，输出 precision/recall/F1。

    标注方式（不用人工标注）：expected_source 命中的候选=正样本，其余=负样本。
    拒答案例的 expected_source 是占位符，全部排除，否则会把噪声算成负样本。
    """
    labeled: list[tuple[float, bool]] = []
    for c, items in zip(cases, kept):
        if c.should_refuse:
            continue
        want = _source_name(c.expected_source)
        for src, score in items:
            labeled.append((score, src == want))

    total_pos = sum(1 for _, p in labeled if p)
    scores = [s for s, _ in labeled]
    print(f"样本 {len(labeled)} 条（正 {total_pos} / 负 {len(labeled) - total_pos}），"
          f"分数范围 [{min(scores):.3f}, {max(scores):.3f}]")
    print(f"当前 min_score = {0.2}")
    print()
    print(f"{'min_score':>10}{'保留':>7}{'precision':>11}{'recall':>9}{'F1':>8}")
    print("-" * WIDTH)

    thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    best = (0.0, -1.0)
    rows: list[tuple] = []
    for t in thresholds:
        tp = sum(1 for s, p in labeled if s >= t and p)
        kept_n = sum(1 for s, _ in labeled if s >= t)
        precision = tp / kept_n if kept_n else 0.0
        recall = tp / total_pos if total_pos else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        rows.append((t, kept_n, precision, recall, f1))
        if f1 > best[1]:
            best = (t, f1)
    for t, kept_n, p, r, f1 in rows:
        mark = "  ← F1 最优" if t == best[0] else ""
        print(f"{t:>10.2f}{kept_n:>7}{p:>11.3f}{r:>9.3f}{f1:>8.3f}{mark}")

    at_default = next(r for r in rows if abs(r[0] - 0.2) < 1e-9)
    print(f"  → 默认 0.2 在「{title}」下保留 {at_default[1]}/{len(labeled)} 条"
          f"（拦掉 {len(labeled) - at_default[1]} 条），precision {at_default[2]:.3f}")
    print(f"  → F1 最优阈值 {best[0]:.2f}（F1={best[1]:.3f}）；"
          f"阈值是**按量纲标定**的，不是普适常数")


CASES: list[EvalCase] = []

if __name__ == "__main__":
    main()
