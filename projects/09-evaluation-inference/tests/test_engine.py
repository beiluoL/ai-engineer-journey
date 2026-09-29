from __future__ import annotations

import numpy as np
import pytest

from ie.engine import CausalLMWithKVCache


@pytest.mark.parametrize("length", [2, 5, 16, 32, 64])
def test_cache_logits_match_full_forward(tiny_model, length):
    engine = CausalLMWithKVCache(tiny_model)
    ids = (np.arange(length) % 60 + 4).tolist()
    assert engine.cache_consistency_error(ids) < 1e-8


@pytest.mark.parametrize("new_tokens", [1, 2, 4, 8])
def test_cached_and_uncached_generation_match(tiny_model, new_tokens):
    engine = CausalLMWithKVCache(tiny_model)
    prompt = list(range(4, 24))
    plain = engine.generate_ids(prompt, new_tokens, use_kv_cache=False, stop_id=None)
    cached = engine.generate_ids(prompt, new_tokens, use_kv_cache=True, stop_id=None)
    assert plain == cached


def test_numpy_forward_matches_p06(tiny_model):
    engine = CausalLMWithKVCache(tiny_model)
    ids = np.array([[4, 7, 9, 11, 3]])
    expected = tiny_model(ids, mask=None).data
    actual = engine.forward(ids)
    assert np.max(np.abs(expected - actual)) < 1e-10


def test_prefill_cache_shape(tiny_model):
    engine = CausalLMWithKVCache(tiny_model)
    last, state = engine.prefill(np.array([[1, 2, 3, 4]]))
    assert last.shape == (1, 64)
    assert state.length == 4
    assert len(state.keys) == tiny_model.n_layers
    assert state.keys[0].shape == (1, tiny_model.n_heads, 4, 4)


def test_decode_increments_length(tiny_model):
    engine = CausalLMWithKVCache(tiny_model)
    _last, state = engine.prefill(np.array([[1, 2, 3]]))
    _next, updated = engine.decode_step(np.array([4]), state)
    assert updated.length == 4
    assert state.length == 3


def test_cache_is_faster_for_long_prompt(tiny_model):
    engine = CausalLMWithKVCache(tiny_model)
    prompt = (np.arange(96) % 60 + 4).tolist()
    result = engine.benchmark(prompt, max_new_tokens=8, repeats=7)
    assert result["outputs_equal"]
    assert result["kv_cache_ms"] < result["no_cache_ms"]


def test_empty_prompt_rejected(tiny_model):
    with pytest.raises(ValueError):
        CausalLMWithKVCache(tiny_model).generate_ids([], 1)


def test_context_overflow_rejected(tiny_model):
    with pytest.raises(ValueError):
        CausalLMWithKVCache(tiny_model).generate_ids([1] * 127, 2)


def test_bad_forward_rank_rejected(tiny_model):
    with pytest.raises(ValueError):
        CausalLMWithKVCache(tiny_model).forward(np.ones((1, 2, 3), dtype=np.int64))
