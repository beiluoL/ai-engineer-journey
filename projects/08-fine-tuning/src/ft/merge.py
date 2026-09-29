"""合并 / 不合并 —— LoRA 部署时的最后一个选择。

LoRA 有个常被忽略的好处：**它是可以「融化」回基座的**。

    W' = W + (alpha/r) · B @ A

因为 LoRA 分支是线性层，前向只是「两次矩阵乘」，所以完全可以把它加回 ``W``
得到一个**形状、结构、推理速度完全不变**的普通模型。推理时没有任何额外开销。

于是部署有两个选项：

    ┌─ 合并（merge）     推理零额外开销；但每个任务一份完整权重，切换任务要重新加载
    └─ 不合并（load）    一个基座常驻显存，切换任务只换几 MB 的 adapter；
                         代价是每次前向多两次小矩阵乘（r 很小时约几个百分点）

本项目两种都实现，并**用数值证明它们等价**（最大绝对误差 ~1e-15 量级），
再用真实计时给出两者的推理耗时差。
"""

from __future__ import annotations

import time
from copy import deepcopy

import numpy as np

from .paths import ensure_p06_importable

ensure_p06_importable()

from model import Parameter, Tensor  # noqa: E402

from .inject import count_parameters, lora_layers, set_param  # noqa: E402
from .lora import LoRALinear  # noqa: E402
from .qlora import QLoRALinear  # noqa: E402

__all__ = [
    "merge_lora",
    "unmerge_lora",
    "time_forward",
    "lora_overhead_report",
    "max_abs_diff",
]


def max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    """两组输出的最大绝对误差（等价性证明用）。"""
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


def merge_lora(model) -> dict:
    """把 ``W + ΔW`` 写回成一个普通 ``Parameter``，原地替换所有 LoRA 层。

    Returns
    -------
    dict: 备份（``unmerge_lora`` 可以用它还原回分离状态）
    """
    layers = lora_layers(model)
    if not layers:
        raise RuntimeError("模型里没有 LoRA 层 —— 先 inject_lora")
    backup: dict = {"layers": []}
    for path, layer in layers:
        backup["layers"].append(
            {
                "path": path,
                "W": np.array(layer.W.data) if hasattr(layer, "W") else None,
                "A": np.array(layer.A.data),
                "B": np.array(layer.B.data),
                "r": layer.r,
                "alpha": layer.alpha,
                "kind": "qlora" if isinstance(layer, QLoRALinear) else "lora",
                "block_size": getattr(layer, "block_size", 64),
                "double_quant": getattr(layer, "double_quant", True),
            }
        )
        merged = layer.merged_weight()
        set_param(model, path, Parameter(merged))
    return backup


def unmerge_lora(model, backup: dict) -> None:
    """把合并后的权重还原成「基座 + LoRA 分离」的结构（A/B 取备份值）。"""
    for entry in backup["layers"]:
        kind = entry["kind"]
        if kind == "qlora":
            layer = QLoRALinear(
                entry["W"].shape[0], entry["W"].shape[1],
                r=entry["r"], alpha=entry["alpha"], weight=entry["W"],
                block_size=entry["block_size"], double_quant=entry["double_quant"],
            )
        else:
            layer = LoRALinear(
                entry["W"].shape[0], entry["W"].shape[1],
                r=entry["r"], alpha=entry["alpha"], weight=Parameter(entry["W"]),
            )
        layer.A.data[:] = entry["A"]
        layer.B.data[:] = entry["B"]
        set_param(model, entry["path"], layer)


def time_forward(model, x: np.ndarray, n_repeat: int = 20, warmup: int = 3) -> dict:
    """真实计时：跑 ``n_repeat`` 次前向，返回总耗时与单次均值。"""
    for _ in range(warmup):
        model(x, mask=None)
    t0 = time.perf_counter()
    for _ in range(n_repeat):
        model(x, mask=None)
    dt = time.perf_counter() - t0
    return {"n_repeat": n_repeat, "total_sec": dt, "per_forward_ms": dt / n_repeat * 1000.0}


def lora_overhead_report(model, batch_size: int = 4, seq_len: int = 256) -> dict:
    """「不合并、只加载 adapter」的额外计算开销（MACs，理论值）。"""
    base_macs = 0
    lora_macs = 0
    n_layers = 0
    for _path, layer in lora_layers(model):
        n_layers += 1
        in_f, out_f = layer.in_features, layer.out_features
        base_macs += in_f * out_f
        lora_macs += layer.r * (in_f + out_f)
    tokens = batch_size * seq_len
    return {
        "n_lora_layers": n_layers,
        "base_macs_per_token": base_macs,
        "lora_macs_per_token": lora_macs,
        "overhead_ratio": lora_macs / base_macs if base_macs else 0.0,
        "lora_macs_per_batch": lora_macs * tokens,
        "base_macs_per_batch": base_macs * tokens,
    }
