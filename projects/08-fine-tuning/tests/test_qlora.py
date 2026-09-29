"""``ft.qlora`` —— NF4 基座 + fp32 adapter，以及那张显存账本。"""

from __future__ import annotations

import numpy as np
import pytest

from ft import QLoRALinear, human_bytes, memory_ledger, training_memory
from ft import dequantize_nf4, quantization_error
from model import Tensor, cross_entropy, grad_check

SHAPES = [(64, 64)] * 8 + [(64, 256), (256, 64)] * 2 + [(64, 1024)]


def test_qlora_shapes():
    q = QLoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert q.A.data.shape == (64, 8)
    assert q.B.data.shape == (8, 256)
    assert q.base_shape == (64, 256)


def test_qlora_b_zero_equals_dequantized_base():
    """B=0 时 QLoRA 输出 == 用 NF4 反量化权重算出来的输出。"""
    q = QLoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    x = Tensor(np.random.randn(4, 64))
    assert np.array_equal(q(x).data, x.data @ q.dequantized_base())


def test_qlora_base_is_actually_quantized():
    """基座必须真的被压成 4bit —— 反量化回去要有误差，不能等于原权重。"""
    w = np.random.default_rng(0).normal(0, 0.02, (64, 256))
    q = QLoRALinear(64, 256, r=8, alpha=16.0, weight=w, rng=0)
    err = quantization_error(w, q.dequantized_base())
    assert err["rel_l2"] > 0.01


def test_qlora_delta_weight_zero_at_init():
    q = QLoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert np.all(q.delta_weight() == 0.0)


def test_qlora_grad_check():
    q = QLoRALinear(16, 24, r=4, alpha=8.0, rng=0)
    q.B.data[:] = np.random.default_rng(1).normal(0, 0.05, size=q.B.data.shape)
    x = Tensor(np.random.randn(5, 16))
    t = np.random.randint(0, 24, 5)

    def f(a, b):
        q.A, q.B = a, b
        return cross_entropy(q(x), t)

    err = grad_check(f, [q.A, q.B], eps=1e-6)
    assert err < 1e-4


def test_qlora_merged_weight_formula():
    q = QLoRALinear(32, 48, r=4, alpha=8.0, rng=0)
    q.B.data[:] = np.random.default_rng(2).normal(0, 0.1, size=q.B.data.shape)
    expected = q.dequantized_base() + (8.0 / 4) * (q.A.data @ q.B.data)
    assert np.allclose(q.merged_weight(), expected, atol=1e-15)


def test_qlora_trainable_is_only_adapter():
    q = QLoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    params = q.trainable_parameters()
    assert len(params) == 2
    assert params[0] is q.A and params[1] is q.B


def test_qlora_num_parameters():
    q = QLoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert q.num_parameters(trainable_only=True) == 64 * 8 + 8 * 256


def test_double_quant_flag_is_respected():
    q1 = QLoRALinear(64, 256, r=8, alpha=16.0, double_quant=True, rng=0)
    q2 = QLoRALinear(64, 256, r=8, alpha=16.0, double_quant=False, rng=0)
    assert q1.double_quant and not q2.double_quant
    assert q1.qw.absmax_codes is not None and q2.qw.absmax_codes is None


# ---------------------------------------------------------------- 显存账本


def test_memory_ledger_nf4_is_one_eighth_of_fp32():
    led = memory_ledger(SHAPES, r=8)
    assert 6.5 < led["compress_fp32_vs_nf4"] <= 8.0


def test_memory_ledger_nf4_not_larger_than_fp16():
    led = memory_ledger(SHAPES, r=8)
    assert led["nf4_bytes"] <= led["fp16_bytes"]
    assert led["nf4_vs_fp16_ratio"] < 1.0


def test_memory_ledger_double_quant_is_smaller():
    led = memory_ledger(SHAPES, r=8)
    assert led["nf4_double_bytes"] < led["nf4_bytes"]


def test_memory_ledger_param_counts():
    led = memory_ledger(SHAPES, r=8)
    assert led["n_base_params"] == sum(a * b for a, b in SHAPES)
    assert led["n_adapter_params"] == sum(8 * (a + b) for a, b in SHAPES)
    assert led["adapter_bytes"] == 4.0 * led["n_adapter_params"]


def test_memory_ledger_fp16_is_half_of_fp32():
    led = memory_ledger(SHAPES, r=8)
    assert led["fp16_bytes"] == pytest.approx(led["fp32_bytes"] / 2)


@pytest.mark.parametrize("r", [1, 4, 8, 16, 32])
def test_memory_ledger_scales_with_rank(r):
    led = memory_ledger(SHAPES, r=r)
    assert led["n_adapter_params"] == sum(r * (a + b) for a, b in SHAPES)
    assert led["adapter_bytes"] == 4.0 * led["n_adapter_params"]


def test_training_memory_adam_is_16_bytes_per_trainable_param():
    m = training_memory(1_000_000, 100_000, optimizer="adam")
    assert m["grad_bytes"] == 4.0 * 100_000
    assert m["optimizer_bytes"] == 8.0 * 100_000
    assert m["param_bytes"] == 4.0 * 1_000_000


def test_training_memory_sgd_has_no_optimizer_state():
    m = training_memory(1_000_000, 100_000, optimizer="sgd")
    assert m["optimizer_bytes"] == 0.0


def test_training_memory_lora_is_much_cheaper():
    n_total, n_train = 257_792, 27_136
    full = training_memory(n_total, n_total, optimizer="adam")
    lora = training_memory(n_total, n_train, optimizer="adam")
    assert lora["total_bytes"] < full["total_bytes"] * 0.45
    assert lora["trainable_ratio"] == pytest.approx(n_train / n_total)


def test_training_memory_unknown_optimizer():
    with pytest.raises(ValueError):
        training_memory(100, 10, optimizer="rmsprop")


def test_human_bytes():
    assert human_bytes(512).endswith("B")
    assert "KB" in human_bytes(2048)
    assert "MB" in human_bytes(5 * 1024 ** 2)
