"""10 章：evaluate() 跑一遍内置评测集，看三段指标 + 失败明细。

三段口径：
    检索段   hit_rate@k / mrr          （黄金文档有没有被召回来，第几名）
    组装段   context_hit_rate          （黄金文档有没有真的进 prompt）
    生成段   keyword_pass / refusal    （答案里有没有那个关键词 / 该拒的是否拒了）

只看总分没有用：hit_rate 低要改检索，hit_rate 高但答案错要改 prompt。
"""

from __future__ import annotations

from pathlib import Path

from common import head, note, rule

from rag.cli import build_components
from rag.evaluation import EvalCase, build_default_eval_cases, evaluate

QUERIES = build_default_eval_cases()


def _rank_of(answer, expected: str) -> int:
    """黄金文档在本次召回里的名次（1 起）；没召回返回 0。"""
    name = Path(expected).name
    for i, src in enumerate(answer.retrieved_sources, start=1):
        if Path(src).name == name:
            return i
    return 0


def main() -> int:
    head("python demos/demo_10_evaluate.py")
    settings, _emb, store, _retr, service = build_components(
        profile="dev", fake=True, top_k=5, index_paths=["data/"])
    print(f"评测集 {len(QUERIES)} 条，top_k={settings.top_k}，"
          f"min_score={settings.min_score}，向量库 {store.count()} 个 chunk")

    rule("① 逐条明细（问答一次问一次，指标就是这些行的汇总）")
    print(f"    {'#':<3}{'question':<34}{'召回名次':<10}{'进上下文':<10}"
          f"{'关键词':<8}{'拒答'}")
    hits: list[int] = []
    for i, case in enumerate(QUERIES):
        answer = service.ask(case.question)
        rank = _rank_of(answer, case.expected_source)
        hits.append(rank)
        in_ctx = bool(answer.used_chunks) and any(
            Path(c.chunk.source).name == Path(case.expected_source).name
            for c in answer.used_chunks)
        kw = "—" if case.should_refuse else (
            "OK" if all(k in answer.answer for k in case.expected_keywords)
            else "缺 " + "/".join(k for k in case.expected_keywords
                                 if k not in answer.answer))
        print(f"    {i:<3}{case.question[:32]:<34}"
              f"{('%d' % rank) if rank else '未召回':<10}"
              f"{('是' if in_ctx else '否'):<10}{str(kw):<14}"
              f"{('是' if answer.refused else '—') if case.should_refuse else '—'}")

    rule("② evaluate() 汇总（和 ① 的明细必须能对上）")
    cases: list[EvalCase] = list(QUERIES)
    report = evaluate(service, cases)
    print(f"    n_cases           = {report.n_cases}")
    print(f"    hit_rate@3        = {report.hit_rate_at_3:.3f}"
          f"   （前 3 条里有没有黄金文档：{sum(1 for r in hits if 0 < r <= 3)}/{len(hits)}）")
    print(f"    hit_rate@5        = {report.hit_rate_at_5:.3f}")
    print(f"    mrr               = {report.mrr:.3f}"
          f"   （= Σ 1/名次，未召回记 0：{'/'.join(str(round(1 / r, 3)) if r else '0' for r in hits)}）")
    print(f"    context_hit_rate  = {report.context_hit_rate:.3f}")
    print(f"    keyword_pass_rate = {report.keyword_pass_rate:.3f}")
    print(f"    refusal_pass_rate = {report.refusal_pass_rate:.3f}")

    rule("③ 失败明细：定位是哪一段出了错")
    if report.failed_cases:
        for line in report.failed_cases:
            print(f"    - {line}")
        print("    hit_rate 低 → 改检索（换 embedding / 调 chunk / 开 hybrid）")
        print("    hit_rate 高但 keyword 挂 → 改 prompt 或换更好的生成模型")
    else:
        print("    （无）")

    rule("④ 报告可落盘 / 可回读：前后对比必须同口径")
    report.dump(Path("data").parent / "tests" / ".tmp" / "report.json")
    back = type(report).load("tests/.tmp/report.json")
    print(f"    dump → load 往返一致：{back.summary() == report.summary()}")
    print(f"    {report.summary()}")

    note("同一份评测集、同一份 corpus，指标才能前后对比；换语料必须同步换评测集（10 坑 4）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
