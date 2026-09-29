"""PagedAttention 的物理块池、block table、共享与抢占。"""

from __future__ import annotations

import math

import numpy as np


class PagedKVCache:
    def __init__(self, num_blocks: int, block_size: int = 8, token_bytes: int = 1) -> None:
        if num_blocks <= 0 or block_size <= 0 or token_bytes <= 0:
            raise ValueError("num_blocks、block_size、token_bytes 必须为正数")
        self.num_blocks = int(num_blocks)
        self.block_size = int(block_size)
        self.token_bytes = int(token_bytes)
        self.blocks = np.zeros((num_blocks, block_size, token_bytes), dtype=np.uint8)
        self.free_blocks = list(range(num_blocks))
        self.block_table: dict[str, list[int]] = {}
        self.lengths: dict[str, int] = {}
        self.refcounts = np.zeros(num_blocks, dtype=np.int64)

    def allocate(self, request_id: str) -> None:
        if request_id in self.block_table:
            raise KeyError(f"请求已存在：{request_id}")
        self.block_table[request_id] = []
        self.lengths[request_id] = 0

    def _take_blocks(self, count: int) -> list[int]:
        if count > len(self.free_blocks):
            raise MemoryError(f"物理块不足：需要 {count}，仅剩 {len(self.free_blocks)}")
        chosen = [self.free_blocks.pop(0) for _ in range(count)]
        for block in chosen:
            self.refcounts[block] = 1
        return chosen

    def append(self, request_id: str, n_tokens: int = 1) -> list[int]:
        if n_tokens < 0:
            raise ValueError("n_tokens 不能为负")
        if request_id not in self.block_table:
            self.allocate(request_id)
        old_length = self.lengths[request_id]
        new_length = old_length + n_tokens
        required = math.ceil(new_length / self.block_size) if new_length else 0
        needed = required - len(self.block_table[request_id])
        if needed > len(self.free_blocks):
            raise MemoryError(f"物理块不足：需要新增 {needed}，仅剩 {len(self.free_blocks)}")
        added = self._take_blocks(needed)
        self.block_table[request_id].extend(added)
        for position in range(old_length, new_length):
            logical = position // self.block_size
            offset = position % self.block_size
            physical = self.block_table[request_id][logical]
            self.blocks[physical, offset, 0] = position % 256
        self.lengths[request_id] = new_length
        return added

    def share_prefix(self, source_id: str, target_id: str, prefix_tokens: int) -> list[int]:
        if target_id in self.block_table:
            raise KeyError(f"目标请求已存在：{target_id}")
        if source_id not in self.block_table:
            raise KeyError(f"源请求不存在：{source_id}")
        if prefix_tokens < 0 or prefix_tokens > self.lengths[source_id]:
            raise ValueError("共享前缀长度越界")
        if prefix_tokens % self.block_size:
            raise ValueError("为避免写时复制歧义，共享前缀必须按完整 block 对齐")
        count = prefix_tokens // self.block_size
        shared = list(self.block_table[source_id][:count])
        for block in shared:
            self.refcounts[block] += 1
        self.block_table[target_id] = list(shared)
        self.lengths[target_id] = prefix_tokens
        return list(shared)

    def release(self, request_id: str) -> list[int]:
        if request_id not in self.block_table:
            raise KeyError(f"请求不存在：{request_id}")
        released: list[int] = []
        for block in self.block_table.pop(request_id):
            self.refcounts[block] -= 1
            if self.refcounts[block] == 0:
                self.blocks[block].fill(0)
                released.append(block)
                self.free_blocks.append(block)
        self.free_blocks.sort()
        self.lengths.pop(request_id)
        return released

    def preempt(self, protected: "set[str] | None" = None) -> tuple[str, list[int]]:
        candidates = [request for request in self.block_table if request not in (protected or set())]
        if not candidates:
            raise RuntimeError("没有可抢占请求")
        victim = max(candidates, key=lambda request: (len(self.block_table[request]), self.lengths[request], request))
        return victim, self.release(victim)

    def physical_block(self, request_id: str, token_position: int) -> tuple[int, int]:
        if request_id not in self.block_table or not 0 <= token_position < self.lengths[request_id]:
            raise IndexError("token 位置越界")
        logical, offset = divmod(token_position, self.block_size)
        return self.block_table[request_id][logical], offset

    def stats(self) -> dict:
        used_blocks = int(np.count_nonzero(self.refcounts))
        logical_refs = int(sum(len(table) for table in self.block_table.values()))
        logical_tokens = int(sum(self.lengths.values()))
        physical_fill: dict[int, int] = {}
        for request_id, table in self.block_table.items():
            length = self.lengths[request_id]
            for logical, block in enumerate(table):
                fill = min(self.block_size, max(0, length - logical * self.block_size))
                physical_fill[block] = max(physical_fill.get(block, 0), fill)
        used_tokens = sum(physical_fill.values())
        capacity_tokens = used_blocks * self.block_size
        return {
            "requests": len(self.block_table),
            "used_blocks": used_blocks,
            "free_blocks": len(self.free_blocks),
            "logical_block_refs": logical_refs,
            "shared_refs": logical_refs - used_blocks,
            "logical_tokens": logical_tokens,
            "used_tokens": used_tokens,
            "capacity_tokens": capacity_tokens,
            "allocated_bytes": capacity_tokens * self.token_bytes,
            "payload_bytes": used_tokens * self.token_bytes,
            "internal_waste_bytes": (capacity_tokens - used_tokens) * self.token_bytes,
            "internal_waste_rate": (capacity_tokens - used_tokens) / capacity_tokens if capacity_tokens else 0.0,
            "utilization": used_tokens / capacity_tokens if capacity_tokens else 0.0,
        }

    def check_invariants(self) -> bool:
        used = set(np.flatnonzero(self.refcounts).tolist())
        free = set(self.free_blocks)
        tables = {block for values in self.block_table.values() for block in values}
        return (
            not (used & free)
            and used | free == set(range(self.num_blocks))
            and used == tables
            and len(self.free_blocks) == len(free)
            and np.all(self.refcounts >= 0)
        )


def memory_comparison(
    lengths: list[int],
    max_seq_len: int,
    block_size: int,
    bytes_per_token: int,
) -> dict:
    if any(length < 0 or length > max_seq_len for length in lengths):
        raise ValueError("序列长度必须位于 [0, max_seq_len]")
    if not lengths:
        raise ValueError("lengths 不能为空")
    useful = sum(lengths) * bytes_per_token
    contiguous = len(lengths) * max_seq_len * bytes_per_token
    paged_tokens = sum(math.ceil(length / block_size) * block_size for length in lengths)
    paged = paged_tokens * bytes_per_token
    return {
        "useful_bytes": useful,
        "contiguous_bytes": contiguous,
        "paged_bytes": paged,
        "contiguous_waste_bytes": contiguous - useful,
        "paged_waste_bytes": paged - useful,
        "contiguous_waste_rate": (contiguous - useful) / contiguous if contiguous else 0.0,
        "paged_waste_rate": (paged - useful) / paged if paged else 0.0,
        "saved_bytes": contiguous - paged,
        "saved_rate": (contiguous - paged) / contiguous if contiguous else 0.0,
    }


__all__ = ["PagedKVCache", "memory_comparison"]
