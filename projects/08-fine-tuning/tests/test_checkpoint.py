"""``ft.checkpoint`` —— adapter 存 / 取 / 续训。

最关键的一条：**续训之后 loss 曲线要接得上**。
只存 A/B、不存训练状态，那叫"重新训练"，不叫断点续训。
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from ft import (
    LoRATrainer,
    adapter_report,
    count_parameters,
    inject_lora,
    load_adapter,
    load_checkpoint,
    save_adapter,
    save_checkpoint,
    trainable_parameters,
)


def test_save_creates_npz_and_json(fresh_model, workdir):
    path = workdir / "a.npz"
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    save_adapter(fresh_model, path, trainer=None, include_optimizer=False)
    assert path.is_file()
    assert path.with_suffix(".json").is_file()


def test_roundtrip_is_bitwise_exact_with_float64(fresh_model, sft_examples, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 6, batch_size=4)
    before = [p.data.copy() for p in trainable_parameters(fresh_model)]

    path = workdir / "a.npz"
    save_checkpoint(fresh_model, trainer, path, dtype=np.float64)

    m2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m2, r=8, alpha=16.0, rng=0)
    t2 = LoRATrainer(m2, lr=3e-3, seed=0)
    load_checkpoint(m2, t2, path)

    after = [p.data for p in trainable_parameters(m2)]
    for a, b in zip(before, after):
        assert np.array_equal(a, b)
    assert t2.step == trainer.step
    assert t2.optimizer.t == trainer.optimizer.t


def test_roundtrip_with_float32_is_within_precision(fresh_model, sft_examples, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 6, batch_size=4)
    before = [p.data.copy() for p in trainable_parameters(fresh_model)]

    path = workdir / "b.npz"
    info = save_checkpoint(fresh_model, trainer, path)  # 默认 fp32
    assert info["save_dtype"] == "float32"

    m2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m2, r=8, alpha=16.0, rng=0)
    t2 = LoRATrainer(m2, lr=3e-3, seed=0)
    load_checkpoint(m2, t2, path)

    for a, b in zip(before, [p.data for p in trainable_parameters(m2)]):
        assert np.max(np.abs(a - b)) < 1e-6


def test_resume_keeps_loss_curve_continuous(fresh_model, sft_examples, workdir):
    """断点续训的曲线必须与「一次性训完」几乎重合。"""
    path = workdir / "c.npz"
    # A：一次性 40 步
    m_a, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m_a, r=8, alpha=16.0, rng=0)
    t_a = LoRATrainer(m_a, lr=3e-3, seed=0)
    straight = t_a.run(sft_examples, 40, batch_size=4)

    # B：20 步 → 存盘 → 重载 → 再 20 步
    m_b, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m_b, r=8, alpha=16.0, rng=0)
    t_b = LoRATrainer(m_b, lr=3e-3, seed=0)
    first = t_b.run(sft_examples, 20, batch_size=4)
    save_checkpoint(m_b, t_b, path, dtype=np.float64)
    m_b2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m_b2, r=8, alpha=16.0, rng=0)
    t_b2 = LoRATrainer(m_b2, lr=3e-3, seed=0)
    load_checkpoint(m_b2, t_b2, path)
    second = t_b2.run(sft_examples, 20, batch_size=4)

    assert np.allclose(first, straight[:20], atol=1e-10)
    assert np.allclose(second, straight[20:], atol=1e-6)
    # 终点不能比「一次性训 40 步」明显更差
    assert second[-1] <= straight[-1] + 1e-4


def test_resume_does_not_rebound(fresh_model, sft_examples, workdir):
    """断点之后第一步的 loss 不能明显反弹。"""
    path = workdir / "d.npz"
    m, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m, r=8, alpha=16.0, rng=0)
    t = LoRATrainer(m, lr=3e-3, seed=0)
    first = t.run(sft_examples, 20, batch_size=4)
    save_checkpoint(m, t, path, dtype=np.float64)

    m2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m2, r=8, alpha=16.0, rng=0)
    t2 = LoRATrainer(m2, lr=3e-3, seed=0)
    load_checkpoint(m2, t2, path)
    second = t2.run(sft_examples, 10, batch_size=4)
    assert second[0] < first[-1] + 1.0  # 不出现数量级级别的反弹


def test_false_resume_without_state_is_different(fresh_model, sft_examples, workdir):
    """只加载权重、不恢复训练状态 → 曲线会明显偏离（假续训）。"""
    path = workdir / "e.npz"
    m_a, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m_a, r=8, alpha=16.0, rng=0)
    t_a = LoRATrainer(m_a, lr=3e-3, seed=0)
    straight = t_a.run(sft_examples, 40, batch_size=4)

    m_b, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m_b, r=8, alpha=16.0, rng=0)
    t_b = LoRATrainer(m_b, lr=3e-3, seed=0)
    t_b.run(sft_examples, 20, batch_size=4)
    save_checkpoint(m_b, t_b, path, dtype=np.float64)

    m_c, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m_c, r=8, alpha=16.0, rng=0)
    _meta = load_adapter(m_c, path)  # 只加载 A/B
    t_c = LoRATrainer(m_c, lr=3e-3, seed=0)
    second = t_c.run(sft_examples, 20, batch_size=4)
    assert t_c.step == 20  # 只跑了 20 步（state 没恢复，计数从 0 开始）
    assert not np.allclose(second, straight[20:], atol=1e-3)


def test_adapter_file_is_smaller_than_base(fresh_model, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    path = workdir / "f.npz"
    save_adapter(fresh_model, path, trainer=None, include_optimizer=False)
    rep = adapter_report(path, fresh_model)
    assert rep["total_bytes"] < rep["base_fp32_bytes"]
    assert rep["ratio_of_base"] < 0.2


def test_optimizer_state_adds_size(fresh_model, sft_examples, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 4, batch_size=4)
    p1 = workdir / "w.npz"
    p2 = workdir / "full.npz"
    save_adapter(fresh_model, p1, trainer=None, include_optimizer=False)
    save_checkpoint(fresh_model, trainer, p2)
    assert p2.stat().st_size > p1.stat().st_size


def test_meta_json_has_expected_fields(fresh_model, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    path = workdir / "g.npz"
    save_adapter(fresh_model, path, trainer=None, include_optimizer=False)
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["format"] == "p08-lora-adapter-v1"
    assert meta["n_layers"] == 13
    assert len(meta["layers"]) == 13
    assert meta["layers"][0]["r"] == 8
    assert meta["n_adapter_params"] == count_parameters(fresh_model)["trainable"]


def test_load_into_mismatched_model_raises(fresh_model, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    path = workdir / "h.npz"
    save_adapter(fresh_model, path, trainer=None, include_optimizer=False)

    m2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m2, targets=("Wq",), r=8, alpha=16.0, rng=0)  # 只有 2 层
    with pytest.raises(ValueError):
        load_adapter(m2, path)


def test_load_missing_file_raises(fresh_model, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    with pytest.raises(FileNotFoundError):
        load_adapter(fresh_model, workdir / "nope.npz")


def test_losses_are_recorded_in_meta(fresh_model, sft_examples, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    losses = trainer.run(sft_examples, 5, batch_size=4)
    path = workdir / "i.npz"
    save_checkpoint(fresh_model, trainer, path)
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(meta["losses"]) == 5
    assert meta["losses"][-1] == pytest.approx(losses[-1])


def test_adapter_report_without_model(fresh_model, workdir):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    path = workdir / "j.npz"
    save_adapter(fresh_model, path, trainer=None, include_optimizer=False)
    rep = adapter_report(path)
    assert rep["base_fp32_bytes"] is None
    assert rep["total_bytes"] > 0
