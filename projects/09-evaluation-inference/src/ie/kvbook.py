"""KV Cache 显存账本。"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class KVArchitecture:
    layers: int
    kv_heads: int
    head_dim: int

    def __post_init__(self) -> None:
        if self.layers <= 0 or self.kv_heads <= 0 or self.head_dim <= 0:
            raise ValueError("架构字段必须为正整数")


def bytes_per_token(architecture: KVArchitecture, dtype_bytes: int = 2) -> int:
    if dtype_bytes <= 0:
        raise ValueError("dtype_bytes 必须为正")
    return 2 * architecture.layers * architecture.kv_heads * architecture.head_dim * dtype_bytes


def kv_cache_bytes(
    architecture: KVArchitecture,
    seq_len: int,
    batch_size: int = 1,
    dtype_bytes: int = 2,
) -> int:
    if seq_len < 0 or batch_size < 0:
        raise ValueError("seq_len 与 batch_size 不能为负")
    return bytes_per_token(architecture, dtype_bytes) * seq_len * batch_size


def memory_table(
    architecture: KVArchitecture,
    seq_lengths: list[int],
    batch_sizes: list[int],
    dtype_bytes: int = 2,
    weight_bytes: "int | None" = None,
) -> list[dict]:
    rows = []
    for batch in batch_sizes:
        for seq_len in seq_lengths:
            total = kv_cache_bytes(architecture, seq_len, batch, dtype_bytes)
            rows.append({
                "batch_size": batch,
                "seq_len": seq_len,
                "kv_bytes": total,
                "kv_mib": total / 1024**2,
                "kv_gib": total / 1024**3,
                "vs_weights": total / weight_bytes if weight_bytes else None,
            })
    return rows


def sequence_length_to_exceed_weights(
    architecture: KVArchitecture,
    weight_bytes: int,
    batch_size: int = 1,
    dtype_bytes: int = 2,
) -> int:
    if weight_bytes <= 0 or batch_size <= 0:
        raise ValueError("weight_bytes 与 batch_size 必须为正")
    per_position = bytes_per_token(architecture, dtype_bytes) * batch_size
    return math.floor(weight_bytes / per_position) + 1


def model_weight_bytes(parameters: int, dtype_bytes: int = 2) -> int:
    if parameters < 0 or dtype_bytes <= 0:
        raise ValueError("参数量不能为负，dtype_bytes 必须为正")
    return parameters * dtype_bytes


def qwen7b_reference() -> dict:
    """从 28 层、4 个 KV 头、head_dim=128 重新推导 P07 的数字。"""
    architecture = KVArchitecture(layers=28, kv_heads=4, head_dim=128)
    per_token = bytes_per_token(architecture, dtype_bytes=2)
    weight_gib = 14.18
    weight_bytes = int(weight_gib * 1024**3)
    return {
        "architecture": architecture,
        "bytes_per_token": per_token,
        "weight_gib": weight_gib,
        "weight_bytes": weight_bytes,
        "cross_seq_batch1": sequence_length_to_exceed_weights(architecture, weight_bytes, 1, 2),
    }


__all__ = [
    "KVArchitecture", "bytes_per_token", "kv_cache_bytes", "memory_table",
    "model_weight_bytes", "qwen7b_reference", "sequence_length_to_exceed_weights",
]
