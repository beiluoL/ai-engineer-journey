"""模型装配与结构自检（M04 / M05）：参数账、因果性、确定性。"""

from __future__ import annotations

import numpy as np
import pytest

from tiny.model import (
    build_model,
    build_optimizer,
    forward_sanity,
    parameter_report,
    walk_parameters,
)


def test_build_model_follows_config(cfg, char_tokenizer):
    model = build_model(cfg, char_tokenizer)
    assert model.vocab_size == char_tokenizer.vocab_size
    assert model.d_model == cfg.model.d_model
    assert model.n_layers == cfg.model.n_layers
    assert model.max_len == cfg.model.max_len


def test_parameter_accounting_adds_up(cfg, char_tokenizer):
    model = build_model(cfg, char_tokenizer)
    report = parameter_report(model)
    assert sum(report["groups"].values()) == report["total"]
    assert report["n_tensors"] == len(walk_parameters(model))
    # 小模型里 embedding + 输出投影就是大头（这是 Tiny LLM 的关键事实）
    emb = report["groups"]["token_embedding"]
    proj = report["groups"].get("output_projection", 0)
    assert (emb + proj) / report["total"] > 0.5


def test_walk_parameters_names_are_hierarchical(cfg, char_tokenizer):
    model = build_model(cfg, char_tokenizer)
    names = [name for name, _p in walk_parameters(model)]
    assert "token_emb.weight" in names
    assert any(name.startswith("decoder.blocks.0.attn.") for name in names)


def test_forward_is_causal_deterministic_and_finite(cfg, char_tokenizer):
    """三个不变量：形状对、改未来不动过去、同样输入同样输出。"""
    model = build_model(cfg, char_tokenizer)
    result = forward_sanity(model, seq_len=8, batch=2, seed=0)
    assert result["passed"], result
    assert result["causal_past_max_error"] == 0.0
    assert result["causal_future_max_error"] > 0.0
    assert result["determinism_max_error"] == 0.0
    assert result["finite"]


def test_forward_rejects_over_long_sequence(cfg, char_tokenizer):
    model = build_model(cfg, char_tokenizer)
    with pytest.raises(ValueError, match="超过"):
        model(np.zeros((1, cfg.model.max_len + 1), dtype=np.int64), mask=None)


def test_build_optimizer_supports_adam_and_sgd(cfg, char_tokenizer):
    model = build_model(cfg, char_tokenizer)
    adam = build_optimizer(cfg, model)
    assert adam.__class__.__name__ == "Adam"
    cfg.optim.optimizer = "sgd"
    assert build_optimizer(cfg, model).__class__.__name__ == "SGD"
    cfg.optim.optimizer = "rmsprop"
    with pytest.raises(ValueError, match="未知优化器"):
        build_optimizer(cfg, model)


def test_same_seed_gives_identical_initial_weights(cfg, char_tokenizer):
    a = build_model(cfg, char_tokenizer, seed=123)
    b = build_model(cfg, char_tokenizer, seed=123)
    for (_, pa), (_, pb) in zip(walk_parameters(a), walk_parameters(b)):
        assert np.array_equal(pa.data, pb.data)
