"""Milestone 09 —— 优化：把「能跑的模型」变成「部署得起的模型」。

模型训完就要面对三个现实问题：**太大、太慢、太贵**。本章给出三条优化路径，
并且**每条都用真实数字回答「代价是什么」** —— 优化不是免费的，
不量化代价的优化等于没做：

1. **权重量化**（INT8 / INT4，per-channel）：复用 P09 的 ``quantize_model``。
   代价用**验证困惑度的变化**衡量，而不是只看压缩比。
2. **KV Cache**：复用 P09 的账本算「每 token 多少字节」，
   并回答「多长的上下文会让 KV Cache 超过模型权重本身」。
   代价是显存，收益是避免重复计算 —— 速度实测交给 M08 的 :meth:`Generator.benchmark`。
3. **部署体积账**：fp64 → fp32 → INT8 → INT4 一路排下来，
   给出「这个模型最终要占多少空间」。

一个刻意保留的结论：**INT4 在 20 万参数的小模型上代价明显大于 INT8**。
因为小模型每层权重少、冗余低，4 bit 的粗粒度误差占比反而更高 ——
这和 7B 模型上「INT4 基本无损」的常识是**相反**的，值得实测一次记住。
"""

from __future__ import annotations

import numpy as np

from .config import TinyConfig
from .train import evaluate_loss

from ie.kvbook import (  # noqa: E402
    KVArchitecture,
    bytes_per_token,
    kv_cache_bytes,
    memory_table,
    model_weight_bytes,
    sequence_length_to_exceed_weights,
)
from ie.quantize import (  # noqa: E402
    compare_quantizers,
    quantize_model,
    quantize_model_nf4,
)

__all__ = [
    "deployment_size_table",
    "kv_cache_report",
    "optimization_report",
    "quantization_report",
]


def deployment_size_table(model, parameters: int) -> list[dict]:
    """同一份模型在不同精度下的体积账。"""
    rows = []
    for label, bytes_per_param in (
        ("fp64（训练时）", 8),
        ("fp32（常见推理）", 4),
        ("fp16 / bf16", 2),
        ("INT8", 1),
        ("INT4", 0.5),
    ):
        size = model_weight_bytes(parameters, bytes_per_param)
        rows.append(
            {
                "precision": label,
                "bytes_per_param": bytes_per_param,
                "bytes": size,
                "mib": size / 1024 ** 2,
            }
        )
    return rows


def kv_cache_report(cfg: TinyConfig, model, parameters: "int | None" = None) -> dict:
    """KV Cache 账本：每 token 多少字节、多长上下文会超过权重。"""
    m = cfg.model
    arch = KVArchitecture(
        layers=m.n_layers, kv_heads=m.n_heads, head_dim=m.d_model // m.n_heads
    )
    per_token_fp32 = bytes_per_token(arch, dtype_bytes=4)
    per_token_fp16 = bytes_per_token(arch, dtype_bytes=2)
    weight_bytes = model_weight_bytes(parameters if parameters is not None else 0, 4)
    seq_lengths = [64, 256, 1024, 4096]
    batches = [1, 4]
    return {
        "architecture": {
            "layers": arch.layers,
            "kv_heads": arch.kv_heads,
            "head_dim": arch.head_dim,
        },
        "bytes_per_token_fp32": per_token_fp32,
        "bytes_per_token_fp16": per_token_fp16,
        "weight_bytes_fp32": weight_bytes,
        "table": memory_table(arch, seq_lengths, batches, dtype_bytes=2, weight_bytes=weight_bytes or None),
        "seq_len_to_exceed_weights": (
            sequence_length_to_exceed_weights(arch, weight_bytes, 1, 2) if weight_bytes else None
        ),
        "kv_bytes_at_max_len": kv_cache_bytes(arch, m.max_len, 1, 4),
    }


def quantization_report(
    cfg: TinyConfig,
    model,
    val_examples,
    bits_list=(8, 4),
    granularity: str = "per_channel",
) -> dict:
    """逐个精度量化，量出**体积收益**与**精度代价**。"""
    before = evaluate_loss(model, val_examples, cfg.train.batch_size)
    results: dict[str, dict] = {}
    for bits in bits_list:
        quantized_model, report = quantize_model(model, bits, granularity=granularity)
        after = evaluate_loss(quantized_model, val_examples, cfg.train.batch_size)
        results[f"INT{bits}"] = {
            "bits": bits,
            "granularity": granularity,
            "n_tensors": report["n_tensors"],
            "storage_bytes": report["storage_bytes"],
            "fp32_bytes": report["fp32_bytes"],
            "compression_ratio": report["compression_ratio"],
            "mse": report["mse"],
            "val_loss_before": before["loss"],
            "val_loss_after": after["loss"],
            "val_loss_delta": after["loss"] - before["loss"],
            "ppl_before": before["perplexity"],
            "ppl_after": after["perplexity"],
            "ppl_delta_pct": (after["perplexity"] - before["perplexity"])
            / before["perplexity"] * 100.0,
            "token_accuracy_after": after["token_accuracy"],
        }
    nf4_model, nf4_report = quantize_model_nf4(model, block_size=64, double_quant=True)
    nf4_after = evaluate_loss(nf4_model, val_examples, cfg.train.batch_size)
    results["NF4"] = {
        "bits": 4,
        "granularity": "nf4_block_64",
        "n_tensors": nf4_report["n_tensors"],
        "storage_bytes": nf4_report["storage_bytes"],
        "fp32_bytes": nf4_report["fp32_bytes"],
        "compression_ratio": nf4_report["compression_ratio"],
        "mse": nf4_report["mse"],
        "val_loss_before": before["loss"],
        "val_loss_after": nf4_after["loss"],
        "val_loss_delta": nf4_after["loss"] - before["loss"],
        "ppl_before": before["perplexity"],
        "ppl_after": nf4_after["perplexity"],
        "ppl_delta_pct": (nf4_after["perplexity"] - before["perplexity"])
        / before["perplexity"] * 100.0,
        "token_accuracy_after": nf4_after["token_accuracy"],
    }
    return {"baseline": before, "quantizers": results}


def _biggest_weight_tensor(model):
    """找出参数量最大的二维权重 —— 拿它做 per-tensor vs per-channel 对照最有代表性。"""
    from .model import walk_parameters

    named = walk_parameters(model)
    candidates = [(p.data.size, name, p) for name, p in named if p.data.ndim >= 2]
    if not candidates:
        raise ValueError("模型里没有二维权重")
    _size, name, param = max(candidates, key=lambda item: item[0])
    return name, param


def granularity_report(model) -> dict:
    """per-tensor vs per-channel vs NF4：同一份权重的误差对照。"""
    name, param = _biggest_weight_tensor(model)
    comparison = compare_quantizers(param.data, granularity="per_channel", block_size=64)
    per_tensor = compare_quantizers(param.data, granularity="per_tensor", block_size=64)
    return {
        "tensor": name,
        "shape": tuple(param.data.shape),
        "per_channel": comparison,
        "per_tensor": per_tensor,
        "std_over_mean_abs": float(
            np.std(np.abs(param.data)) / max(np.mean(np.abs(param.data)), 1e-12)
        ),
    }


def optimization_report(
    cfg: TinyConfig,
    model,
    val_examples,
    generator=None,
    prompt: str = "问：什么是 LoRA？答：",
) -> dict:
    """一次跑完「量化 + KV Cache + 速度」三本账。"""
    from .model import parameter_report

    params = parameter_report(model)
    report = {
        "parameters": params,
        "deployment_size": deployment_size_table(model, params["total"]),
        "kv_cache": kv_cache_report(cfg, model, params["total"]),
        "quantization": quantization_report(cfg, model, val_examples),
        "granularity": granularity_report(model),
    }
    if generator is not None:
        report["speed"] = generator.benchmark(prompt, repeats=5)
        report["cache_consistency_error"] = generator.cache_consistency_error(prompt)
    return report
