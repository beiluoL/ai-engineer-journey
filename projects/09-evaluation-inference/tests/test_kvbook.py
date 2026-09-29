from __future__ import annotations

import pytest

from ie.kvbook import (
    KVArchitecture,
    bytes_per_token,
    kv_cache_bytes,
    memory_table,
    model_weight_bytes,
    qwen7b_reference,
    sequence_length_to_exceed_weights,
)


@pytest.mark.parametrize(
    "layers,heads,dim,dtype,expected",
    [(1, 1, 1, 1, 2), (2, 4, 16, 8, 2048), (28, 4, 128, 2, 57344), (32, 32, 128, 2, 524288), (12, 2, 64, 4, 12288)],
)
def test_bytes_per_token_formula(layers, heads, dim, dtype, expected):
    assert bytes_per_token(KVArchitecture(layers, heads, dim), dtype) == expected


@pytest.mark.parametrize("seq", [0, 1, 8, 128, 2048])
def test_kv_memory_linear_in_sequence(seq):
    arch = KVArchitecture(2, 4, 16)
    assert kv_cache_bytes(arch, seq, 3, 2) == bytes_per_token(arch, 2) * seq * 3


@pytest.mark.parametrize("batch", [1, 2, 4, 16])
def test_kv_memory_linear_in_batch(batch):
    arch = KVArchitecture(3, 2, 8)
    assert kv_cache_bytes(arch, 10, batch, 2) == kv_cache_bytes(arch, 10, 1, 2) * batch


def test_reference_matches_p07_numbers():
    result = qwen7b_reference()
    assert result["bytes_per_token"] == 57344
    assert result["weight_gib"] == 14.18


def test_threshold_is_first_exceeding_length():
    arch = KVArchitecture(1, 1, 1)
    threshold = sequence_length_to_exceed_weights(arch, weight_bytes=10, batch_size=1, dtype_bytes=1)
    assert threshold == 6
    assert kv_cache_bytes(arch, threshold - 1, 1, 1) <= 10
    assert kv_cache_bytes(arch, threshold, 1, 1) > 10


def test_memory_table_cartesian_product():
    rows = memory_table(KVArchitecture(2, 2, 4), [1, 2, 3], [1, 4])
    assert len(rows) == 6


def test_model_weight_bytes():
    assert model_weight_bytes(7_000_000_000, 2) == 14_000_000_000


@pytest.mark.parametrize("args", [(0, 1, 1), (1, 0, 1), (1, 1, 0)])
def test_invalid_architecture(args):
    with pytest.raises(ValueError):
        KVArchitecture(*args)
