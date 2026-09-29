"""对称 INT8/INT4 量化及与 P08 NF4 的统一比较。"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .paths import ensure_deps_importable

ensure_deps_importable()

from ft.inject import named_parameters  # noqa: E402
from ft.quantize import dequantize_nf4, nf4_storage_bytes, quantize_nf4  # noqa: E402


@dataclass(frozen=True)
class QuantizedTensor:
    codes: np.ndarray
    scale: np.ndarray
    shape: tuple[int, ...]
    bits: int
    granularity: str
    channel_axis: int | None

    def dequantize(self, dtype=np.float64) -> np.ndarray:
        values = self.codes.astype(np.float64)
        if self.channel_axis is None:
            restored = values * float(np.asarray(self.scale).reshape(-1)[0])
        else:
            shape = [1] * len(self.shape)
            shape[self.channel_axis] = self.shape[self.channel_axis]
            restored = values * np.asarray(self.scale, dtype=np.float64).reshape(shape)
        return restored.reshape(self.shape).astype(dtype)

    @property
    def storage_bytes(self) -> float:
        return self.codes.size * self.bits / 8.0 + self.scale.size * 4.0


def quantize_symmetric(
    weights: np.ndarray,
    bits: int,
    granularity: str = "per_tensor",
    channel_axis: int = -1,
) -> QuantizedTensor:
    if bits not in (4, 8):
        raise ValueError("仅支持 INT4 或 INT8")
    if granularity not in ("per_tensor", "per_channel"):
        raise ValueError("granularity 必须是 per_tensor 或 per_channel")
    w = np.asarray(weights, dtype=np.float64)
    if w.size == 0:
        raise ValueError("权重不能为空")
    qmax = (1 << (bits - 1)) - 1
    axis: int | None = None
    if granularity == "per_tensor" or w.ndim == 0:
        absmax = np.array([np.max(np.abs(w))], dtype=np.float64)
        scale = np.where(absmax > 0, absmax / qmax, 1.0)
        codes = np.clip(np.rint(w / scale[0]), -qmax, qmax).astype(np.int8)
    else:
        axis = channel_axis % w.ndim
        reduce_axes = tuple(index for index in range(w.ndim) if index != axis)
        absmax = np.max(np.abs(w), axis=reduce_axes)
        scale = np.where(absmax > 0, absmax / qmax, 1.0)
        shape = [1] * w.ndim
        shape[axis] = w.shape[axis]
        codes = np.clip(np.rint(w / scale.reshape(shape)), -qmax, qmax).astype(np.int8)
    return QuantizedTensor(
        codes=codes, scale=np.asarray(scale, dtype=np.float32), shape=tuple(w.shape),
        bits=bits, granularity=granularity, channel_axis=axis,
    )


def quantize_int8(weights: np.ndarray, granularity: str = "per_tensor", channel_axis: int = -1) -> QuantizedTensor:
    return quantize_symmetric(weights, 8, granularity, channel_axis)


def quantize_int4(weights: np.ndarray, granularity: str = "per_tensor", channel_axis: int = -1) -> QuantizedTensor:
    return quantize_symmetric(weights, 4, granularity, channel_axis)


def quantization_error(weights: np.ndarray, restored: np.ndarray) -> dict:
    w = np.asarray(weights, dtype=np.float64)
    r = np.asarray(restored, dtype=np.float64)
    if w.shape != r.shape:
        raise ValueError("原权重与反量化权重形状不一致")
    diff = w - r
    norm = float(np.linalg.norm(w))
    return {
        "mse": float(np.mean(diff * diff)),
        "rmse": float(np.sqrt(np.mean(diff * diff))),
        "mean_abs": float(np.mean(np.abs(diff))),
        "max_abs": float(np.max(np.abs(diff))),
        "relative_l2": float(np.linalg.norm(diff) / norm) if norm else 0.0,
    }


def compression_ratio(qtensor: QuantizedTensor, source_bytes: int = 4) -> float:
    return float(qtensor.codes.size * source_bytes / qtensor.storage_bytes)


def compare_quantizers(weights: np.ndarray, granularity: str = "per_channel", block_size: int = 64) -> dict:
    w = np.asarray(weights, dtype=np.float64)
    out: dict[str, dict] = {}
    for name, fn in (("INT8", quantize_int8), ("INT4", quantize_int4)):
        quantized = fn(w, granularity=granularity)
        out[name] = {
            **quantization_error(w, quantized.dequantize()),
            "storage_bytes": quantized.storage_bytes,
            "compression_ratio": compression_ratio(quantized),
        }
    nf4 = quantize_nf4(w, block_size=block_size, double_quant=True)
    nf4_bytes = nf4_storage_bytes(w.size, block_size=block_size, double_quant=True)
    out["NF4"] = {
        **quantization_error(w, dequantize_nf4(nf4)),
        "storage_bytes": nf4_bytes,
        "compression_ratio": float(w.size * 4.0 / nf4_bytes),
    }
    return out


def quantize_model(model, bits: int, granularity: str = "per_channel"):
    """深拷贝模型，并把所有二维权重替换为量化后反量化值。"""
    copied = deepcopy(model)
    tensors: dict[str, QuantizedTensor] = {}
    weighted_mse = 0.0
    n_values = 0
    for path, parameter in named_parameters(copied):
        if parameter.data.ndim < 2:
            continue
        quantized = quantize_symmetric(parameter.data, bits, granularity)
        restored = quantized.dequantize(parameter.data.dtype)
        error = quantization_error(parameter.data, restored)
        weighted_mse += error["mse"] * parameter.data.size
        n_values += parameter.data.size
        parameter.data[:] = restored
        tensors[path] = quantized
    storage = sum(item.storage_bytes for item in tensors.values())
    return copied, {
        "bits": bits,
        "granularity": granularity,
        "n_tensors": len(tensors),
        "n_values": n_values,
        "mse": weighted_mse / n_values if n_values else 0.0,
        "storage_bytes": storage,
        "fp32_bytes": n_values * 4.0,
        "compression_ratio": n_values * 4.0 / storage if storage else 0.0,
        "tensors": tensors,
    }


def quantize_model_nf4(model, block_size: int = 64, double_quant: bool = True):
    """深拷贝模型，并把所有二维权重替换为 NF4 反量化值。"""
    copied = deepcopy(model)
    tensors = {}
    weighted_mse = 0.0
    n_values = 0
    storage = 0.0
    for path, parameter in named_parameters(copied):
        if parameter.data.ndim < 2:
            continue
        quantized = quantize_nf4(parameter.data, block_size=block_size, double_quant=double_quant)
        restored = dequantize_nf4(quantized).astype(parameter.data.dtype)
        error = quantization_error(parameter.data, restored)
        weighted_mse += error["mse"] * parameter.data.size
        n_values += parameter.data.size
        storage += nf4_storage_bytes(parameter.data.size, block_size, double_quant)
        parameter.data[:] = restored
        tensors[path] = quantized
    return copied, {
        "bits": 4,
        "granularity": f"nf4_block_{block_size}",
        "n_tensors": len(tensors),
        "n_values": n_values,
        "mse": weighted_mse / n_values if n_values else 0.0,
        "storage_bytes": storage,
        "fp32_bytes": n_values * 4.0,
        "compression_ratio": n_values * 4.0 / storage if storage else 0.0,
        "tensors": tensors,
    }


def save_quantized_artifact(report: dict, path: "str | Path") -> Path:
    """把量化 codes/scale 与元信息写入 P09 自己的 npz。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, np.ndarray] = {}
    metadata = {key: value for key, value in report.items() if key != "tensors"}
    for index, (name, tensor) in enumerate(report["tensors"].items()):
        arrays[f"codes_{index}"] = tensor.codes
        arrays[f"scale_{index}"] = tensor.scale
        metadata.setdefault("paths", []).append(name)
    arrays["metadata_json"] = np.frombuffer(json.dumps(metadata, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)
    np.savez(target, **arrays)
    return target


__all__ = [
    "QuantizedTensor", "compare_quantizers", "compression_ratio", "quantization_error",
    "quantize_int4", "quantize_int8", "quantize_model", "quantize_model_nf4",
    "quantize_symmetric", "save_quantized_artifact",
]
