"""``ft.eval`` + ``ft.base`` —— 评估指标与基座模型。

评估这条线最容易被"看起来对"骗过去：困惑度算错一个 mask、乘除一个 token 数，
数字依然会下降。所以这里既测「域内是否下降」，也测「指标本身是否自洽」。
"""

from __future__ import annotations

import numpy as np
import pytest

from ft import (
    LoRATrainer,
    build_lm_examples,
    build_sft_examples,
    build_tokenizer,
    compare,
    ensure_base_model,
    evaluate,
    forgetting_report,
    general_corpus,
    inject_lora,
    load_java_records,
    perplexity,
)
from ft.base import BASE_NPZ, TOKENIZER_JSON
from ft.merge import merge_lora


# ---------------------------------------------------------------- evaluate


def test_evaluate_counts_only_masked_tokens(fresh_model, sft_examples):
    res = evaluate(fresh_model, sft_examples[:8])
    expected = sum(int(e.mask.sum()) for e in sft_examples[:8])
    assert res["n_tokens"] == expected


def test_perplexity_is_exp_of_mean_ce(fresh_model, sft_examples):
    res = evaluate(fresh_model, sft_examples[:8])
    assert res["ppl"] == pytest.approx(np.exp(res["mean_ce"]), rel=1e-12)
    assert perplexity(fresh_model, sft_examples[:8]) == pytest.approx(res["ppl"])


def test_evaluate_is_deterministic(fresh_model, sft_examples):
    a = evaluate(fresh_model, sft_examples[:8])
    b = evaluate(fresh_model, sft_examples[:8])
    assert a["mean_ce"] == b["mean_ce"]


def test_perplexity_drops_after_finetuning(fresh_model, sft_examples):
    """域内困惑度必须下降（这是本项目的核心结论）。"""
    before = perplexity(fresh_model, sft_examples)
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 40, batch_size=4)
    after = perplexity(fresh_model, sft_examples)
    assert after < before * 0.7


def test_perplexity_drop_survives_merge(fresh_model, sft_examples):
    """合并之后，困惑度的改善必须原样保留。"""
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 30, batch_size=4)
    split = perplexity(fresh_model, sft_examples)
    merge_lora(fresh_model)
    merged = perplexity(fresh_model, sft_examples)
    assert merged == pytest.approx(split, rel=1e-9)


def test_general_perplexity_is_measurable(fresh_model, tokenizer):
    train_lines, held_lines = general_corpus()
    ex = build_lm_examples("\n".join(train_lines), tokenizer, max_len=256)
    assert len(ex) >= 1
    res = evaluate(fresh_model, ex)
    assert res["ppl"] > 0 and res["n_tokens"] > 0


def test_evaluate_raises_on_empty_mask(fresh_model, sft_examples):
    """mask 全 0 时必须显式报错，而不是悄悄算出 0。"""
    import copy

    zeroed = []
    for e in sft_examples[:2]:
        e2 = copy.copy(e)
        e2.mask = np.zeros_like(e.mask)
        zeroed.append(e2)
    with pytest.raises(ValueError):
        evaluate(fresh_model, zeroed)


# ---------------------------------------------------------------- 对比 / 遗忘判定


def test_compare_reports_improvement():
    cmp = compare({"ppl": 100.0, "mean_ce": 4.6}, {"ppl": 50.0, "mean_ce": 3.9})
    assert cmp["better"] is True
    assert cmp["drop_pct"] == pytest.approx(50.0)


def test_compare_reports_regression():
    cmp = compare({"ppl": 50.0, "mean_ce": 3.9}, {"ppl": 100.0, "mean_ce": 4.6})
    assert cmp["better"] is False
    assert cmp["drop_pct"] == pytest.approx(-100.0)


def test_forgetting_report_no_forgetting():
    rep = forgetting_report(
        {"ppl_before": 1000.0, "ppl_after": 100.0, "drop_pct": 90.0, "better": True},
        {"ppl_before": 10.0, "ppl_after": 10.1}, tolerance=0.05,
    )
    assert "未观察到" in rep["verdict"]
    assert rep["domain_learned"] is True


def test_forgetting_report_detects_forgetting():
    rep = forgetting_report(
        {"ppl_before": 1000.0, "ppl_after": 100.0, "drop_pct": 90.0, "better": True},
        {"ppl_before": 10.0, "ppl_after": 30.0}, tolerance=0.05,
    )
    assert "灾难性遗忘" in rep["verdict"]
    assert rep["general_rise_pct"] == pytest.approx(200.0)


def test_forgetting_report_mild_case():
    rep = forgetting_report(
        {"ppl_before": 1000.0, "ppl_after": 100.0, "drop_pct": 90.0, "better": True},
        {"ppl_before": 10.0, "ppl_after": 10.8}, tolerance=0.05,
    )
    assert "轻微" in rep["verdict"]


# ---------------------------------------------------------------- base


def test_tokenizer_is_cached():
    tok = build_tokenizer()
    assert TOKENIZER_JSON.is_file()
    assert tok.vocab_size > 600
    assert tok.vocab_size == build_tokenizer().vocab_size


def test_tokenizer_covers_prompt_template(tokenizer):
    """模板里的 '#' 必须在词表内（否则整个 prompt 开头都是 <unk>）。"""
    unk = tokenizer.token_to_id["<unk>"]
    ids = tokenizer.encode("### 指令:\n问题\n\n### 回答:\n")
    assert unk not in ids


def test_java_data_has_no_unk_in_answers(tokenizer, records):
    """领域数据的答案几乎不该出现 <unk>。"""
    unk = tokenizer.token_to_id["<unk>"]
    total = 0
    n_unk = 0
    for r in records:
        ids = tokenizer.encode(r["output"])
        total += len(ids)
        n_unk += sum(1 for i in ids if i == unk)
    assert n_unk / total < 0.01


def test_base_model_is_cached():
    _model, tok, info = ensure_base_model()
    assert BASE_NPZ.is_file()
    assert info["source"] == "cache"
    assert info["vocab_size"] == tok.vocab_size


def test_base_model_config(fresh_model):
    assert fresh_model.d_model == 64
    assert fresh_model.n_heads == 4
    assert fresh_model.n_layers == 2
    assert fresh_model.max_len == 256


def test_base_model_is_deterministic():
    m1, _, _ = ensure_base_model()
    m2, _, _ = ensure_base_model()
    from ft import named_parameters

    p1 = {p: v.data for p, v in named_parameters(m1)}
    p2 = {p: v.data for p, v in named_parameters(m2)}
    assert set(p1) == set(p2)
    for k in p1:
        assert np.array_equal(p1[k], p2[k])


def test_general_corpus_split():
    train_lines, held_lines = general_corpus()
    assert len(train_lines) > 10
    assert len(held_lines) == 4
    assert not (set(train_lines) & set(held_lines))


def test_generate_text_runs(fresh_model, tokenizer):
    from ft import generate_text

    text = generate_text(fresh_model, tokenizer, "### 指令:\n测试\n\n### 回答:\n",
                         max_new_tokens=8, temperature=0.8, seed=0)
    assert isinstance(text, str)
    assert len(text) > 0


def test_generate_text_is_deterministic(fresh_model, tokenizer):
    from ft import generate_text

    prompt = "### 指令:\n测试\n\n### 回答:\n"
    a = generate_text(fresh_model, tokenizer, prompt, max_new_tokens=8, seed=3)
    b = generate_text(fresh_model, tokenizer, prompt, max_new_tokens=8, seed=3)
    assert a == b


def test_real_end_to_end_domain_gain(fresh_model, sft_examples, tokenizer):
    """端到端：注入 → 训练 → 合并，域内困惑度必须显著下降。"""
    before = perplexity(fresh_model, sft_examples)
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    losses = trainer.run(sft_examples, 40, batch_size=4)
    after = perplexity(fresh_model, sft_examples)
    merge_lora(fresh_model)
    merged = perplexity(fresh_model, sft_examples)

    assert losses[-1] < losses[0] - 1.0
    assert after < before * 0.7
    assert merged == pytest.approx(after, rel=1e-9)
