from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ie.metrics import (
    answer_coverage,
    calibration,
    expected_calibration_error,
    metrics_from_logits,
    perplexity,
    reliability_bins,
    token_accuracy,
)


class FixedModel:
    def __init__(self, table):
        self.table = np.asarray(table, dtype=np.float64)

    def __call__(self, x, mask=None):
        return SimpleNamespace(data=self.table[np.asarray(x)])


@pytest.mark.parametrize("classes", [2, 3, 4, 5, 8, 16, 32, 64])
def test_perfect_logits_have_unit_perplexity(classes):
    targets = np.arange(6) % classes
    logits = np.full((6, classes), -100.0)
    logits[np.arange(6), targets] = 100.0
    result = metrics_from_logits(logits, targets)
    assert result["ppl"] == pytest.approx(1.0, abs=1e-12)
    assert result["token_accuracy"] == 1.0


@pytest.mark.parametrize("n_bins", [1, 2, 5, 10, 20])
def test_perfect_calibration_has_zero_ece(n_bins):
    ece, rows = expected_calibration_error(np.ones(12), np.ones(12), n_bins)
    assert ece == pytest.approx(0.0)
    assert sum(row["count"] for row in rows) == 12


@pytest.mark.parametrize("size,n_bins", [(1, 2), (7, 3), (17, 5), (31, 10), (100, 7)])
def test_reliability_bins_conserve_samples(size, n_bins):
    confidence = np.linspace(0, 1, size)
    correct = np.arange(size) % 2
    rows = reliability_bins(confidence, correct, n_bins)
    assert len(rows) == n_bins
    assert sum(row["count"] for row in rows) == size


def test_mask_excludes_wrong_prediction():
    logits = np.array([[[10.0, 0.0], [10.0, 0.0]]])
    targets = np.array([[0, 1]])
    result = metrics_from_logits(logits, targets, np.array([[1.0, 0.0]]))
    assert result["token_accuracy"] == 1.0
    assert result["n_tokens"] == 1


def test_fixed_model_metrics():
    table = np.array([[9.0, 0.0], [0.0, 9.0]])
    model = FixedModel(table)
    examples = [(np.array([0, 1]), np.array([0, 1]), np.ones(2))]
    assert perplexity(model, examples) < 1.001
    assert token_accuracy(model, examples) == 1.0
    assert calibration(model, examples, n_bins=4)["ece"] < 0.001


def test_answer_coverage():
    examples = [
        (np.array([1, 2]), np.array([2, 3]), np.array([0.0, 1.0])),
        (np.array([1, 2, 3]), np.array([2, 3, 4]), np.array([0.0, 1.0, 1.0])),
    ]
    result = answer_coverage(examples)
    assert result == {"answer_tokens": 3, "total_tokens": 5, "coverage": 0.6, "n_examples": 2}


@pytest.mark.parametrize("bad_conf", [-0.1, 1.1])
def test_bad_confidence_rejected(bad_conf):
    with pytest.raises(ValueError):
        reliability_bins(np.array([bad_conf]), np.array([1.0]))


def test_empty_examples_rejected():
    with pytest.raises(ValueError):
        perplexity(FixedModel([[1.0, 0.0]]), [])
