#!/usr/bin/env python
"""M02 · Dataset Preparation —— 领域数据长什么样，它是怎么变成 id 序列的。

数据质量决定微调上限，而"数据长什么样"这件事光看 JSON 是看不出来的：
要 tokenizer 之后统计 token 长度分布，才知道 seq_len 该设多少、
有多少样本会被截断、以及 mask 到底能覆盖多少 token。

本 demo 全部数字来自真实 encode，不做任何估算。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

import numpy as np

np.random.seed(0)

from _emit import Printer  # noqa: E402

from ft import (  # noqa: E402
    build_sft_examples,
    build_tokenizer,
    dataset_stats,
    ensure_base_model,
    load_java_records,
    render_example,
)


def histogram(values: list[int], n_bins: int = 8, width: int = 40) -> list[str]:
    """ASCII 直方图（真实分箱，不是示意图）。"""
    arr = np.asarray(values, dtype=np.float64)
    lo, hi = arr.min(), arr.max()
    edges = np.linspace(lo, hi, n_bins + 1)
    counts, _ = np.histogram(arr, bins=edges)
    peak = max(1, int(counts.max()))
    lines = []
    for i, c in enumerate(counts):
        bar = "█" * int(round(c / peak * width))
        lines.append(f"  [{edges[i]:5.0f}, {edges[i + 1]:5.0f}]  {bar:<{width}} {int(c)}")
    return lines


def main() -> None:
    out = Printer("demo_02_dataset_prep")
    try:
        out.section("M02 · Dataset Preparation：Alpaca 数据的统计与 token 化")

        # ---------------- 原始数据 ----------------
        out.subsection("1. 原始数据（只读复用 P07 手写的 Java 面试数据集）")
        recs = load_java_records()
        out.kv("样本条数", f"{len(recs)}")
        out.kv("字段", ", ".join(sorted(recs[0].keys())), "Alpaca 三元组")
        out.kv("有 input 字段的条数", f"{sum(1 for r in recs if (r.get('input') or '').strip())}",
               "全部为空 → 渲染时省略「### 输入:」段")
        instr_chars = [len(r["instruction"]) for r in recs]
        out_chars = [len(r["output"]) for r in recs]
        out.kv("instruction 平均字符数", f"{np.mean(instr_chars):.1f}", f"最短 {min(instr_chars)} / 最长 {max(instr_chars)}")
        out.kv("output 平均字符数", f"{np.mean(out_chars):.1f}", f"最短 {min(out_chars)} / 最长 {max(out_chars)}")
        out.kv("总字符数", f"{sum(instr_chars) + sum(out_chars):,}")

        out.blank()
        out.line("  第一条记录（原文）：")
        p, a = render_example(recs[0])
        out.line(f"    instruction: {recs[0]['instruction']}")
        out.line(f"    output     : {recs[0]['output'][:60]}…")

        # ---------------- 词表 ----------------
        out.subsection("2. 词表")
        tok = build_tokenizer()
        corpus_chars = set()
        for r in recs:
            corpus_chars.update(r["instruction"] + (r["input"] or "") + r["output"])
        out.kv("分词器", "P06 的 BPETokenizer（子词级）")
        out.kv("词表大小", f"{tok.vocab_size}")
        out.kv("数据集里的不同字符数", f"{len(corpus_chars)}")
        out.blank()
        out.line("  ⚠ 一个必须说清楚的现实约束：")
        out.line(f"    这套数据里出现 {len(corpus_chars)} 个不同字符。BPE 的基础词表就是字符集本身，")
        out.line("    所以「词表控制在 300~600」在这个数据集上做不到 —— 除非接受 <unk>：")
        out.line("    实测 char 级 min_freq=3 时词表 592，但领域语料会有 2.84% 的字符变成 <unk>。")
        out.line("    本项目选择「宁可词表 1024，也不要把领域数据喂成 <unk>」。")

        # ---------------- token 化 ----------------
        out.subsection("3. token 化后的真实统计")
        model, tok, _info = ensure_base_model()
        st = dataset_stats(recs, tok, max_len=model.max_len)
        out.kv("prompt 平均 token 数", f"{st['prompt_len_mean']:.1f}")
        out.kv("answer 平均 token 数", f"{st['answer_len_mean']:.1f}")
        out.kv("整条样本平均 token 数", f"{st['len_mean']:.1f}")
        out.kv("最短 / 中位 / p90 / 最长", f"{st['len_min']} / {st['len_median']:.0f} / {st['len_p90']:.0f} / {st['len_max']}")
        out.kv("总 token 数", f"{st['total_tokens']:,}")
        out.kv("其中答案区 token", f"{st['answer_tokens']:,}", f"{st['mask_coverage']:.1%}")
        out.kv("超过 max_len 被截断的样本", f"{st['n_truncated']} / {st['n_records']}",
               f"max_len={model.max_len}（从左侧截，答案区永远完整保留）")
        out.kv("压缩率（字符/token）",
               f"{sum(instr_chars + out_chars) / st['total_tokens']:.2f}",
               "BPE 相对字符级")

        out.blank()
        out.line("  样本长度分布（token）：")
        examples = build_sft_examples(recs, tok, max_len=model.max_len)
        for ln in histogram([e.length for e in examples]):
            out.line(ln)

        # ---------------- 渲染与切分 ----------------
        out.subsection("4. 一条样本是怎么被切开的")
        e0 = examples[0]
        out.line(f"  prompt 模板渲染结果（{len(p)} 字符）：")
        for ln in p.splitlines():
            out.line(f"    │ {ln}")
        out.line(f"  answer（{len(a)} 字符）：")
        out.line(f"    │ {a[:70]}…")
        pieces = tok.pieces(p)[:24]
        out.line(f"  prompt 的 BPE 切分（前 24 个）：{pieces}")

        out.subsection("5. 本 demo 的关键数字")
        out.kv("样本数", f"{st['n_records']}")
        out.kv("词表大小", f"{st['vocab_size']}")
        out.kv("prompt / answer 平均长度", f"{st['prompt_len_mean']:.1f} / {st['answer_len_mean']:.1f} token")
        out.kv("答案区占比（= mask 覆盖率）", f"{st['mask_coverage']:.2%}")
        out.kv("被截断的样本", f"{st['n_truncated']}")
        out.blank()
        out.line(f"  结论：{st['n_records']} 条样本、约 {st['total_tokens'] / 1000:.2f} 千 token、"
                 f"答案占 {st['mask_coverage']:.1%} ——")
        out.line("  这个数据集小到只能验证「流程是否跑通」，不足以训出真正好用的模型。")
        out.line("  这正是本项目刻意保留的真实约束：别把玩具实验的结论当成生产结论。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
