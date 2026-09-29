"""静态批处理与连续批处理的离散事件仿真。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Request:
    request_id: str
    arrival_ms: float
    tokens: int

    def __post_init__(self) -> None:
        if self.arrival_ms < 0 or self.tokens <= 0:
            raise ValueError("arrival_ms 必须非负，tokens 必须为正")


def _report(requests: list[Request], completion: dict[str, float], start: float, end: float, busy_slots: int, capacity_slots: int) -> dict:
    latencies = np.asarray([completion[r.request_id] - r.arrival_ms for r in requests], dtype=np.float64)
    duration = max(end - start, np.finfo(float).eps)
    return {
        "completed": len(completion),
        "total_requests": len(requests),
        "duration_ms": float(duration),
        "throughput_rps": float(len(requests) / duration * 1000.0),
        "mean_latency_ms": float(latencies.mean()),
        "p95_latency_ms": float(np.percentile(latencies, 95)),
        "max_latency_ms": float(latencies.max()),
        "compute_idle_rate": 1.0 - busy_slots / capacity_slots if capacity_slots else 0.0,
        "busy_slots": busy_slots,
        "capacity_slots": capacity_slots,
        "completion_ms": completion,
    }


def simulate_static(requests: list[Request], batch_size: int, step_ms: float) -> dict:
    if not requests or batch_size <= 0 or step_ms <= 0:
        raise ValueError("请求不能为空，batch_size/step_ms 必须为正")
    ordered = sorted(requests, key=lambda req: (req.arrival_ms, req.request_id))
    completion: dict[str, float] = {}
    now = ordered[0].arrival_ms
    busy_slots = 0
    capacity_slots = 0
    for offset in range(0, len(ordered), batch_size):
        batch = ordered[offset : offset + batch_size]
        start = max(now, max(req.arrival_ms for req in batch))
        batch_steps = max(req.tokens for req in batch)
        for req in batch:
            completion[req.request_id] = start + req.tokens * step_ms
            busy_slots += req.tokens
        capacity_slots += batch_steps * batch_size
        now = start + batch_steps * step_ms
    return _report(ordered, completion, ordered[0].arrival_ms, now, busy_slots, capacity_slots)


def simulate_continuous(requests: list[Request], batch_size: int, step_ms: float) -> dict:
    if not requests or batch_size <= 0 or step_ms <= 0:
        raise ValueError("请求不能为空，batch_size/step_ms 必须为正")
    pending = sorted(requests, key=lambda req: (req.arrival_ms, req.request_id))
    active: list[list] = []
    completion: dict[str, float] = {}
    now = pending[0].arrival_ms
    busy_slots = 0
    capacity_slots = 0
    while pending or active:
        if not active and pending and pending[0].arrival_ms > now:
            now = pending[0].arrival_ms
        while pending and pending[0].arrival_ms <= now and len(active) < batch_size:
            req = pending.pop(0)
            active.append([req, req.tokens])
        if not active:
            continue
        busy_slots += len(active)
        capacity_slots += batch_size
        finish_time = now + step_ms
        survivors: list[list] = []
        for req, remaining in active:
            remaining -= 1
            if remaining == 0:
                completion[req.request_id] = finish_time
            else:
                survivors.append([req, remaining])
        active = survivors
        now = finish_time
    ordered = sorted(requests, key=lambda req: (req.arrival_ms, req.request_id))
    return _report(ordered, completion, ordered[0].arrival_ms, now, busy_slots, capacity_slots)


def compare_batching(requests: list[Request], batch_size: int, step_ms: float) -> dict:
    static = simulate_static(requests, batch_size, step_ms)
    continuous = simulate_continuous(requests, batch_size, step_ms)
    return {
        "step_ms": float(step_ms),
        "static": static,
        "continuous": continuous,
        "throughput_gain": continuous["throughput_rps"] / static["throughput_rps"],
        "latency_reduction": 1.0 - continuous["mean_latency_ms"] / static["mean_latency_ms"],
        "p95_reduction": 1.0 - continuous["p95_latency_ms"] / static["p95_latency_ms"],
        "idle_reduction": static["compute_idle_rate"] - continuous["compute_idle_rate"],
    }


__all__ = ["Request", "compare_batching", "simulate_continuous", "simulate_static"]
