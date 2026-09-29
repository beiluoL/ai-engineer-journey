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
from ie.paged import PagedKVCache, memory_comparison  # noqa: E402


def main() -> None:
    with Printer("demo_08_paged_attention") as out:
        out.section("M08 · PagedAttention：按需 KV 物理块")
        layers, heads, head_dim, dtype_bytes = 2, 4, 16, 8
        token_bytes = 2 * layers * heads * head_dim * dtype_bytes
        lengths = [9, 17, 33, 62]
        memory = memory_comparison(lengths, max_seq_len=128, block_size=8, bytes_per_token=token_bytes)
        out.kv("KV bytes/token", f"{token_bytes:,}")
        out.kv("序列长度", lengths)
        out.kv("连续预分配", f"{memory['contiguous_bytes'] / 1024:.1f} KiB")
        out.kv("分页按需分配", f"{memory['paged_bytes'] / 1024:.1f} KiB")
        out.kv("浪费率", f"{memory['contiguous_waste_rate']:.1%} → {memory['paged_waste_rate']:.1%}")
        out.kv("节省", f"{memory['saved_rate']:.1%}")

        cache = PagedKVCache(num_blocks=32, block_size=8, token_bytes=token_bytes)
        snapshots = []
        for request_id, length in zip(("A", "B", "C", "D"), lengths):
            cache.append(request_id, length)
            snapshots.append([f"加入 {request_id}:{length}", dict(cache.block_table), cache.stats()["free_blocks"]])
        released = cache.release("B")
        snapshots.append(["释放 B", dict(cache.block_table), cache.stats()["free_blocks"]])
        shared = cache.share_prefix("A", "E", 8)
        cache.append("E", 7)
        snapshots.append([f"E 共享 A 前缀块 {shared}", dict(cache.block_table), cache.stats()["free_blocks"]])
        victim, reclaimed = cache.preempt(protected={"A", "E"})
        snapshots.append([f"抢占 {victim}，回收 {reclaimed}", dict(cache.block_table), cache.stats()["free_blocks"]])
        out.subsection("Block table 演化")
        out.table(
            ["操作", "block_table", "空闲块"],
            [[label, table, free] for label, table, free in snapshots],
            aligns=["<", "<", ">"],
        )
        stats = cache.stats()
        out.subsection("池守恒与共享")
        out.kv("物理块", f"已用 {stats['used_blocks']} + 空闲 {stats['free_blocks']} = {cache.num_blocks}")
        out.kv("逻辑引用 / 物理块", f"{stats['logical_block_refs']} / {stats['used_blocks']}")
        out.kv("共享引用", stats["shared_refs"])
        out.kv("池不变量", cache.check_invariants())


if __name__ == "__main__":
    main()
