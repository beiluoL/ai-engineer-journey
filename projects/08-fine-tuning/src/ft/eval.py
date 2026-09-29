"""评估：困惑度、灾难性遗忘、以及「生成一段看看」。

微调到底有没有用，需要两类证据：

1. **定量**：困惑度（perplexity）。
   - 域内（Java 面试）困惑度**下降** → 确实学会了领域知识。
   - 通用语料困惑度**不能暴涨** → 没有灾难性遗忘。
   只报第一条是自欺欺人：把模型训成只会背 59 条答案的复读机，域内指标也会很好看。

2. **定性**：同一道题，微调前后各生成一段。
   本项目是 d_model=64 的玩具模型，生成质量**注定很差**（词表是 BPE 子词、
   只有 2 层、预训练语料才 1KB 量级）。这里如实呈现，不美化 ——
   「小模型定性效果有限，但困惑度指标是真实下降的」本身就是一条重要结论：
   它说明**指标与体感的差距**，也说明为什么真实场景要用 7B 起步的基座。

困惑度的定义：``ppl = exp(平均交叉熵)``。它等价于「模型在每个位置上平均有多
不确定」，越低越好。注意**不同分词器之间的困惑度不可比**（字符级天然比 BPE 低），
本项目只在同一个分词器内部做前后对比。
"""

from __future__ import annotations

import numpy as np

from .paths import ensure_p06_importable

ensure_p06_importable()

from model import generate_ids  # noqa: E402
from model.inference import generate as p06_generate  # noqa: E402

from .sft_data import pad_batch  # noqa: E402

__all__ = [
    "compare",
    "evaluate",
    "forgetting_report",
    "generate_text",
    "perplexity",
]


def evaluate(model, examples: list, batch_size: int = 4) -> dict:
    """在样本集上算平均交叉熵 + 困惑度（只统计 mask=1 的位置）。

    不走 autograd 的 ``cross_entropy``：评估不需要建图，直接 numpy 算 log-softmax
    更快，也避免和训练时的实现互相干扰。
    """
    total_nll = 0.0
    total_tokens = 0.0
    order = np.arange(len(examples))
    for start in range(0, len(order), batch_size):
        chunk = [examples[int(i)] for i in order[start : start + batch_size]]
        X, Y, M = pad_batch(chunk)
        logits = model(X, mask=None).data  # (B, T, V)
        B, T, V = logits.shape
        z = logits.reshape(B * T, V)
        m = z.max(axis=1, keepdims=True)
        e = np.exp(z - m)
        logp = z - m - np.log(e.sum(axis=1, keepdims=True))
        y = Y.reshape(-1)
        w = M.reshape(-1)
        sel = logp[np.arange(z.shape[0]), y]
        total_nll += float(-(sel * w).sum())
        total_tokens += float(w.sum())
    if total_tokens <= 0:
        raise ValueError("没有任何计入 loss 的 token —— 检查 mask")
    mean_ce = total_nll / total_tokens
    return {
        "mean_ce": mean_ce,
        "ppl": float(np.exp(mean_ce)),
        "n_tokens": int(total_tokens),
        "n_examples": len(examples),
    }


def perplexity(model, examples: list, batch_size: int = 4) -> float:
    """困惑度（标量）。"""
    return float(evaluate(model, examples, batch_size)["ppl"])


def compare(before: dict, after: dict) -> dict:
    """两组评估结果的对比（下降百分比 + 判定）。"""
    p0, p1 = before["ppl"], after["ppl"]
    return {
        "ppl_before": p0,
        "ppl_after": p1,
        "drop": p0 - p1,
        "drop_pct": (p0 - p1) / p0 * 100.0,
        "ce_before": before["mean_ce"],
        "ce_after": after["mean_ce"],
        "better": p1 < p0,
    }


def forgetting_report(
    domain: dict,
    general: dict,
    tolerance: float = 0.05,
) -> dict:
    """灾难性遗忘判定。

    ``tolerance`` = 通用困惑度允许的**相对上升幅度**（默认 5%）。
    域内必须变好，通用不能显著变差 —— 两条同时满足才算「学会了且没忘」。
    """
    g0, g1 = general["ppl_before"], general["ppl_after"]
    rise = (g1 - g0) / g0
    if rise <= tolerance:
        verdict = "未观察到灾难性遗忘"
    elif rise <= 3 * tolerance:
        verdict = "轻微遗忘（通用困惑度小幅上升）"
    else:
        verdict = "存在灾难性遗忘（通用困惑度显著上升）"
    return {
        "domain_ppl_before": domain["ppl_before"],
        "domain_ppl_after": domain["ppl_after"],
        "domain_drop_pct": domain["drop_pct"],
        "general_ppl_before": g0,
        "general_ppl_after": g1,
        "general_rise_pct": rise * 100.0,
        "tolerance_pct": tolerance * 100.0,
        "domain_learned": domain["better"],
        "verdict": verdict,
    }


def generate_text(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 60,
    temperature: float = 0.8,
    top_k: "int | None" = None,
    seed: int = 0,
) -> str:
    """用 P06 的采样逻辑生成一段（seed 固定 → 可复现）。"""
    rng = np.random.default_rng(seed)
    ids = generate_ids(
        model, tokenizer, prompt,
        max_new_tokens=max_new_tokens, temperature=temperature, top_k=top_k, rng=rng,
    )
    return tokenizer.decode(ids, skip_special=True)
