"""``ft.merge`` —— 合并回基座的等价性与代价。

合并之所以成立，完全因为 LoRA 分支是线性的：
``x@W + (alpha/r)·x@A@B == x@(W + (alpha/r)·A@B)``。
这个等式必须被数值证明（而不是相信），否则合并就是个定时炸弹。
"""

from __future__ import annotations

import numpy as np
import pytest

from ft import (
    count_parameters,
    ensure_base_model,
    inject_lora,
    lora_layers,
    lora_overhead_report,
    max_abs_diff,
    merge_lora,
    unmerge_lora,
)
from ft.merge import time_forward


def test_merge_output_is_identical_to_split(fresh_model):
    """合并前后在同一输入上的输出必须一致（误差 < 1e-10）。"""
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    ids = np.random.randint(4, 1000, (4, 32))
    before = fresh_model(ids, mask=None).data.copy()
    merge_lora(fresh_model)
    after = fresh_model(ids, mask=None).data
    assert max_abs_diff(before, after) < 1e-10


def test_merge_error_is_near_machine_epsilon(fresh_model, sft_examples):
    """训过之后（ΔW 非零）再合并，等价性依然要成立。"""
    from ft import LoRATrainer

    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 10, batch_size=4)
    ids = np.random.randint(4, 1000, (2, 48))
    before = fresh_model(ids, mask=None).data.copy()
    merge_lora(fresh_model)
    after = fresh_model(ids, mask=None).data
    assert max_abs_diff(before, after) < 1e-10


def test_merge_removes_lora_layers(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    assert len(lora_layers(fresh_model)) == 13
    merge_lora(fresh_model)
    assert len(lora_layers(fresh_model)) == 0


def test_merge_reduces_parameter_count(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    before = count_parameters(fresh_model)
    merge_lora(fresh_model)
    after = count_parameters(fresh_model)
    assert after["total"] == before["base"]
    assert after["trainable"] == 0


def test_merge_without_lora_raises(fresh_model):
    with pytest.raises(RuntimeError):
        merge_lora(fresh_model)


def test_unmerge_restores_split_structure(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    backup = merge_lora(fresh_model)
    unmerge_lora(fresh_model, backup)
    assert len(lora_layers(fresh_model)) == 13
    for entry, (_p, layer) in zip(backup["layers"], lora_layers(fresh_model)):
        assert np.array_equal(layer.A.data, entry["A"])
        assert np.array_equal(layer.B.data, entry["B"])


def test_unmerge_restores_original_output(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    ids = np.random.randint(4, 1000, (2, 32))
    before = fresh_model(ids, mask=None).data.copy()
    backup = merge_lora(fresh_model)
    unmerge_lora(fresh_model, backup)
    assert max_abs_diff(before, fresh_model(ids, mask=None).data) < 1e-10


def test_merge_weight_equals_w_plus_delta(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    layers = dict(lora_layers(fresh_model))
    expected = {p: l.merged_weight().copy() for p, l in layers.items()}
    merge_lora(fresh_model)
    from ft import named_parameters

    for p, param in named_parameters(fresh_model):
        if p in expected:
            assert np.allclose(param.data, expected[p], atol=1e-15)


def test_overhead_report(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    rep = lora_overhead_report(fresh_model, batch_size=4, seq_len=64)
    assert rep["n_lora_layers"] == 13
    assert 0 < rep["overhead_ratio"] < 0.5
    assert rep["lora_macs_per_batch"] == rep["lora_macs_per_token"] * 4 * 64


def test_overhead_grows_with_rank(fresh_model):
    inject_lora(fresh_model, r=4, alpha=8.0, rng=0)
    r4 = lora_overhead_report(fresh_model)["overhead_ratio"]
    m2, _, _ = ensure_base_model()
    inject_lora(m2, r=16, alpha=32.0, rng=0)
    r16 = lora_overhead_report(m2)["overhead_ratio"]
    assert r16 > r4


def test_time_forward_runs(fresh_model):
    x = np.random.randint(4, 1000, (2, 16))
    out = time_forward(fresh_model, x, n_repeat=3, warmup=1)
    assert out["n_repeat"] == 3
    assert out["total_sec"] > 0
    assert out["per_forward_ms"] > 0


def test_max_abs_diff():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.5, 3.0])
    assert max_abs_diff(a, b) == pytest.approx(0.5)


def test_merge_then_forward_has_no_lora_branch(fresh_model):
    """合并后前向里不应再出现任何 LoRA 张量。"""
    from ft.inject import walk_parameters

    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    merge_lora(fresh_model)
    paths = [p for p, _parent, _key, _param in walk_parameters(fresh_model)]
    assert not any(p.endswith(".A") or p.endswith(".B") for p in paths)
