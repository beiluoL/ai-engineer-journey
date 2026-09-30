"""Milestone 07 —— 评估：证明「训完了」不等于「训好了」。

困惑度一路下降是最容易自欺的指标 —— 它只说明模型更**确定**，不说明它更**对**。
所以本章把评估拆成三层，缺一层结论就不成立：

1. **语言层**（能不能预测）：验证集交叉熵 / 困惑度 / token 准确率。
2. **校准层**（确定得有没有道理）：用 P09 的 ``calibration`` 算 ECE。
   一个 ECE 很高的模型会「很自信地说错话」，上线就是灾难。
3. **生成层**（说出来的话能不能用）：把验证集里的「问：…答：」当成 held-out 题目，
   让模型续写答案，用 P09 的 ``evaluate_answer`` 打关键词覆盖 / 重复 / 忠实度分。

第三层是本项目最能暴露问题的一层：一个 20 万参数的 Tiny LLM 完全可能
困惑度很好看、但生成出来全是复读。所以 M07 额外算了 distinct-1/2 和重复率。

另外 :func:`compare_models` 做**配对比较**（同一个样本、同一个 seed、逐条对拍），
而不是比两个平均值 —— n=1 的「提升 3%」没有意义，配对后能看出
这个提升是**稳定**的还是被个别样本带偏的。
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from .config import TinyConfig
from .train import evaluate_loss

from ie.autoeval import aggregate_scores, evaluate_answer  # noqa: E402
from ie.compare import paired_compare  # noqa: E402
from ie.metrics import calibration  # noqa: E402

__all__ = [
    "compare_models",
    "diversity_report",
    "evaluate_model",
    "generation_report",
    "qa_pairs_from_lines",
    "per_example_losses",
]


def per_example_losses(model, examples, batch_size: int = 4) -> list[float]:
    """逐条样本的交叉熵 —— 配对比较的原料。

    为什么要逐条：两个模型的平均 loss 差 0.02，可能是每条都差 0.02，
    也可能是 3 条样本差了 0.5 而其余全平。这两种「提升」完全不是一回事。
    """
    from .data import pad_batch

    from model import cross_entropy  # noqa: PLC0415

    losses: list[float] = []
    for example in examples:
        x, y, mask = pad_batch([example])
        logits = model(x, mask=None)
        loss = cross_entropy(logits, y, mask=mask)
        losses.append(float(loss.data))
    return losses


def compare_models(baseline_model, challenger_model, examples, batch_size: int = 4) -> dict:
    """配对比较两个模型：返回逐条差值、胜负场与**一致性**。"""
    base = per_example_losses(baseline_model, examples, batch_size)
    chal = per_example_losses(challenger_model, examples, batch_size)
    paired = paired_compare(base, chal, lower_is_better=True)
    paired.update(
        {
            "baseline_mean": float(np.mean(base)),
            "challenger_mean": float(np.mean(chal)),
            "n_examples": len(base),
        }
    )
    return paired


def qa_pairs_from_lines(lines: list[str]) -> list[tuple[str, str]]:
    """从「问：…答：…」语料行里抽出 (题目, 参考答案)。

    这是本项目**最真实**的一份评测集：它来自语料、经过 train/val 切分，
    所以拿验证集里的题目去问模型，模型确实没见过答案。
    """
    pairs: list[tuple[str, str]] = []
    for line in lines:
        if "问：" not in line or "答：" not in line:
            continue
        question = line.split("问：", 1)[1].split("答：", 1)[0].strip()
        answer = line.split("答：", 1)[1].strip()
        if question and answer:
            pairs.append((question, answer))
    return pairs


def diversity_report(texts: list[str]) -> dict:
    """生成多样性：distinct-1 / distinct-2 / 3-gram 重复率。

    distinct-1 = 不同字 / 总字数。模型一旦开始复读，这个数会**断崖式**下跌，
    比人眼看几条样例可靠得多。
    """
    if not texts:
        return {"distinct_1": 0.0, "distinct_2": 0.0, "repetition_rate": 0.0, "chars": 0}
    joined = "".join(texts)
    unigrams = list(joined)
    bigrams = [joined[i : i + 2] for i in range(max(0, len(joined) - 1))]
    trigrams = [joined[i : i + 3] for i in range(max(0, len(joined) - 2))]
    counts = Counter(trigrams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return {
        "distinct_1": len(set(unigrams)) / max(len(unigrams), 1),
        "distinct_2": len(set(bigrams)) / max(len(bigrams), 1),
        "repetition_rate": repeated / max(len(trigrams), 1),
        "chars": len(joined),
    }


def generation_report(generate_fn, pairs: list[tuple[str, str]], limit: int = 6) -> dict:
    """用 held-out 的「问/答」对，评一次生成质量。

    ``generate_fn(prompt) -> str``，由调用方注入（M08 的推理器），
    这样评估层不依赖具体的采样实现。
    """
    if not pairs:
        return {"n": 0, "aggregate": {}, "samples": []}
    samples: list[dict] = []
    for question, reference in pairs[:limit]:
        prompt = f"问：{question}答："
        answer = generate_fn(prompt)
        score = evaluate_answer(answer, reference)
        samples.append(
            {
                "prompt": prompt,
                "reference": reference,
                "generated": answer,
                "score": score.to_dict(),
            }
        )
    aggregate = aggregate_scores([evaluate_answer(s["generated"], s["reference"]) for s in samples])
    return {"n": len(samples), "aggregate": aggregate, "samples": samples}


def evaluate_model(
    cfg: TinyConfig,
    model,
    val_examples,
    val_lines: "list[str] | None" = None,
    generate_fn=None,
    n_bins: int = 10,
) -> dict:
    """三层评估一次跑完，返回可直接打印的报告字典。"""
    lang = evaluate_loss(model, val_examples, cfg.train.batch_size)
    cal = calibration(model, val_examples, n_bins=n_bins, batch_size=cfg.train.batch_size,
                      use_mask=True)
    report = {
        "loss": lang["loss"],
        "perplexity": lang["perplexity"],
        "token_accuracy": lang["token_accuracy"],
        "ece": cal["ece"],
        "calibration_bins": cal["bins"],
        "n_tokens": cal["n_tokens"],
        "n_examples": len(val_examples),
    }
    if val_lines and generate_fn is not None:
        pairs = qa_pairs_from_lines(val_lines)
        gen = generation_report(generate_fn, pairs)
        texts = [s["generated"] for s in gen.get("samples", [])]
        report["generation"] = gen
        report["diversity"] = diversity_report(texts)
    return report
