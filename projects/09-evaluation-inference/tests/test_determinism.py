from __future__ import annotations

import numpy as np
import pytest

from ie.autoeval import evaluate_answer
from ie.batching import Request, simulate_continuous
from ie.compare import evaluate_models
from ie.evalset import build_evaluation_set
from ie.quantize import quantize_int4


def records():
    return [{"instruction": f"问题 {i}", "input": "", "output": f"答案 {i}"} for i in range(20)]


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 999])
def test_eval_split_is_deterministic(seed):
    first = build_evaluation_set(records(), 5, seed)
    second = build_evaluation_set(records(), 5, seed)
    assert first.heldout == second.heldout


@pytest.mark.parametrize("seed", [0, 2, 11, 31])
def test_quantization_is_deterministic(seed):
    weights = np.random.default_rng(seed).normal(size=(16, 8))
    first = quantize_int4(weights, "per_channel")
    second = quantize_int4(weights, "per_channel")
    assert np.array_equal(first.codes, second.codes)
    assert np.array_equal(first.scale, second.scale)


def test_autoeval_is_deterministic():
    args = ("CAS 保证原子性。", "CAS 是原子操作。", ["CAS", "原子性"])
    assert evaluate_answer(*args) == evaluate_answer(*args)


def test_batching_is_deterministic():
    reqs = [Request("a", 0, 3), Request("b", 1, 7), Request("c", 2, 2)]
    assert simulate_continuous(reqs, 2, 0.25) == simulate_continuous(reqs, 2, 0.25)


def test_comparison_seed_results_are_deterministic():
    evaluator = lambda offset, seed: float(np.random.default_rng(seed).normal() + offset)
    one = evaluate_models({"a": 0, "b": 1}, [0, 1, 2], evaluator)
    two = evaluate_models({"a": 0, "b": 1}, [0, 1, 2], evaluator)
    assert one == two
