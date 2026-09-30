"""评估三层（M07）：语言层、校准层、生成层 + 配对比较。"""

from __future__ import annotations

import numpy as np

from tiny.evaluate import (
    compare_models,
    diversity_report,
    evaluate_model,
    generation_report,
    per_example_losses,
    qa_pairs_from_lines,
)
from tiny.infer import Generator
from tiny.model import build_model


def test_evaluate_model_returns_three_layers(trained_bundle):
    cfg = trained_bundle["cfg"]
    model = trained_bundle["model"]
    dataset = trained_bundle["dataset"]
    generator = Generator(model, trained_bundle["tokenizer"], cfg)
    report = evaluate_model(
        cfg,
        model,
        dataset.val_examples,
        dataset.val_lines,
        generate_fn=lambda p: generator.generate(p, max_new_tokens=10, temperature=0.0),
    )
    assert report["perplexity"] > 0
    assert 0.0 <= report["ece"] <= 1.0
    assert 0.0 <= report["token_accuracy"] <= 1.0
    assert "generation" in report and "diversity" in report


def test_qa_pairs_are_parsed_from_corpus_lines():
    pairs = qa_pairs_from_lines(
        ["问：什么是 LoRA？答：低秩适配。", "分词器把文本切成 token。", "问：为什么？答：因为。"]
    )
    assert pairs == [("什么是 LoRA？", "低秩适配。"), ("为什么？", "因为。")]


def test_diversity_detects_repetition():
    repeated = diversity_report(["是 token token token token"])
    varied = diversity_report(["分词器把文本切成 token 再映射成整数"])
    assert repeated["repetition_rate"] > varied["repetition_rate"]
    assert repeated["distinct_1"] < varied["distinct_1"]


def test_generation_report_scores_samples():
    def fake_generate(prompt: str) -> str:
        return "低秩适配用两个小矩阵的乘积表示权重增量"

    report = generation_report(fake_generate, [("什么是 LoRA？", "低秩适配是一种参数高效微调方法")])
    assert report["n"] == 1
    # P09 的 AutoEvalScore.total 是百分制（0~100），不是 0~1 —— 别想当然
    assert 0.0 <= report["aggregate"]["total"] <= 100.0
    assert report["samples"][0]["prompt"].startswith("问：")


def test_per_example_losses_matches_count(trained_bundle):
    cfg = trained_bundle["cfg"]
    model = trained_bundle["model"]
    examples = trained_bundle["dataset"].val_examples[:3]
    losses = per_example_losses(model, examples, cfg.train.batch_size)
    assert len(losses) == 3
    assert all(np.isfinite(value) and value > 0 for value in losses)


def test_compare_models_is_pairwise(trained_bundle):
    """配对比较：样本数相同、胜负场之和 + 平局 = 样本数。"""
    cfg = trained_bundle["cfg"]
    model = trained_bundle["model"]
    baseline = build_model(cfg, trained_bundle["tokenizer"])  # 未训练的随机模型
    examples = trained_bundle["dataset"].val_examples[:4]
    result = compare_models(baseline, model, examples, cfg.train.batch_size)
    assert result["n_examples"] == 4
    assert result["wins"] + result["losses"] + result["ties"] == 4
    assert result["challenger_mean"] < result["baseline_mean"]  # 训过的应该更好
