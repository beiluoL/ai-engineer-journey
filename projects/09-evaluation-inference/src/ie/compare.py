"""多种子模型评估与配对比较。"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def summarize(values: list[float]) -> dict:
    if not values:
        raise ValueError("values 不能为空")
    arr = np.asarray(values, dtype=np.float64)
    return {
        "values": arr.tolist(),
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def paired_compare(
    baseline: list[float],
    challenger: list[float],
    *,
    lower_is_better: bool = False,
    atol: float = 1e-12,
) -> dict:
    """同 seed 配对；improvement > 0 始终表示 challenger 更好。"""
    a = np.asarray(baseline, dtype=np.float64)
    b = np.asarray(challenger, dtype=np.float64)
    if a.shape != b.shape or a.size == 0:
        raise ValueError("两组配对结果必须同形且非空")
    raw_delta = b - a
    improvement = -raw_delta if lower_is_better else raw_delta
    signs = np.where(improvement > atol, 1, np.where(improvement < -atol, -1, 0))
    non_ties = signs[signs != 0]
    consistency = float(max(np.mean(non_ties > 0), np.mean(non_ties < 0))) if non_ties.size else 1.0
    stable = bool(non_ties.size > 0 and np.all(non_ties == non_ties[0]) and not np.any(signs == 0))
    return {
        "raw_differences": raw_delta.tolist(),
        "improvements": improvement.tolist(),
        "mean_difference": float(raw_delta.mean()),
        "mean_improvement": float(improvement.mean()),
        "std_difference": float(raw_delta.std(ddof=1)) if raw_delta.size > 1 else 0.0,
        "wins": int(np.sum(signs > 0)),
        "losses": int(np.sum(signs < 0)),
        "ties": int(np.sum(signs == 0)),
        "sign_consistency": consistency,
        "stable": stable,
        "noise_flip": bool(np.any(signs > 0) and np.any(signs < 0)),
    }


def evaluate_models(
    models: dict[str, object],
    seeds: list[int],
    evaluator: Callable[[object, int], float],
    *,
    baseline: "str | None" = None,
    lower_is_better: bool = False,
) -> dict:
    if not models or not seeds:
        raise ValueError("models 与 seeds 不能为空")
    values = {
        name: [float(evaluator(model, int(seed))) for seed in seeds]
        for name, model in models.items()
    }
    summary = {name: summarize(scores) for name, scores in values.items()}
    base_name = baseline or next(iter(models))
    if base_name not in values:
        raise KeyError(f"基线模型不存在：{base_name}")
    paired = {
        name: paired_compare(values[base_name], scores, lower_is_better=lower_is_better)
        for name, scores in values.items() if name != base_name
    }
    ordered = sorted(
        summary,
        key=lambda name: summary[name]["mean"],
        reverse=not lower_is_better,
    )
    return {
        "seeds": list(seeds), "baseline": base_name, "values": values,
        "summary": summary, "paired": paired, "ranking": ordered,
        "lower_is_better": lower_is_better,
    }


__all__ = ["evaluate_models", "paired_compare", "summarize"]
