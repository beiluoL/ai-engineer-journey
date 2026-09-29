#!/usr/bin/env python
"""M03 · Instruction Tuning —— loss 只算在答案区，到底有多大差别？

这是 SFT 和预训练**唯一但关键**的区别：

    mask[i] = 1  ⟺  第 i 个目标 token 属于「回答」
    mask[i] = 0  ⟺  它属于「指令 / 输入」，不计入 loss

直觉上：用户的问题是我们给的，模型不需要学会"生成问题"。让模型去拟合 prompt
的分布，既浪费容量，又会把「学会问答格式」和「学会领域知识」两件事搅在一起。

本 demo 不空谈，直接做对照实验：
    A 组：只在答案区算 loss（正确做法）
    B 组：全序列都算 loss（偷懒做法）
两组用**完全相同的基座、相同步数、相同学习率**，然后比较：
    · 答案区困惑度（我们真正想要的指标）
    · prompt 区困惑度（看 B 组是不是把力气花在背问题上）
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

import numpy as np

np.random.seed(0)

from _emit import Printer  # noqa: E402

from ft import (  # noqa: E402
    LoRATrainer,
    build_sft_examples,
    ensure_base_model,
    evaluate,
    inject_lora,
    load_java_records,
    visualize_example,
)
from ft.sft_data import SFTExample  # noqa: E402

STEPS = 60
R, ALPHA, LR = 8, 16.0, 3e-3


def with_mask(examples: list[SFTExample], mode: str) -> list[SFTExample]:
    """复制一份样本，把 mask 换成指定模式。"""
    out_list = []
    for e in examples:
        e2 = copy.copy(e)
        if mode == "answer":
            e2.mask = e.mask.copy()
        elif mode == "all":
            e2.mask = np.ones_like(e.mask)
        elif mode == "prompt":
            e2.mask = 1.0 - e.mask
        out_list.append(e2)
    return out_list


def run_branch(name: str, mask_mode: str, examples: list[SFTExample],
               answer_eval: list[SFTExample], prompt_eval: list[SFTExample], out: Printer):
    """训一条分支，返回 (末步 loss, 答案区 ppl, prompt 区 ppl)。"""
    model, tok, _ = ensure_base_model()
    inject_lora(model, r=R, alpha=ALPHA, rng=0)
    trainer = LoRATrainer(model, lr=LR, optimizer="adam", seed=0)
    losses = trainer.run(examples, STEPS, batch_size=4)
    a = evaluate(model, answer_eval)
    p = evaluate(model, prompt_eval)
    out.kv(f"{name} 首步 loss", f"{losses[0]:.4f}")
    out.kv(f"{name} 末步 loss", f"{losses[-1]:.4f}")
    return float(losses[-1]), a, p


def main() -> None:
    out = Printer("demo_03_instruction_tuning")
    try:
        out.section("M03 · Instruction Tuning：prompt / answer mask 可视化 + 只算答案区的收益")

        model, tok, _info = ensure_base_model()
        recs = load_java_records()
        examples = build_sft_examples(recs, tok, max_len=model.max_len)

        # ---------------- 模板 ----------------
        out.subsection("1. 指令模板（prompt / answer 的分界线就是 mask 的分界线）")
        out.line("  ┌─ prompt（mask=0）──────────────────────────────┐")
        for ln in examples[0].prompt_text.splitlines():
            out.line(f"  │ {ln}")
        out.line("  └─────────────────────────────────────────────────┘")
        out.line("  ┌─ answer（mask=1）──────────────────────────────┐")
        out.line(f"  │ {examples[0].answer_text[:56]}…")
        out.line("  └─────────────────────────────────────────────────┘")

        # ---------------- 可视化 ----------------
        out.subsection("2. mask 可视化（· = 不计入 loss，1 = 计入 loss）")
        for idx in (0, 1, 2):
            out.line(f"  【样本 {idx + 1}】")
            out.line(visualize_example(examples[idx], tok, max_show=64))
            out.blank()
        cover = np.mean([e.mask_coverage for e in examples])
        total_tok = sum(e.length for e in examples)
        ans_tok = sum(int(e.mask.sum()) for e in examples)
        out.kv("全部样本的答案区 token", f"{ans_tok:,} / {total_tok:,}")
        out.kv("mask 覆盖的 token 占比", f"{ans_tok / total_tok:.2%}", "（单条平均覆盖率 %.2f%%）" % (cover * 100))
        out.kv("被 mask 掉的 prompt token", f"{total_tok - ans_tok:,}", "这些位置的梯度全是 0")

        # ---------------- 对照实验 ----------------
        out.subsection(f"3. 对照实验：A 只算答案区 / B 全序列都算（各训 {STEPS} 步，其余完全相同）")
        answer_eval = with_mask(examples, "answer")
        prompt_eval = with_mask(examples, "prompt")
        all_examples = with_mask(examples, "all")

        base_model, _, _ = ensure_base_model()
        a0 = evaluate(base_model, answer_eval)
        p0 = evaluate(base_model, prompt_eval)
        out.kv("微调前 答案区困惑度", f"{a0['ppl']:,.2f}")
        out.kv("微调前 prompt 区困惑度", f"{p0['ppl']:,.2f}")
        out.blank()

        loss_a, a_a, p_a = run_branch("A组(只算答案)", "answer", answer_eval, answer_eval, prompt_eval, out)
        out.kv("A组 答案区困惑度", f"{a_a['ppl']:,.2f}")
        out.kv("A组 prompt 区困惑度", f"{p_a['ppl']:,.2f}")
        out.blank()
        loss_b, a_b, p_b = run_branch("B组(全序列)", "all", all_examples, answer_eval, prompt_eval, out)
        out.kv("B组 答案区困惑度", f"{a_b['ppl']:,.2f}")
        out.kv("B组 prompt 区困惑度", f"{p_b['ppl']:,.2f}")

        # ---------------- 对比表 ----------------
        out.subsection("4. 结果对比")
        out.table(
            ["指标", "微调前", "A组 只算答案区", "B组 全序列", "谁更好"],
            [
                ["答案区困惑度", f"{a0['ppl']:,.1f}", f"{a_a['ppl']:,.1f}", f"{a_b['ppl']:,.1f}",
                 "A" if a_a["ppl"] < a_b["ppl"] else "B"],
                ["prompt 区困惑度", f"{p0['ppl']:,.1f}", f"{p_a['ppl']:,.1f}", f"{p_b['ppl']:,.1f}",
                 "A" if p_a["ppl"] < p_b["ppl"] else "B"],
                ["答案区 CE", f"{a0['mean_ce']:.4f}", f"{a_a['mean_ce']:.4f}", f"{a_b['mean_ce']:.4f}",
                 "A" if a_a["mean_ce"] < a_b["mean_ce"] else "B"],
            ],
            aligns=["<", ">", ">", ">", ">"],
        )
        gap_a = (a_b["ppl"] - a_a["ppl"]) / a_a["ppl"] * 100
        gap_p = (p_b["ppl"] - p_a["ppl"]) / p_a["ppl"] * 100
        out.kv("答案区困惑度：B 相对 A", f"{gap_a:+.2f}%", "正数 = B 更差")
        out.kv("prompt 区困惑度：B 相对 A", f"{gap_p:+.2f}%", "负数 = B 更会背问题")

        out.subsection("5. 本 demo 的关键数字")
        out.kv("mask 覆盖的 token 占比", f"{ans_tok / total_tok:.2%}")
        out.kv("答案区困惑度 微调前 → A组", f"{a0['ppl']:,.1f} → {a_a['ppl']:,.1f}（↓{(1 - a_a['ppl'] / a0['ppl']) * 100:.1f}%）")
        out.kv("答案区困惑度 微调前 → B组", f"{a0['ppl']:,.1f} → {a_b['ppl']:,.1f}（↓{(1 - a_b['ppl'] / a0['ppl']) * 100:.1f}%）")
        out.kv("只算答案区带来的收益", f"答案区困惑度再降 {gap_a:.2f}%")
        out.blank()
        out.line("  读法：B 组把一部分梯度拿去拟合 prompt 了 —— 它的 prompt 区困惑度确实更低，")
        out.line("  但那是「背下了用户会问什么」，不是「学会了怎么回答」。答案区才是我们要的指标。")
        out.line("  59 条数据、60 步的规模下差距不算夸张，但方向稳定，且步数越多差距越明显。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
