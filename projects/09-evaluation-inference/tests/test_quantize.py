from __future__ import annotations

import os

import numpy as np
import pytest

from ie.paths import P09_MODELS
from ie.quantize import (
    compare_quantizers,
    compression_ratio,
    quantization_error,
    quantize_int4,
    quantize_int8,
    quantize_model,
    quantize_symmetric,
    save_quantized_artifact,
)


@pytest.mark.parametrize("shape", [(7,), (3, 5), (4, 3, 2)])
@pytest.mark.parametrize("bits", [4, 8])
@pytest.mark.parametrize("granularity", ["per_tensor", "per_channel"])
def test_roundtrip_shape_and_dtype(shape, bits, granularity):
    rng = np.random.default_rng(sum(shape) + bits)
    weights = rng.normal(size=shape)
    quantized = quantize_symmetric(weights, bits, granularity)
    restored = quantized.dequantize()
    assert restored.shape == weights.shape
    assert restored.dtype == np.float64
    assert quantized.codes.dtype == np.int8


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5])
def test_per_channel_mse_no_worse(seed):
    rng = np.random.default_rng(seed)
    weights = rng.normal(size=(128, 8)) * np.geomspace(0.01, 10.0, 8)
    tensor = quantize_int4(weights, "per_tensor").dequantize()
    channel = quantize_int4(weights, "per_channel").dequantize()
    assert quantization_error(weights, channel)["mse"] <= quantization_error(weights, tensor)["mse"] + 1e-15


def test_int8_error_lower_than_int4_on_random_weights():
    weights = np.random.default_rng(0).normal(size=(64, 32))
    e8 = quantization_error(weights, quantize_int8(weights).dequantize())["mse"]
    e4 = quantization_error(weights, quantize_int4(weights).dequantize())["mse"]
    assert e8 < e4


def test_zero_weights_roundtrip():
    weights = np.zeros((4, 5))
    assert np.array_equal(quantize_int4(weights, "per_channel").dequantize(), weights)


def test_int4_compression_includes_scale():
    q = quantize_int4(np.ones(100), "per_tensor")
    assert q.storage_bytes == 54.0
    assert compression_ratio(q) == pytest.approx(400 / 54)


def test_int8_compression_includes_channel_scales():
    q = quantize_int8(np.ones((10, 4)), "per_channel")
    assert q.storage_bytes == 56.0
    assert compression_ratio(q) == pytest.approx(160 / 56)


def test_nf4_comparison_is_finite():
    weights = np.random.default_rng(7).normal(size=(32, 32))
    result = compare_quantizers(weights)
    assert set(result) == {"INT8", "INT4", "NF4"}
    assert all(np.isfinite(row["mse"]) for row in result.values())
    assert result["NF4"]["mse"] != result["INT4"]["mse"]


def test_quantize_model_preserves_forward_shape(tiny_model):
    quantized, report = quantize_model(tiny_model, 8, "per_channel")
    output = quantized(np.array([[1, 2, 3]]), mask=None).data
    assert output.shape == (1, 3, 64)
    assert report["n_tensors"] > 0


def test_save_quantized_artifact(tiny_model):
    _model, report = quantize_model(tiny_model, 4, "per_tensor")
    # 用 pid 区分文件名，避免并发 pytest 进程互相删除同一个临时产物
    path = P09_MODELS / f"_test_quantized_{os.getpid()}.npz"
    try:
        saved = save_quantized_artifact(report, path)
        assert saved.is_file()
        assert saved.stat().st_size > 0
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("bits", [1, 2, 3, 5, 16])
def test_invalid_bits_rejected(bits):
    with pytest.raises(ValueError):
        quantize_symmetric(np.ones(3), bits)


def test_invalid_granularity_rejected():
    with pytest.raises(ValueError):
        quantize_int8(np.ones(3), "grouped")
