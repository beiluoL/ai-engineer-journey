from __future__ import annotations

import numpy as np
import pytest

from ie.compare import evaluate_models, paired_compare, summarize


@pytest.mark.parametrize(
    "values,mean",
    [([1], 1), ([1, 2], 1.5), ([1, 2, 3], 2), ([-1, 0, 1], 0), ([0.25, 0.75], 0.5)],
)
def test_summarize_mean(values, mean):
    result = summarize(values)
    assert result["mean"] == pytest.approx(mean)
    assert result["n"] == len(values)


@pytest.mark.parametrize(
    "baseline,challenger,wins,losses,ties,stable,flip",
    [
        ([1, 1, 1], [2, 2, 2], 3, 0, 0, True, False),
        ([2, 2, 2], [1, 1, 1], 0, 3, 0, True, False),
        ([1, 1, 1], [1, 1, 1], 0, 0, 3, False, False),
        ([1, 1, 1], [2, 0, 2], 2, 1, 0, False, True),
        ([1, 1, 1], [2, 1, 2], 2, 0, 1, False, False),
    ],
)
def test_paired_signs(baseline, challenger, wins, losses, ties, stable, flip):
    result = paired_compare(baseline, challenger)
    assert (result["wins"], result["losses"], result["ties"]) == (wins, losses, ties)
    assert result["stable"] is stable
    assert result["noise_flip"] is flip


def test_lower_is_better_reverses_improvement():
    result = paired_compare([2, 2], [1, 1], lower_is_better=True)
    assert result["wins"] == 2
    assert result["mean_improvement"] == 1.0


def test_evaluate_models_uses_same_seeds():
    seen = []

    def evaluator(offset, seed):
        seen.append((offset, seed))
        return offset + seed

    result = evaluate_models({"a": 0, "b": 1}, [0, 1, 2], evaluator, baseline="a")
    assert result["ranking"] == ["b", "a"]
    assert result["paired"]["b"]["wins"] == 3
    assert len(seen) == 6


def test_shape_mismatch_rejected():
    with pytest.raises(ValueError):
        paired_compare([1], [1, 2])


def test_empty_summary_rejected():
    with pytest.raises(ValueError):
        summarize([])
