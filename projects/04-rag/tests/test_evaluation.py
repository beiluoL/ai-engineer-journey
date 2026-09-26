"""evaluation.py：三段式评估（10 章）。口径固定，前后只比同一份评测集。"""

from __future__ import annotations

import json
from pathlib import Path

from rag.evaluation import (EvalCase, EvalReport, build_default_eval_cases,
                           check_expected_sources, evaluate)
from rag.llm import BaseLLMClient


class EchoLLM(BaseLLMClient):
    """最简单的替身：把第一条引用编号写进答案，方便构造「关键词命中 / 未命中」。"""

    model_name = "echo"

    def __init__(self, answer: str = "生成器能省内存"):
        self.answer = answer

    def chat(self, messages):
        return self.answer


ANSWERS = {
    "hit": "生成器能省内存",                        # 命中评估关键词
    "miss": "无从得知",                              # 答案里一个关键词都没有
    "refuse": "知识库中没有相关资料，无法回答这个问题。",  # 应拒答
}


def _service(kind: str = "hit"):
    from rag.assembler import ContextAssembler
    from rag.cli import build_components
    from rag.pipeline import RAGService
    from rag.reranker import NoopReranker

    # 用仓库里真实的 data/ 语料：评测集的 expected_source 就是按它的文件名写的
    data_dir = Path(__file__).resolve().parents[1] / "data"
    settings, _emb, _store, retriever, _svc = build_components(
        profile="dev", fake=True, top_k=5, index_paths=[str(data_dir)])
    llm = EchoLLM(ANSWERS[kind])
    return RAGService(retriever=retriever, reranker=NoopReranker(),
                      assembler=ContextAssembler(min_score=settings.min_score),
                      llm=llm, settings=settings)


def test_evaluate_全部命中时指标为满分():
    cases = [EvalCase(question="生成器为什么省内存？", expected_source="data/python-generators.md",
                      expected_keywords=("生成器",))]
    report = evaluate(_service("hit"), cases)
    assert report.n_cases == 1
    assert report.hit_rate_at_3 == 1.0 and report.mrr == 1.0
    assert report.context_hit_rate == 1.0 and report.keyword_pass_rate == 1.0
    assert not report.failed_cases


def test_evaluate_关键词没出现在答案里会被抓出来():
    cases = [EvalCase(question="生成器为什么省内存？", expected_source="data/python-generators.md",
                      expected_keywords=("生成器", "yield"))]
    report = evaluate(_service("hit"), cases)               # 答案只说了「生成器能省内存」
    assert report.keyword_pass_rate == 0.0                  # 缺 yield
    assert report.failed_cases and "缺关键词" in report.failed_cases[0]


def test_evaluate_正确文档没被召回时不算命中():
    cases = [EvalCase(question="生成器为什么省内存？", expected_source="data/nope.md")]
    report = evaluate(_service("hit"), cases)
    assert report.hit_rate_at_5 == 0.0 and report.mrr == 0.0
    assert "未命中" in report.failed_cases[0]


def test_evaluate_拒答案例只算refusal():
    cases = [EvalCase(question="今天天气？", expected_source="nonexistent.md",
                      should_refuse=True)]
    report = evaluate(_service("refuse"), cases)
    assert report.refusal_pass_rate == 1.0 and report.keyword_pass_rate == 0.0


def test_指标都落在0到1之间():
    report = evaluate(_service("hit"), build_default_eval_cases())
    for name in ("hit_rate_at_3", "hit_rate_at_5", "mrr", "context_hit_rate",
                 "keyword_pass_rate", "refusal_pass_rate"):
        assert 0.0 <= getattr(report, name) <= 1.0


def test_summary_可读():
    report = evaluate(_service("hit"), build_default_eval_cases())
    text = report.summary()
    assert "hit@3=" in text and "mrr=" in text and "n=" in text


def test_dump_与load_可往返():
    report = evaluate(_service("hit"), build_default_eval_cases())
    report.dump("tests/.tmp-eval-report.json")
    try:
        back = EvalReport.load("tests/.tmp-eval-report.json")
        assert back.n_cases == report.n_cases
        with open("tests/.tmp-eval-report.json", encoding="utf-8") as fh:
            assert json.load(fh)["n_cases"] == report.n_cases
    finally:
        import os

        os.remove("tests/.tmp-eval-report.json")


def test_check_expected_sources_能自检评测集():
    cases = build_default_eval_cases()
    assert check_expected_sources(cases, [c.expected_source for c in cases]) == []
    broken = [EvalCase(question="q", expected_source="not-here.md")]
    assert check_expected_sources(broken, ["other.md"])


def test_eval_report_字段即口径():
    r = EvalReport()
    assert r.n_cases == 0 and r.mrr == 0.0
