#!/usr/bin/env python
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import base_bundle  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.batching import Request, compare_batching  # noqa: E402
from ie.engine import CausalLMWithKVCache  # noqa: E402


def main() -> None:
    with Printer("demo_09_batching") as out:
        out.section("M09 · Batching：Static vs Continuous")
        model, tokenizer, _info, _split, _train, _eval = base_bundle()
        engine = CausalLMWithKVCache(model)
        prompt_ids = tokenizer.encode("请解释 Java 并发机制以及线程安全的核心原则。")[:64]
        last, state = engine.prefill(np.asarray([prompt_ids], dtype=np.int64))
        token = np.array([int(np.argmax(last[0]))])
        for _ in range(10):
            engine.decode_step(token, state)
        trials = []
        for _ in range(101):
            started = time.perf_counter()
            engine.decode_step(token, state)
            trials.append((time.perf_counter() - started) * 1000.0)
        step_ms = float(np.median(trials))
        token_counts = [3, 14, 6, 20, 5, 11, 2, 17, 8, 4, 13, 7]
        arrivals = [0, 0, 0, 0, 2, 4, 7, 10, 12, 15, 18, 21]
        requests = [
            Request(f"r{index:02d}", arrival * step_ms, tokens)
            for index, (arrival, tokens) in enumerate(zip(arrivals, token_counts))
        ]
        result = compare_batching(requests, batch_size=4, step_ms=step_ms)
        out.kv("真实单 token 解码中位耗时", f"{step_ms:.4f} ms", "101 次实测")
        out.kv("仿真请求数", len(requests))
        out.kv("Batch size", 4)
        out.subsection("调度结果")
        out.table(
            ["策略", "吞吐 req/s", "平均延迟 ms", "p95 ms", "计算空闲率", "完成数"],
            [["Static", f"{result['static']['throughput_rps']:.2f}",
              f"{result['static']['mean_latency_ms']:.2f}", f"{result['static']['p95_latency_ms']:.2f}",
              f"{result['static']['compute_idle_rate']:.1%}", result['static']['completed']],
             ["Continuous", f"{result['continuous']['throughput_rps']:.2f}",
              f"{result['continuous']['mean_latency_ms']:.2f}", f"{result['continuous']['p95_latency_ms']:.2f}",
              f"{result['continuous']['compute_idle_rate']:.1%}", result['continuous']['completed']]],
            aligns=["<", ">", ">", ">", ">", ">"],
        )
        out.subsection("关键结论")
        out.kv("吞吐提升", f"{result['throughput_gain']:.2f}×")
        out.kv("平均延迟下降", f"{result['latency_reduction']:.1%}")
        out.kv("p95 下降", f"{result['p95_reduction']:.1%}")
        out.kv("计算空闲率下降", f"{result['idle_reduction']:.1%}")
        out.line("  仿真只替换调度策略；每个 decode step 的时间来自本机真实引擎计时。")


if __name__ == "__main__":
    main()
