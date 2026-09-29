from __future__ import annotations

import pytest

from ie.autoeval import (
    aggregate_scores,
    evaluate_answer,
    format_compliance,
    keyword_coverage,
    length_reasonableness,
    rank_answers,
    repetition_score,
)
from ie.benchmark import Benchmark, BenchmarkTask


REFERENCE = "volatile 保证可见性和有序性，但不能保证复合操作的原子性。"
KEYWORDS = ["volatile", "可见性", "有序性", "原子性"]


def test_full_answer_scores_high():
    assert evaluate_answer(REFERENCE, REFERENCE, KEYWORDS).total > 85


def test_empty_answer_scores_low():
    assert evaluate_answer("", REFERENCE, KEYWORDS).total < 5


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_keyword_coverage_monotonic(count):
    answer = " ".join(KEYWORDS[:count])
    assert keyword_coverage(answer, KEYWORDS) == pytest.approx(count / 4)


@pytest.mark.parametrize(
    "answer,minimum",
    [("", 0.0), ("短", 0.3), ("这是结论。", 0.5), ("1. 第一。\n2. 第二。", 0.9)],
)
def test_format_scores(answer, minimum):
    assert format_compliance(answer) >= minimum


@pytest.mark.parametrize("ratio", [0.25, 0.5, 0.75, 1.0, 1.5, 2.0])
def test_length_score_bounded(ratio):
    ref = "a" * 100
    answer = "b" * int(100 * ratio)
    score = length_reasonableness(answer, ref)
    assert 0.0 <= score <= 1.0


def test_repetition_penalty():
    assert repetition_score("abcdefghi") > repetition_score("abcabcabcabcabc")


def test_aggregate_count_and_mean():
    scores = [evaluate_answer(REFERENCE, REFERENCE, KEYWORDS), evaluate_answer("", REFERENCE, KEYWORDS)]
    result = aggregate_scores(scores)
    assert result["n"] == 2
    assert result["total"] == pytest.approx(sum(score.total for score in scores) / 2)


def test_rank_answers():
    ranking = rank_answers({"good": [REFERENCE], "bad": [""]}, [REFERENCE], [KEYWORDS])
    assert [row["model"] for row in ranking] == ["good", "bad"]


def test_benchmark_ranking_and_details():
    task = BenchmarkTask("t1", "问题", REFERENCE, tuple(KEYWORDS), "并发")
    bench = Benchmark("test", [task])
    rows = bench.compare({"good": lambda _p: REFERENCE, "bad": lambda _p: ""})
    assert rows[0]["model"] == "good"
    assert rows[0]["rank"] == 1
    assert rows[0]["details"][0]["task_id"] == "t1"


def test_benchmark_rejects_duplicate_ids():
    task = BenchmarkTask("same", "p", "r")
    with pytest.raises(ValueError):
        Benchmark("bad", [task, task])


def test_benchmark_rejects_empty_tasks():
    with pytest.raises(ValueError):
        Benchmark("bad", [])
