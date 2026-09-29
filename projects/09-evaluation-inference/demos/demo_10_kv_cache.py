#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _emit import Printer  # noqa: E402
from ie.kvbook import memory_table, qwen7b_reference, sequence_length_to_exceed_weights  # noqa: E402


def main() -> None:
    with Printer("demo_10_kv_cache") as out:
        out.section("M10 · KV Cache：显存账本")
        reference = qwen7b_reference()
        arch = reference["architecture"]
        weight_bytes = reference["weight_bytes"]
        out.kv("架构", f"layers={arch.layers}, kv_heads={arch.kv_heads}, head_dim={arch.head_dim}")
        out.kv("公式", "2 × layers × kv_heads × head_dim × dtype_bytes")
        out.kv("BF16 bytes/token", f"{reference['bytes_per_token']:,} B")
        out.kv("7B BF16 权重", f"{reference['weight_gib']:.2f} GiB")
        rows = memory_table(
            arch, seq_lengths=[512, 2048, 8192, 32768], batch_sizes=[1, 4, 16],
            dtype_bytes=2, weight_bytes=weight_bytes,
        )
        out.subsection("KV 随序列长度与 batch 线性增长")
        out.table(
            ["batch", "seq_len", "KV MiB", "KV GiB", "KV/权重"],
            [[row["batch_size"], f"{row['seq_len']:,}", f"{row['kv_mib']:.2f}",
              f"{row['kv_gib']:.3f}", f"{row['vs_weights']:.2%}"] for row in rows],
            aligns=[">", ">", ">", ">", ">"],
        )
        out.subsection("KV 何时超过权重")
        cross_rows = []
        for batch in (1, 4, 16, 64):
            threshold = sequence_length_to_exceed_weights(arch, weight_bytes, batch, 2)
            cross_rows.append([batch, f"{threshold:,}", f"{threshold * batch:,}"])
        out.table(["batch", "每请求 seq 阈值", "总缓存 token 阈值"], cross_rows, aligns=[">", ">", ">"])
        out.kv("batch=1 反超点", f"seq_len={reference['cross_seq_batch1']:,}")
        out.line("  KV 与 batch×seq_len 成正比；高并发长上下文下，它会从配角变成显存主体。")


if __name__ == "__main__":
    main()
