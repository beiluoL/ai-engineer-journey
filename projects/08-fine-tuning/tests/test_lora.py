"""``ft.lora`` —— LoRA 线性层本身。

这里的每个断言都在守护同一个核心性质：
**LoRA 是「基座 + 增量」**，不是「换个模型」。所以初始化时必须 ΔW=0，
缩放必须是 alpha/r，梯度必须能穿过冻结的 W 正确流到 A 和 B。
"""

from __future__ import annotations

import numpy as np
import pytest

from ft import LoRAConfig, LoRALinear
from model import Tensor, cross_entropy, grad_check


# ---------------------------------------------------------------- 形状 / 初始化


def test_output_shape_2d():
    """LoRA 层的输出 shape 必须和普线性层一致。"""
    layer = LoRALinear(8, 16, r=4, alpha=8.0, rng=0)
    out = layer(Tensor(np.random.randn(3, 8)))
    assert out.data.shape == (3, 16)


@pytest.mark.parametrize("in_f,out_f,r", [(8, 16, 1), (16, 32, 4), (64, 256, 8), (32, 8, 2)])
def test_output_shape_parametrized(in_f, out_f, r):
    layer = LoRALinear(in_f, out_f, r=r, alpha=float(2 * r), rng=0)
    out = layer(Tensor(np.random.randn(5, in_f)))
    assert out.data.shape == (5, out_f)


def test_a_and_b_shapes():
    layer = LoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert layer.A.data.shape == (64, 8)
    assert layer.B.data.shape == (8, 256)
    assert layer.W.data.shape == (64, 256)


def test_b_is_zero_initialized():
    """教科书初始化：A 小随机、B 全零。"""
    layer = LoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert np.all(layer.B.data == 0.0)
    assert np.any(layer.A.data != 0.0)


def test_a_is_small_not_zero():
    """A 必须是小值（不是全零、也不是 O(1)）。"""
    layer = LoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert np.any(layer.A.data != 0.0)
    bound = 1.0 / np.sqrt(64)
    assert np.abs(layer.A.data).max() <= bound + 1e-12


# ---------------------------------------------------------------- 等价性


def test_b_zero_makes_lora_identical_to_base():
    """B=0 时 LoRA 输出必须**逐位等于**纯基座输出。"""
    layer = LoRALinear(32, 48, r=4, alpha=8.0, rng=0)
    x = Tensor(np.random.randn(6, 32))
    assert np.array_equal(layer(x).data, x.data @ layer.W.data)


def test_delta_weight_is_all_zero_at_init():
    layer = LoRALinear(32, 48, r=4, alpha=8.0, rng=0)
    assert np.all(layer.delta_weight() == 0.0)
    assert np.max(np.abs(layer.delta_weight())) == 0.0


def test_merged_weight_equals_base_at_init():
    layer = LoRALinear(32, 48, r=4, alpha=8.0, rng=0)
    assert np.array_equal(layer.merged_weight(), layer.W.data)


def test_nonzero_b_breaks_equivalence():
    """反过来验一遍：B 一旦非零，输出就必须不同（防止测试恒真）。"""
    layer = LoRALinear(32, 48, r=4, alpha=8.0, rng=0)
    x = Tensor(np.random.randn(6, 32))
    layer.B.data[:] = np.random.randn(*layer.B.data.shape) * 0.1
    assert not np.allclose(layer(x).data, x.data @ layer.W.data)


# ---------------------------------------------------------------- 缩放


@pytest.mark.parametrize("alpha,r", [(1.0, 1), (8.0, 4), (16.0, 8), (32.0, 16), (4.0, 8)])
def test_scaling_is_alpha_over_r(alpha, r):
    layer = LoRALinear(16, 24, r=r, alpha=alpha, rng=0)
    layer.B.data[:] = np.random.default_rng(1).normal(0, 0.1, size=layer.B.data.shape)
    expected = (alpha / r) * (layer.A.data @ layer.B.data)
    assert np.allclose(layer.delta_weight(), expected, atol=1e-15)
    assert layer.scaling == pytest.approx(alpha / r)


def test_larger_alpha_gives_larger_deviation():
    """alpha 越大，输出偏离基座越多（证明缩放真的进了前向）。"""
    x = Tensor(np.random.randn(4, 16))
    base_w = np.random.default_rng(0).normal(0, 0.02, (16, 24))
    devs = []
    for alpha in (1.0, 4.0, 16.0):
        layer = LoRALinear(16, 24, r=4, alpha=alpha, weight=base_w, rng=0)
        layer.B.data[:] = 0.01
        devs.append(np.linalg.norm(layer(x).data - x.data @ base_w))
    assert devs[0] < devs[1] < devs[2]


# ---------------------------------------------------------------- 梯度


def test_grad_check_on_a_and_b():
    """autograd 的 dL/dA、dL/dB 必须和中心差分一致。"""
    layer = LoRALinear(16, 24, r=4, alpha=8.0, rng=0)
    layer.B.data[:] = np.random.default_rng(2).normal(0, 0.05, size=layer.B.data.shape)
    x = Tensor(np.random.randn(5, 16))
    targets = np.random.randint(0, 24, size=5)
    A, B = layer.A, layer.B

    def f(a, b):
        layer.A, layer.B = a, b
        return cross_entropy(layer(x), targets)

    err = grad_check(f, [A, B], eps=1e-6)
    assert err < 1e-4, f"grad_check 最大相对误差 {err:.3e} 超过 1e-4"


def test_gradient_reaches_a_and_b():
    """反传之后 A、B 的梯度不能是 None / 全零。"""
    layer = LoRALinear(16, 24, r=4, alpha=8.0, rng=0)
    layer.B.data[:] = 0.01
    loss = cross_entropy(layer(Tensor(np.random.randn(5, 16))), np.random.randint(0, 24, 5))
    loss.backward()
    assert layer.A.grad is not None and np.any(layer.A.grad != 0)
    assert layer.B.grad is not None and np.any(layer.B.grad != 0)


def test_b_grad_is_nonzero_even_when_b_is_zero():
    """B 全零时 dL/dB 依然非零（否则永远学不起来）—— 这正是 B=0 可用的原因。"""
    layer = LoRALinear(16, 24, r=4, alpha=8.0, rng=0)
    loss = cross_entropy(layer(Tensor(np.random.randn(5, 16))), np.random.randint(0, 24, 5))
    loss.backward()
    assert np.any(layer.B.grad != 0.0)


def test_frozen_w_is_not_in_compute_graph():
    """冻结的 W 不参与计算图，因此不会被写梯度。"""
    layer = LoRALinear(16, 24, r=4, alpha=8.0, rng=0)
    loss = cross_entropy(layer(Tensor(np.random.randn(5, 16))), np.random.randint(0, 24, 5))
    loss.backward()
    assert layer.W.grad is None


def test_grads_do_not_accumulate_across_backward():
    """连续两次 backward，梯度不应累加（backward 会清零图内节点）。"""
    layer = LoRALinear(16, 24, r=4, alpha=8.0, rng=0)
    x = Tensor(np.random.randn(5, 16))
    t = np.random.randint(0, 24, 5)
    loss = cross_entropy(layer(x), t)
    loss.backward()
    g1 = layer.A.grad.copy()
    loss2 = cross_entropy(layer(x), t)
    loss2.backward()
    assert np.array_equal(layer.A.grad, g1)


# ---------------------------------------------------------------- 杂项


def test_dropout_must_be_zero():
    """本项目不支持 LoRA 的 input dropout —— 必须显式报错而不是静默失效。"""
    with pytest.raises(ValueError):
        LoRALinear(8, 16, r=4, alpha=8.0, dropout=0.1)


def test_invalid_rank():
    with pytest.raises(ValueError):
        LoRALinear(8, 16, r=0, alpha=8.0)


def test_reuse_existing_weight_object():
    """传 Parameter 进来时必须**复用**同一个对象（冻结的原权重）。"""
    w = Tensor(np.random.randn(8, 16))
    from model import Parameter

    p = Parameter(np.random.randn(8, 16))
    layer = LoRALinear(8, 16, r=4, alpha=8.0, weight=p)
    assert layer.W is p
    assert w is not None


def test_parameter_count():
    layer = LoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    assert layer.num_parameters(trainable_only=True) == 64 * 8 + 8 * 256
    assert layer.num_parameters(trainable_only=False) == 64 * 256 + 64 * 8 + 8 * 256


def test_trainable_parameters_returns_only_a_and_b():
    layer = LoRALinear(64, 256, r=8, alpha=16.0, rng=0)
    params = layer.trainable_parameters()
    assert len(params) == 2
    assert params[0] is layer.A and params[1] is layer.B


def test_lora_config_roundtrip():
    cfg = LoRAConfig(r=8, alpha=16.0, dropout=0.0)
    d = cfg.to_dict()
    assert d == {"r": 8, "alpha": 16.0, "dropout": 0.0}
    back = LoRAConfig.from_dict(d)
    assert back.r == 8 and back.alpha == 16.0 and back.scaling == 2.0


def test_deterministic_init_with_same_seed():
    a = LoRALinear(32, 48, r=4, alpha=8.0, rng=7)
    b = LoRALinear(32, 48, r=4, alpha=8.0, rng=7)
    assert np.array_equal(a.A.data, b.A.data)
