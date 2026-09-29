from __future__ import annotations

import math

import pytest

from ie.paged import PagedKVCache, memory_comparison


@pytest.mark.parametrize("tokens", [0, 1, 7, 8, 9, 15, 16, 31, 32])
def test_blocks_are_allocated_by_ceiling(tokens):
    cache = PagedKVCache(16, block_size=8)
    cache.append("r", tokens)
    expected = math.ceil(tokens / 8) if tokens else 0
    assert len(cache.block_table["r"]) == expected
    assert cache.check_invariants()


def test_logical_to_physical_mapping():
    cache = PagedKVCache(4, block_size=4)
    cache.append("r", 6)
    assert cache.physical_block("r", 0) == (0, 0)
    assert cache.physical_block("r", 5) == (1, 1)


def test_release_restores_pool():
    cache = PagedKVCache(8, block_size=4)
    cache.append("r", 10)
    released = cache.release("r")
    assert len(released) == 3
    assert len(cache.free_blocks) == 8
    assert cache.check_invariants()


def test_shared_prefix_reuses_physical_block():
    cache = PagedKVCache(8, block_size=4)
    cache.append("a", 8)
    shared = cache.share_prefix("a", "b", 4)
    assert shared == [cache.block_table["a"][0]]
    assert cache.refcounts[shared[0]] == 2
    assert cache.stats()["shared_refs"] == 1


def test_shared_block_freed_after_last_reference():
    cache = PagedKVCache(8, block_size=4)
    cache.append("a", 8)
    block = cache.share_prefix("a", "b", 4)[0]
    cache.release("a")
    assert block not in cache.free_blocks
    cache.release("b")
    assert block in cache.free_blocks


def test_unaligned_share_rejected():
    cache = PagedKVCache(8, block_size=4)
    cache.append("a", 8)
    with pytest.raises(ValueError):
        cache.share_prefix("a", "b", 3)


def test_overflow_is_atomic():
    cache = PagedKVCache(2, block_size=4)
    cache.append("r", 4)
    with pytest.raises(MemoryError):
        cache.append("r", 8)
    assert cache.lengths["r"] == 4
    assert len(cache.block_table["r"]) == 1


def test_preemption_reclaims_largest_request():
    cache = PagedKVCache(10, block_size=4)
    cache.append("small", 3)
    cache.append("large", 9)
    victim, blocks = cache.preempt()
    assert victim == "large"
    assert len(blocks) == 3
    assert cache.check_invariants()


@pytest.mark.parametrize(
    "lengths,max_len,block,expected_contiguous,expected_paged",
    [
        ([1], 8, 4, 8, 4),
        ([4], 8, 4, 8, 4),
        ([5], 8, 4, 8, 8),
        ([1, 7], 8, 4, 16, 12),
        ([8, 8], 8, 4, 16, 16),
    ],
)
def test_memory_comparison(lengths, max_len, block, expected_contiguous, expected_paged):
    result = memory_comparison(lengths, max_len, block, bytes_per_token=1)
    assert result["contiguous_bytes"] == expected_contiguous
    assert result["paged_bytes"] == expected_paged
    assert result["paged_waste_rate"] <= result["contiguous_waste_rate"] + 1e-12


def test_long_sequence_over_max_rejected():
    with pytest.raises(ValueError):
        memory_comparison([9], max_seq_len=8, block_size=4, bytes_per_token=1)
