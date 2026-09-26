"""真实 RAG 评估：30 条 EvalCase 跑 Hit Rate / MRR / 忠实度（14 章）。

    python demos/demo_15_real_eval.py              # 真实 embedding + 真实 DeepSeek
    python demos/demo_15_real_eval.py --fake       # 全离线对比（看离线指标虚高）

重点不在「分数高不高」，而在：
1. 同样的评测集、同样的口径，top_k=3 和 top_k=5 差多少；
2. 离线（Fake）和真实（DashScope + DeepSeek）的指标落差有多大；
3. 忠实度审计能捞出哪些「看起来对、其实编」的答案。
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import WIDTH, head, rule  # noqa: E402

from rag.cli import build_components  # noqa: E402
from rag.evaluation import (EvalCase, EvalReport, check_answer_faithfulness,  # noqa: E402
                           evaluate)  # noqa: E402
from rag.llm import DeepSeekLLMClient  # noqa: E402
from rag.pipeline import RAGService  # noqa: E402
from rag.settings import RAGSettings  # noqa: E402

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "eval_cases.json"
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "eval_report.json"


def load_cases() -> list[EvalCase]:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return [EvalCase(**item) for item in data]


def run_one(service: RAGService, cases: list[EvalCase], top_k: int) -> EvalReport:
    """固定 top_k 跑一遍，保证评测集不变，只看参数影响。"""
    # 切换 top_k：只改 service.settings 里的 top_k
    service.settings = service.settings.replace(top_k=top_k)
    return evaluate(service, cases)


def faithful_stats(service: RAGService, cases: list[EvalCase],
                   max_cases: int = 20) -> dict:
    """对非拒答案例做忠实度审计，返回均值、最差样本与注入式自测结果。"""
    ratios: list[float] = []
    unsupported_count = 0
    normal = [c for c in cases if not c.should_refuse][:max_cases]
    worst = None
    for case in normal:
        ans = service.ask(case.question)
        r = check_answer_faithfulness(ans)
        ratios.append(r.ratio)
        if r.unsupported:
            unsupported_count += len(r.unsupported)
        if worst is None or r.ratio < worst[0]:
            worst = (r.ratio, case.question, r.unsupported[:2])
    return {
        "n": len(ratios),
        "avg_ratio": sum(ratios) / len(ratios) if ratios else 0.0,
        "min_ratio": min(ratios) if ratios else 0.0,
        "unsupported_sentences": unsupported_count,
        "worst_question": worst[1] if worst else "",
        "worst_ratio": worst[0] if worst else 0.0,
    }


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    head(f"python demos/demo_15_real_eval.py {'--fake' if fake else ''}")
    print(f"  模式：{'全离线 Fake' if fake else '真实 embedding + 真实 DeepSeek'}")

    cases = load_cases()
    n_normal = sum(1 for c in cases if not c.should_refuse)
    n_refuse = len(cases) - n_normal
    print(f"  评测集：{len(cases)} 条（可回答 {n_normal} / 应拒答 {n_refuse}）")

    if fake:
        llm = None  # build_components 默认 FakeLLMClient
    else:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            print("请设置环境变量 DEEPSEEK_API_KEY")
            return 1
        llm = DeepSeekLLMClient(api_key=key)

    _settings, _emb, store, retriever, service = build_components(
        profile="dev", fake=fake, index_paths=["data/"], quiet=True, llm=llm)
    print(f"  索引完成：{store.count()} chunks，模型={store.model_name or _settings.embedding_model}")

    rule("① 口径对照：同一评测集，top_k=3 vs top_k=5")
    for k in (3, 5):
        t0 = time.perf_counter()
        report = run_one(service, cases, k)
        cost = time.perf_counter() - t0
        print(f"  top_k={k}: {report.summary()}  用时 {cost:.1f}s")
    print("  → 调 top_k 不应该是拍脑袋：先看 Hit Rate 是否已经饱和，")
    print("    再看 keyword_pass 是否随 top_k 提升；只升不降说明该换策略。")

    rule("② 最终报告：top_k=5")
    t0 = time.perf_counter()
    report = run_one(service, cases, 5)
    print(f"  {report.summary()}  总用时 {time.perf_counter()-t0:.1f}s")
    print(f"  失败明细（{len(report.failed_cases)} 条）：")
    for line in report.failed_cases[:10]:
        print(f"    - {line}")
    if len(report.failed_cases) > 10:
        print(f"    ... 还有 {len(report.failed_cases)-10} 条")

    rule("③ 忠实度审计（抽查非拒答案例）")
    if fake:
        print("  FakeLLMClient 只会复制参考资料里的句子，忠实度天然 100%，")
        print("  所以离线模式下忠实度审计没有区分度 —— 它只能用在真实 LLM 上。")
    else:
        stats = faithful_stats(service, cases)
        print(f"  抽查 {stats['n']} 条，平均忠实度={stats['avg_ratio']:.2f}，"
              f"最低={stats['min_ratio']:.2f}")
        print(f"  无出处句子数 = {stats['unsupported_sentences']}")
        print(f"  最差样本（ratio={stats['worst_ratio']:.2f}）：{stats['worst_question'][:56]}")
        print("  → 忠实度低说明资料找对了但模型在自由发挥，应改 system 规则或减 temperature。")

    rule("⑤ 可复现性：同一个问题连问 5 次")
    # 上一节出现过「两次 top_k=5 跑出 kw=0.174 / 0.261」，这里把它坐实成一条结论。
    probe = next((c for c in cases if not c.should_refuse), None)
    if probe is not None:
        seen: dict[str, int] = {}
        for _ in range(5):
            text = service.ask(probe.question).answer
            # 指纹 = 去掉空白后的长度 + 首 12 字，足以看出两次是不是同一个答案
            seen[f"len={len(text)} {text[:12]}"] = seen.get(f"len={len(text)} {text[:12]}", 0) + 1
        print(f"  问题：{probe.question}")
        print(f"  连问 5 次，得到 {len(seen)} 种不同答案：")
        for fp, cnt in seen.items():
            print(f"    ×{cnt}  {fp}")
        print("  → temperature=0 也不保证逐字可复现（云端推理节点会分流）。")
        print("    所以 keyword_pass 这类「生成质量」指标本身有抖动，")
        print("    不适合当回归门槛；判定回归要看检索类指标（hit / ctx / mrr）。")

    rule("④ 口径纪律")
    print("  · 固定评测集：data/eval_cases.json，不随模型调整而改")
    print("  · 固定评估函数：src/rag/evaluation.py evaluate()")
    print("  · 固定指标口径：hit@3 / hit@5 / mrr / ctx / kw / refuse")
    print(f"  · 报告已落盘：{REPORT_PATH}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.dump(REPORT_PATH)
    rule()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
