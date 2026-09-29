from __future__ import annotations

import pytest

from ie.batching import Request, compare_batching, simulate_continuous, simulate_static


def make_requests(tokens):
    return [Request(str(i), 0.0, token) for i, token in enumerate(tokens)]


@pytest.mark.parametrize(
    "tokens",
    [[1], [1, 2], [1, 4, 2], [2, 8, 3, 7], [1, 10, 2, 9, 3], [3, 3, 3, 3, 3, 3]],
)
def test_all_requests_complete(tokens):
    requests = make_requests(tokens)
    assert simulate_static(requests, 4, 1.0)["completed"] == len(tokens)
    assert simulate_continuous(requests, 4, 1.0)["completed"] == len(tokens)


@pytest.mark.parametrize(
    "tokens",
    [[1, 10, 1, 10, 1, 10], [2, 8, 3, 7, 4, 6], [1, 20, 1, 20, 1, 20], [5, 6, 7, 8, 1, 2, 3, 4]],
)
def test_continuous_throughput_at_least_static(tokens):
    result = compare_batching(make_requests(tokens), batch_size=3, step_ms=0.5)
    assert result["continuous"]["throughput_rps"] >= result["static"]["throughput_rps"]


def test_continuous_reduces_idle_slots_for_varied_lengths():
    result = compare_batching(make_requests([1, 12, 2, 11, 3, 10, 4, 9]), 4, 1.0)
    assert result["continuous"]["compute_idle_rate"] < result["static"]["compute_idle_rate"]


def test_arrival_time_is_included_in_latency():
    requests = [Request("a", 0, 3), Request("b", 10, 1)]
    result = simulate_continuous(requests, 1, 2.0)
    assert result["completion_ms"]["a"] == 6.0
    assert result["completion_ms"]["b"] == 12.0


def test_simulation_is_deterministic():
    requests = [Request("a", 0, 3), Request("b", 1, 4), Request("c", 2, 2)]
    assert simulate_continuous(requests, 2, 0.25) == simulate_continuous(requests, 2, 0.25)


@pytest.mark.parametrize("arrival,tokens", [(-1, 1), (0, 0), (0, -1)])
def test_bad_request_rejected(arrival, tokens):
    with pytest.raises(ValueError):
        Request("bad", arrival, tokens)
