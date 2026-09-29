"""``ft.quantize`` —— NF4 分位量化 + 双量化。

NF4 的两条硬性质必须被守住：
1. 码本 16 个值、包含 0（否则 0 权重会被量化成非 0，稀疏性被破坏）。
2. 量化是**分块 absmax + 最近邻查表**，不是 round —— 这两者的误差差得出来。
"""

from __future__ import annotations

import numpy as np
import pytest

from ft import (
    NF4_LEVELS,
    dequantize_nf4,
    nf4_codebook,
    nf4_storage_bytes,
    quantization_error,
    quantize_nf4,
)


# ---------------------------------------------------------------- 码本


def test_codebook_has_16_levels():
    assert len(NF4_LEVELS) == 16
    assert len(nf4_codebook()) == 16


def test_codebook_is_sorted_and_in_range():
    cb = nf4_codebook()
    assert np.all(np.diff(cb) > 0)
    assert cb.min() == -1.0 and cb.max() == 1.0


def test_codebook_contains_zero():
    assert np.any(NF4_LEVELS == 0.0)


def test_codebook_is_not_uniform():
    """NF4 的关键：电平不等距（按正态分布的分位数切）。"""
    gaps = np.diff(NF4_LEVELS)
    assert gaps.max() / gaps.min() > 2.0


def test_codebook_values_match_paper():
    expected = np.array(
        [-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
         -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
         0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
         0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
         0.7229568362236023, 1.0]
    )
    assert np.allclose(NF4_LEVELS, expected, atol=0, rtol=0)


# ---------------------------------------------------------------- 量化 / 反量化


def test_dequantize_keeps_shape():
    w = np.random.randn(64, 256) * 0.02
    q = quantize_nf4(w, block_size=64)
    assert dequantize_nf4(q).shape == w.shape


@pytest.mark.parametrize("shape", [(64, 64), (64, 256), (256, 64), (33, 17)])
def test_dequantize_keeps_shape_parametrized(shape):
    w = np.random.randn(*shape) * 0.02
    assert dequantize_nf4(quantize_nf4(w)).shape == shape


def test_codes_are_within_0_15():
    w = np.random.randn(128, 32) * 0.02
    q = quantize_nf4(w)
    assert q.codes.min() >= 0 and q.codes.max() <= 15
    assert q.codes.dtype == np.uint8


def test_quantization_error_is_reasonable():
    """4 bit 量化的相对误差应落在 3%~20% —— 太大说明实现错了，太小说明根本没量化。"""
    w = np.random.default_rng(0).normal(0, 0.02, (64, 256))
    err = quantization_error(w, dequantize_nf4(quantize_nf4(w)))
    assert 0.03 < err["rel_l2"] < 0.20
    assert err["mse"] > 0


def test_extreme_values_keep_sign():
    """最大的正权重和最小的负权重，量化后符号不能翻转。"""
    w = np.random.default_rng(0).normal(0, 0.02, (64, 256))
    w_hat = dequantize_nf4(quantize_nf4(w))
    i_max = int(np.argmax(w))
    i_min = int(np.argmin(w))
    assert w_hat.flat[i_max] > 0
    assert w_hat.flat[i_min] < 0


def test_zero_block_is_safe():
    """全零块不能出现 0/0 —— 反量化结果必须还是全零。"""
    w = np.zeros((64, 64))
    assert np.array_equal(dequantize_nf4(quantize_nf4(w)), w)


def test_absmax_normalization_bounds():
    """每个块的 absmax 归一化后，权重必须落在 [-1, 1]。

    容差取 1e-6 而不是机器精度：absmax 按 QLoRA 惯例以 **fp32** 存放，
    而本项目其他张量是 fp64，fp32 舍入会让归一化后的最大值出现 ~1e-7 的相对溢出。
    这点误差相对 4bit 量化本身的 9% 误差完全可以忽略。
    """
    w = np.random.default_rng(0).normal(0, 0.02, (64, 256))
    q = quantize_nf4(w, block_size=64)
    normed = w.reshape(-1) / np.repeat(np.asarray(q.absmax, dtype=np.float64), 64)[: w.size]
    assert np.abs(normed).max() <= 1.0 + 1e-6


def test_smaller_block_is_more_accurate():
    """分块越小，离群值的影响越小，误差越低。"""
    w = np.random.default_rng(0).normal(0, 0.02, (256, 256))
    e32 = quantization_error(w, dequantize_nf4(quantize_nf4(w, block_size=32)))["rel_l2"]
    e256 = quantization_error(w, dequantize_nf4(quantize_nf4(w, block_size=256)))["rel_l2"]
    assert e32 < e256


def test_nearest_neighbor_beats_uniform_round():
    """NF4（分位）的误差必须小于均匀 int4 —— 否则 NF4 就没意义了。"""
    w = np.random.default_rng(0).normal(0, 0.02, (256, 256))

    def quantize_with_levels(levels, block_size=64):
        flat = w.reshape(-1)
        n_blocks = int(np.ceil(flat.size / block_size))
        pad = n_blocks * block_size - flat.size
        if pad:
            flat = np.concatenate([flat, np.zeros(pad)])
        blocks = flat.reshape(n_blocks, block_size)
        absmax = np.abs(blocks).max(axis=1)
        absmax = np.where(absmax <= 0, 1.0, absmax)
        normed = blocks / absmax[:, None]
        idx = np.argmin(np.abs(normed[:, :, None] - levels[None, None, :]), axis=2)
        return ((levels[idx] * absmax[:, None]).reshape(-1)[: w.size]).reshape(w.shape)

    e_nf4 = quantization_error(w, quantize_with_levels(NF4_LEVELS))["rel_l2"]
    e_uni = quantization_error(w, quantize_with_levels(np.linspace(-1, 1, 16)))["rel_l2"]
    assert e_nf4 < e_uni


# ---------------------------------------------------------------- 双量化


def test_double_quant_saves_bytes():
    n = 163_840
    assert nf4_storage_bytes(n, double_quant=True) < nf4_storage_bytes(n, double_quant=False)


def test_double_quant_saving_is_about_8_percent():
    """absmax 从 fp32 压到 8bit，理论上能省掉 absmax 的 3/4 ≈ 8.3%。"""
    n = 163_840
    sq = nf4_storage_bytes(n, double_quant=False)
    dq = nf4_storage_bytes(n, double_quant=True)
    assert 0.05 < (1 - dq / sq) < 0.12


def test_double_quant_costs_little_accuracy():
    w = np.random.default_rng(0).normal(0, 0.02, (64, 256))
    e_sq = quantization_error(w, dequantize_nf4(quantize_nf4(w, 64, False)))["rel_l2"]
    e_dq = quantization_error(w, dequantize_nf4(quantize_nf4(w, 64, True)))["rel_l2"]
    assert e_dq / e_sq < 1.05  # 误差恶化不超过 5%


def test_double_quant_stores_codes_and_scale():
    q = quantize_nf4(np.random.randn(64, 256) * 0.02, double_quant=True)
    assert q.absmax_codes is not None and q.absmax_scale is not None
    assert q.absmax_codes.dtype == np.uint8
    assert q.absmax_codes.max() <= 127


# ---------------------------------------------------------------- 体积账


def test_nf4_is_about_one_eighth_of_fp32():
    n = 1_000_000
    ratio = 4.0 * n / nf4_storage_bytes(n, block_size=64, double_quant=False)
    assert 6.5 < ratio <= 8.0


def test_nf4_double_quant_ratio():
    n = 1_000_000
    ratio = 4.0 * n / nf4_storage_bytes(n, block_size=64, double_quant=True)
    assert 7.0 < ratio <= 8.0


def test_nf4_beats_fp16():
    n = 1_000_000
    assert nf4_storage_bytes(n, double_quant=True) < 2.0 * n


def test_quantization_error_keys():
    w = np.random.randn(32, 32)
    err = quantization_error(w, w * 0.999)
    assert set(err) == {"mse", "rmse", "max_abs", "rel_l2", "mean_abs", "std_w"}
    assert err["rel_l2"] == pytest.approx(0.001, abs=1e-9)
