#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import base_bundle  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.engine import CausalLMWithKVCache  # noqa: E402


def main() -> None:
    with Printer("demo_07_inference_engine") as out:
        out.section("M07 · Inference Engine：真实 KV Cache")
        model, tokenizer, _info, split, _train, _eval = base_bundle()
        prompt = split.heldout[0]["instruction"] + "。请分点解释底层机制和适用场景。"
        prompt_ids = tokenizer.encode(prompt)[:96]
        engine = CausalLMWithKVCache(model)
        result = engine.benchmark(prompt_ids, max_new_tokens=16, repeats=7)
        out.kv("Prompt tokens", len(prompt_ids))
        out.kv("生成 tokens", result["n_generated"])
        out.kv("无 KV Cache 中位耗时", f"{result['no_cache_ms']:.3f} ms")
        out.kv("有 KV Cache 中位耗时", f"{result['kv_cache_ms']:.3f} ms")
        out.kv("真实加速比", f"{result['speedup']:.2f}×")
        out.kv("生成 token 完全一致", result["outputs_equal"])
        out.kv("单步 logits 最大误差", f"{result['max_logit_error']:.3e}", "要求 < 1e-8")
        out.subsection("7 轮原始计时")
        out.table(
            ["轮次", "无缓存 ms", "有缓存 ms", "单轮加速"],
            [[index + 1, f"{plain:.3f}", f"{cached:.3f}", f"{plain / cached:.2f}×"]
             for index, (plain, cached) in enumerate(zip(result["no_cache_trials_ms"], result["kv_cache_trials_ms"]))],
            aligns=[">", ">", ">", ">"],
        )
        out.subsection("结论")
        if result["speedup"] > 1:
            out.line("  KV Cache 在该 prompt 上测得真实加速；生成越长，避免的历史 token 重算越多。")
        else:
            out.line("  该玩具规模没有测得加速：缓存拼接与 Python 调度开销盖过了省下的矩阵计算。")


if __name__ == "__main__":
    main()
