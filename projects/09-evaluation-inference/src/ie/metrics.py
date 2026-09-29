"""困惑度、准确率、校准与答案覆盖度指标。"""

from __future__ import annotations

from typing import Iterable

import numpy as np


def _parts(example):
    if hasattr(example, "x"):
        return np.asarray(example.x), np.asarray(example.y), np.asarray(example.mask)
    if len(example) == 2:
        x, y = example
        return np.asarray(x), np.asarray(y), np.ones_like(y, dtype=np.float64)
    x, y, mask = example
    return np.asarray(x), np.asarray(y), np.asarray(mask, dtype=np.float64)


def _pad(examples: list, use_mask: bool = True):
    parts = [_parts(example) for example in examples]
    if not parts:
        raise ValueError("examples 不能为空")
    length = max(len(x) for x, _y, _m in parts)
    batch = len(parts)
    x = np.zeros((batch, length), dtype=np.int64)
    y = np.zeros((batch, length), dtype=np.int64)
    mask = np.zeros((batch, length), dtype=np.float64)
    for row, (xi, yi, mi) in enumerate(parts):
        size = len(xi)
        x[row, :size] = xi
        y[row, :size] = yi
        mask[row, :size] = mi if use_mask else 1.0
    return x, y, mask


def _model_logits(model, x: np.ndarray) -> np.ndarray:
    result = model(x, mask=None)
    return np.asarray(result.data if hasattr(result, "data") else result, dtype=np.float64)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


def prediction_arrays(model, examples: list, batch_size: int = 4, use_mask: bool = True) -> dict:
    """收集被 mask 选中的目标概率、置信度与命中标记。"""
    if not examples:
        raise ValueError("examples 不能为空")
    target_probs: list[np.ndarray] = []
    confidences: list[np.ndarray] = []
    correct: list[np.ndarray] = []
    for start in range(0, len(examples), batch_size):
        x, y, mask = _pad(examples[start : start + batch_size], use_mask=use_mask)
        probs = _softmax(_model_logits(model, x))
        flat_p = probs.reshape(-1, probs.shape[-1])
        flat_y = y.reshape(-1)
        selected = mask.reshape(-1) > 0.5
        rows = np.arange(flat_p.shape[0])
        target_probs.append(flat_p[rows, flat_y][selected])
        pred = np.argmax(flat_p, axis=1)
        confidences.append(np.max(flat_p, axis=1)[selected])
        correct.append((pred == flat_y)[selected])
    return {
        "target_probs": np.concatenate(target_probs),
        "confidences": np.concatenate(confidences),
        "correct": np.concatenate(correct).astype(np.float64),
    }


def metrics_from_logits(logits: np.ndarray, targets: np.ndarray, mask: "np.ndarray | None" = None) -> dict:
    """不依赖模型对象，直接从 logits 计算基础指标。"""
    logits = np.asarray(logits, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.int64)
    if logits.shape[:-1] != targets.shape:
        raise ValueError(f"logits/targets 形状不匹配：{logits.shape} vs {targets.shape}")
    weights = np.ones(targets.shape, dtype=np.float64) if mask is None else np.asarray(mask, dtype=np.float64)
    if weights.shape != targets.shape or weights.sum() <= 0:
        raise ValueError("mask 形状必须匹配 targets 且至少含一个有效位置")
    probs = _softmax(logits)
    flat = probs.reshape(-1, probs.shape[-1])
    y = targets.reshape(-1)
    w = weights.reshape(-1)
    rows = np.arange(y.size)
    nll = -np.log(flat[rows, y] + 1e-300)
    pred = np.argmax(flat, axis=1)
    mean_ce = float(np.sum(nll * w) / np.sum(w))
    return {
        "mean_ce": mean_ce,
        "ppl": float(np.exp(mean_ce)),
        "token_accuracy": float(np.sum((pred == y) * w) / np.sum(w)),
        "n_tokens": int(np.sum(w)),
    }


def perplexity(model, examples: list, batch_size: int = 4, use_mask: bool = True) -> float:
    arrays = prediction_arrays(model, examples, batch_size=batch_size, use_mask=use_mask)
    return float(np.exp(-np.log(arrays["target_probs"] + 1e-300).mean()))


def answer_perplexity(model, examples: list, batch_size: int = 4) -> float:
    """仅统计样本 mask=1 的答案区域。"""
    return perplexity(model, examples, batch_size=batch_size, use_mask=True)


def token_accuracy(model, examples: list, batch_size: int = 4, use_mask: bool = True) -> float:
    arrays = prediction_arrays(model, examples, batch_size=batch_size, use_mask=use_mask)
    return float(arrays["correct"].mean())


def reliability_bins(confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> list[dict]:
    """按置信度等宽分箱，返回可直接打印的可靠性表。"""
    if n_bins <= 0:
        raise ValueError("n_bins 必须大于 0")
    conf = np.asarray(confidences, dtype=np.float64).reshape(-1)
    corr = np.asarray(correct, dtype=np.float64).reshape(-1)
    if conf.shape != corr.shape or conf.size == 0:
        raise ValueError("confidences/correct 必须同形且非空")
    if np.any((conf < 0) | (conf > 1)):
        raise ValueError("置信度必须位于 [0, 1]")
    indices = np.minimum((conf * n_bins).astype(np.int64), n_bins - 1)
    rows = []
    for index in range(n_bins):
        selected = indices == index
        count = int(selected.sum())
        avg_conf = float(conf[selected].mean()) if count else 0.0
        accuracy = float(corr[selected].mean()) if count else 0.0
        rows.append({
            "bin": index,
            "lower": index / n_bins,
            "upper": (index + 1) / n_bins,
            "count": count,
            "avg_confidence": avg_conf,
            "accuracy": accuracy,
            "gap": abs(avg_conf - accuracy),
        })
    return rows


def expected_calibration_error(
    confidences: np.ndarray,
    correct: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, list[dict]]:
    rows = reliability_bins(confidences, correct, n_bins=n_bins)
    total = sum(row["count"] for row in rows)
    ece = sum(row["count"] / total * row["gap"] for row in rows)
    return float(ece), rows


def calibration(model, examples: list, n_bins: int = 10, batch_size: int = 4, use_mask: bool = True) -> dict:
    arrays = prediction_arrays(model, examples, batch_size=batch_size, use_mask=use_mask)
    ece, bins = expected_calibration_error(arrays["confidences"], arrays["correct"], n_bins)
    return {"ece": ece, "bins": bins, "n_tokens": int(arrays["correct"].size)}


def answer_coverage(examples: Iterable) -> dict:
    answer = 0
    total = 0
    count = 0
    for example in examples:
        _x, y, mask = _parts(example)
        answer += int(np.asarray(mask).sum())
        total += int(np.asarray(y).size)
        count += 1
    return {
        "answer_tokens": answer,
        "total_tokens": total,
        "coverage": answer / total if total else 0.0,
        "n_examples": count,
    }


def evaluate(model, examples: list, batch_size: int = 4, n_bins: int = 10) -> dict:
    arrays = prediction_arrays(model, examples, batch_size=batch_size, use_mask=True)
    mean_ce = float(-np.log(arrays["target_probs"] + 1e-300).mean())
    ece, bins = expected_calibration_error(arrays["confidences"], arrays["correct"], n_bins)
    return {
        "mean_ce": mean_ce,
        "ppl": float(np.exp(mean_ce)),
        "token_accuracy": float(arrays["correct"].mean()),
        "ece": ece,
        "bins": bins,
        "n_tokens": int(arrays["correct"].size),
        **answer_coverage(examples),
    }


__all__ = [
    "answer_coverage", "answer_perplexity", "calibration", "evaluate",
    "expected_calibration_error", "metrics_from_logits", "perplexity",
    "prediction_arrays", "reliability_bins", "token_accuracy",
]
