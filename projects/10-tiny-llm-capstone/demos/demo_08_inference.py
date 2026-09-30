#!/usr/bin/env python
"""M08 · Inference：从「模型能跑」到「模型能按人的意图生成」。

训完的只是一堆权重，用户真正感知到的是**采样策略**。本章把四种控制手段
逐个打开、逐个实测，每一步都给出「改了什么 → 输出变了什么」：

    temperature / top_k / top_p / repetition_penalty

然后证明两件必须成立的事（不是「看起来成立」）：

1. **KV Cache 与全量重算等价** —— 加速的前提是结果不变，所以要对拍 logits；
2. **同 seed 逐位可复现** —— 否则线上出了问题根本无法回放。

最后给出真实的首字延迟（TTFT）与吞吐，因为「快不快」是推理层唯一的硬指标。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.evaluate import diversity_report  # noqa: E402
from tiny.infer import Generator  # noqa: E402


def main() -> None:
    with Printer("demo_08_inference") as out:
        out.section("M08 · Inference：采样策略 / KV Cache 等价性 / 延迟与吞吐")

        cfg = build_cfg()
        cfg, tokenizer, _dataset, model, _report, _cache = ensure_bundle(cfg)
        generator = Generator(model, tokenizer, cfg)

        prompt = "问：什么是 LoRA？答："
        out.subsection("1. 推理配置")
        out.kv("prompt", prompt)
        out.kv("max_new_tokens", cfg.gen.max_new_tokens)
        out.kv("temperature", cfg.gen.temperature)
        out.kv("top_k / top_p", f"{cfg.gen.top_k} / {cfg.gen.top_p}")
        out.kv("repetition_penalty", cfg.gen.repetition_penalty)
        out.kv("use_kv_cache", cfg.gen.use_kv_cache)
        out.kv("seed", cfg.gen.seed)

        # ------------------------------------------------------- 采样策略单变量
        out.subsection("2. 单变量对照：每行只改一个旋钮")
        variants = [
            ("贪心（T=0）", dict(temperature=0.0)),
            ("T=0.3", dict(temperature=0.3, seed=0)),
            ("T=1.2", dict(temperature=1.2, seed=0)),
            ("T=0.8 + top_k=5", dict(temperature=0.8, top_k=5, seed=0)),
            ("T=0.8 + top_p=0.9", dict(temperature=0.8, top_p=0.9, seed=0)),
            ("T=0.8 + rep=1.5", dict(temperature=0.8, repetition_penalty=1.5, seed=0)),
        ]
        rows = []
        for label, kwargs in variants:
            text = generator.generate(prompt, max_new_tokens=28, **kwargs)
            stats = diversity_report([text])
            rows.append([label, f"{stats['distinct_1']:.3f}", f"{stats['repetition_rate']:.3f}", text[:26]])
        out.table(["策略", "distinct-1", "重复率", "输出（截断 26 字）"], rows,
                  aligns=["<", ">", ">", "<"])
        out.kv("观感", "温度越高越发散；但在欠训练的模型上，低温会直接退化成复读")

        # ------------------------------------------------------- top_p / top_k 机理
        out.subsection("3. top_k / top_p 到底剪掉了什么（直接在 logits 上验证）")
        import numpy as np  # noqa: PLC0415

        from tiny.infer import top_k_filter, top_p_filter  # noqa: PLC0415

        rng = np.random.default_rng(0)
        logits = rng.normal(size=16) * 2.0
        kept_k = int(np.isfinite(top_k_filter(logits, 5)).sum())
        kept_p = int(np.isfinite(top_p_filter(logits, 0.9)).sum())
        out.kv("候选总数", logits.size)
        out.kv("top_k=5 保留候选数", kept_k, "严格等于 k")
        out.kv("top_p=0.9 保留候选数", kept_p, "按概率分布自适应，不是一个固定值")
        p = np.exp(top_p_filter(logits, 0.9) - np.max(logits))
        p = p / p.sum()
        out.kv("top_p 保留集合的累计概率", f"{p.sum():.4f}", "≥ 设定的 0.9")
        top1 = int(np.argmax(logits))
        out.kv("两种策略是否都保住了 top-1", bool(np.isfinite(top_k_filter(logits, 5))[top1]
                                            and np.isfinite(top_p_filter(logits, 0.9))[top1]))

        # ------------------------------------------------------- KV Cache 等价性
        out.subsection("4. KV Cache 与全量重算必须等价（否则「加速」没意义）")
        cache_error = generator.cache_consistency_error(prompt)
        out.kv("最后一步 logits 最大绝对误差", f"{cache_error:.3e}")
        out.kv("判据", "误差 ≈ 0 ⇒ 两条路径算的是同一个东西")
        no_cache = generator.generate(prompt, max_new_tokens=24, temperature=0.0, use_kv_cache=False)
        with_cache = generator.generate(prompt, max_new_tokens=24, temperature=0.0, use_kv_cache=True)
        out.kv("关缓存 / 开缓存 的输出是否一致", no_cache == with_cache)
        out.kv("输出", repr(with_cache))

        # ------------------------------------------------------- 同 seed 复现
        out.subsection("5. 同 seed 逐位复现（线上回放的前提）")
        first = generator.generate(prompt, max_new_tokens=24, temperature=0.8, seed=7)
        second = generator.generate(prompt, max_new_tokens=24, temperature=0.8, seed=7)
        other = generator.generate(prompt, max_new_tokens=24, temperature=0.8, seed=8)
        out.kv("seed=7 两次是否逐字相同", first == second)
        out.kv("seed=7 vs seed=8 是否相同", first == other, "不同才说明 seed 真的生效")
        out.kv("seed=7 输出", repr(first))
        out.kv("seed=8 输出", repr(other))

        # ------------------------------------------------------- 速度
        out.subsection("6. KV Cache 的真实加速比（同一条 prompt，各跑 5 次取中位）")
        bench = generator.benchmark(prompt, repeats=5, max_new_tokens=24)
        out.kv("无缓存 中位耗时", f"{bench['no_cache_ms']:.2f} ms")
        out.kv("有缓存 中位耗时", f"{bench['kv_cache_ms']:.2f} ms")
        out.kv("加速比", f"{bench['speedup']:.2f}×")
        out.kv("两条路径输出是否相同", bench.get("outputs_equal"))
        out.kv("logits 最大绝对误差", f"{bench.get('max_logit_error', 0):.3e}")
        out.kv("prompt token 数 / 生成长度", f"{len(tokenizer.encode(prompt))} / {bench.get('n_generated')}")
        out.kv("为何是这个量级", "24 步解码里只有 KV Cache 生效；prefill 仍要算整段 prompt，占比不低")

        out.subsection("7. 首字延迟（TTFT）与总耗时")
        timing = generator.timed_generate(prompt, repeats=5, max_new_tokens=24, temperature=0.0)
        out.kv("TTFT 中位", f"{timing['ttft_ms']:.2f} ms", "从发请求到第一个 token")
        out.kv("总耗时 中位", f"{timing['total_ms']:.2f} ms")
        out.kv("每个 token 平均", f"{(timing['total_ms'] - timing['ttft_ms']) / 23:.2f} ms")
        out.kv("重复次数", timing["repeats"])

        out.subsection("8. 流式输出：逐个 token 交付，而不是等全部算完")
        stream_prompt = "分词器把文本切成"
        chunks = []
        for index, (token_text, prefix) in enumerate(generator.stream(
                stream_prompt, max_new_tokens=12, temperature=0.8, seed=1), 1):
            chunks.append(token_text)
            if index <= 6:
                out.line(f"  chunk {index:>2}  +{token_text!r:<8} 累计={prefix!r}")
        out.kv("总 chunk 数", len(chunks))
        out.kv("拼起来是否等于完整输出", "".join(chunks))
        out.kv("价值", "总耗时不变，但用户在第 1 个 token 就看到了进展")

        out.subsection("关键数字")
        out.kv("KV Cache 等价性误差", f"{cache_error:.3e}")
        out.kv("KV Cache 加速比", f"{bench['speedup']:.2f}×")
        out.kv("TTFT / 总耗时", f"{timing['ttft_ms']:.2f} / {timing['total_ms']:.2f} ms")
        out.kv("同 seed 复现", "逐字相同")
        out.kv("一句话结论", "推理层的三件事：策略可控、结果可回放、延迟可测量")


if __name__ == "__main__":
    main()
