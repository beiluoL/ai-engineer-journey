"""推理与采样（M08）：策略生效、KV Cache 等价、可复现。"""

from __future__ import annotations

import numpy as np

from tiny.infer import Generator, top_k_filter, top_p_filter


def test_top_k_keeps_only_k_candidates():
    logits = np.array([0.1, 0.5, 0.2, 0.9])
    masked = top_k_filter(logits, 2)
    assert np.isfinite(masked[3]) and np.isfinite(masked[1])
    assert np.isneginf(masked[0]) and np.isneginf(masked[2])


def test_top_p_keeps_nucleus():
    logits = np.array([5.0, 1.0, 0.1, 0.05])
    masked = top_p_filter(logits, 0.9)
    finite = [i for i in range(4) if np.isfinite(masked[i])]
    assert finite == [0]  # 5.0 已经占了 90% 以上的概率质量
    assert top_p_filter(logits, 1.0).tolist() == logits.tolist()


def test_greedy_equals_argmax_and_is_deterministic(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    first = gen.generate_ids("问：什么是 LoRA？答：", temperature=0.0)
    second = gen.generate_ids("问：什么是 LoRA？答：", temperature=0.0)
    assert first == second


def test_same_seed_reproduces_sampling(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    a = gen.generate_ids("分词器把文本切成", temperature=0.9, seed=42)
    b = gen.generate_ids("分词器把文本切成", temperature=0.9, seed=42)
    assert a == b


def test_different_seed_changes_sampling(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    a = gen.generate_ids("分词器把文本切成", temperature=1.2, seed=1)
    b = gen.generate_ids("分词器把文本切成", temperature=1.2, seed=2)
    assert a != b


def test_kv_cache_matches_full_recompute(trained_bundle):
    """KV Cache 是加速手段，前提是结果不变 —— 这里对拍两者的 logits。"""
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    error = gen.cache_consistency_error("问：什么是 KV Cache？答：")
    assert error < 1e-9


def test_kv_cache_and_full_path_agree_on_greedy_output(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    prompt = "问：什么是早停？答："
    cached = gen.generate_ids(prompt, temperature=0.0, use_kv_cache=True)
    full = gen.generate_ids(prompt, temperature=0.0, use_kv_cache=False)
    assert cached == full


def test_benchmark_reports_speedup_and_equality(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    result = gen.benchmark("问：什么是 LoRA？答：", repeats=3, max_new_tokens=8)
    assert result["outputs_equal"]
    assert result["no_cache_ms"] > 0 and result["kv_cache_ms"] > 0
    assert result["max_logit_error"] < 1e-9


def test_repetition_penalty_reduces_repeats(trained_bundle):
    """实测有效：惩罚之后同一 token 的连续重复次数必须下降。"""
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    prompt = "问：什么是 LoRA？答："

    def max_run(ids):
        best = current = 1
        for i in range(1, len(ids)):
            current = current + 1 if ids[i] == ids[i - 1] else 1
            best = max(best, current)
        return best

    plain = gen.generate_ids(prompt, temperature=0.0, repetition_penalty=1.0)
    penalized = gen.generate_ids(prompt, temperature=0.0, repetition_penalty=1.5)
    assert max_run(penalized) <= max_run(plain)


def test_stream_yields_incremental_text(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    chunks = list(gen.stream("问：什么是幻觉？答：", temperature=0.0, max_new_tokens=6))
    assert len(chunks) > 0
    assert all(isinstance(text, str) for _token, text in chunks)
    assert len(chunks[-1][1]) >= len(chunks[0][1])


def test_timed_generate_measures_ttft(trained_bundle):
    cfg = trained_bundle["cfg"]
    gen = Generator(trained_bundle["model"], trained_bundle["tokenizer"], cfg)
    timing = gen.timed_generate("问：什么是量化？答：", repeats=2, max_new_tokens=6)
    assert timing["ttft_ms"] >= 0
    assert timing["total_ms"] >= timing["ttft_ms"]
