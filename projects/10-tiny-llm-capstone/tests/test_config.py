"""配置契约（M01）：校验、序列化、词表解析。"""

from __future__ import annotations

import pytest

from tiny.config import (
    TinyConfig,
    default_config,
    resolve_vocab_size,
)


def test_default_config_passes_validation():
    cfg = default_config()
    assert cfg.model.d_model % cfg.model.n_heads == 0
    assert cfg.train.n_steps > 0


def test_d_model_not_divisible_by_heads_is_rejected():
    cfg = TinyConfig()
    cfg.model.n_heads = 3  # 64 不能被 3 整除
    with pytest.raises(ValueError, match="n_heads"):
        cfg.validate()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: setattr(c.train, "batch_size", 0),
        lambda c: setattr(c.optim, "lr", 0.0),
        lambda c: setattr(c.data, "val_ratio", 0.9),
        lambda c: setattr(c.gen, "top_p", 1.5),
        lambda c: setattr(c.tokenizer, "kind", "wordpiece"),
    ],
)
def test_invalid_values_are_rejected(mutate):
    cfg = TinyConfig()
    mutate(cfg)
    with pytest.raises(ValueError, match="TinyConfig 校验未通过"):
        cfg.validate()


def test_json_roundtrip_keeps_every_field(workdir):
    cfg = default_config()
    path = workdir / "config.json"
    cfg.save(path)
    restored = TinyConfig.load(path)
    assert restored.to_dict() == cfg.to_dict()


def test_unknown_field_is_rejected_instead_of_silently_ignored(workdir):
    cfg = default_config()
    path = workdir / "bad.json"
    path.write_text('{"name": "x", "learning_rate": 0.1}', encoding="utf-8")
    with pytest.raises(ValueError, match="未知配置项"):
        TinyConfig.load(path)


def test_unknown_section_field_is_rejected(workdir):
    path = workdir / "bad2.json"
    path.write_text('{"model": {"d_model": 64, "depth": 3}}', encoding="utf-8")
    with pytest.raises(ValueError, match="model 段出现未知配置项"):
        TinyConfig.load(path)


def test_resolve_vocab_size_follows_tokenizer():
    cfg = TinyConfig()
    assert cfg.model.vocab_size == 0

    class Fake:
        vocab_size = 777

    resolve_vocab_size(cfg, Fake())
    assert cfg.model.vocab_size == 777


def test_resolve_vocab_size_rejects_mismatch():
    cfg = TinyConfig()
    cfg.model.vocab_size = 100

    class Fake:
        vocab_size = 777

    with pytest.raises(ValueError, match="不一致"):
        resolve_vocab_size(cfg, Fake())


def test_summary_lines_cover_every_section():
    lines = "\n".join(default_config().summary_lines())
    for section in ("tokenizer", "model", "data", "optim", "train", "gen", "serve"):
        assert section in lines
