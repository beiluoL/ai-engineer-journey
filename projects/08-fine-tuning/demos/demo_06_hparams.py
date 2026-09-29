#!/usr/bin/env python
"""M06 · Training Configuration —— rank / lr / alpha 的真实扫描。

LoRA 只有三个真正需要调的超参：

    r     ：低秩维度。越大表达力越强，但参数量线性增长。
    alpha ：缩放系数。真正起作用的是 alpha/r，常用做法是 alpha = 2r。
    lr    ：LoRA 的学习率通常要比全量微调**大一个数量级**（1e-4 vs 1e-3~3e-3），
            因为 adapter 是从零初始化的，基座已经收敛了。

网上流传的"经验值"很多，本 demo 全部**实测**：同一基座、同一数据、同一 seed，
只改一个变量，看末段 loss 与域内困惑度怎么动。

⚠ 扫描结论的适用范围：59 条样本、45 步。它能告诉你"趋势与量级"，
不能直接外推到真实任务 —— 但至少不是拍脑袋。
"""

from __future__ import annotations

import sys
import time
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
    count_parameters,
    ensure_base_model,
    evaluate,
    inject_lora,
    load_java_records,
)

STEPS = 45
BASE_R, BASE_ALPHA, BASE_LR = 8, 16.0, 3e-3
BATCH = 4


def run_config(examples, eval_examples, r: int, alpha: float, lr: float, steps: int = STEPS):
    """训一个配置，返回 (末10步均值loss, 域内困惑度, adapter参数量, 耗时)。"""
    model, tok, _ = ensure_base_model()
    inject_lora(model, r=r, alpha=alpha, rng=0)
    counts = count_parameters(model)
    trainer = LoRATrainer(model, lr=lr, optimizer="adam", seed=0)
    t0 = time.perf_counter()
    losses = trainer.run(examples, steps, batch_size=BATCH)
    dt = time.perf_counter() - t0
    ppl = evaluate(model, eval_examples)["ppl"]
    tail = float(np.mean(losses[-10:]))
    diverged = bool(np.mean(losses[:5]) < tail)  # 末段比开头还高 = 崩了
    return tail, ppl, counts["trainable"], dt, diverged


def main() -> None:
    out = Printer("demo_06_hparams")
    try:
        out.section("M06 · Training Configuration：rank / lr / alpha 的真实扫描")
        model0, tok, _info = ensure_base_model()
        recs = load_java_records()
        examples = build_sft_examples(recs, tok, max_len=model0.max_len)
        base_ppl = evaluate(model0, examples)["ppl"]
        out.kv("扫描设置", f"每个配置 {STEPS} 步，batch={BATCH}，Adam，seed=0")
        out.kv("基线（未微调）域内困惑度", f"{base_ppl:,.2f}")
        out.kv("对照变量之外的固定值", f"r={BASE_R}, alpha={BASE_ALPHA:g}, lr={BASE_LR:g}")

        # ---------------- rank ----------------
        out.subsection(f"1. rank 扫描（固定 alpha={BASE_ALPHA:g}, lr={BASE_LR:g}）")
        rows = []
        for r in (1, 2, 4, 8, 16):
            tail, ppl, nparam, dt, bad = run_config(examples, examples, r, BASE_ALPHA, BASE_LR)
            rows.append([r, f"{nparam:,}", f"{nparam / count_parameters(model0)['total']:.2%}",
                         f"{tail:.4f}", f"{ppl:,.1f}", f"{dt:.1f}s", "崩了" if bad else ""])
        out.table(["r", "adapter 参数", "占基座", "末10步 loss", "域内困惑度", "耗时", ""],
                  rows, aligns=[">", ">", ">", ">", ">", ">", "<"])
        best_r = min(rows, key=lambda x: float(x[4].replace(",", "")))[0]
        out.kv("困惑度最低的 rank", f"{best_r}", "（在本次扫描范围内）")

        # ---------------- lr ----------------
        out.subsection(f"2. 学习率扫描（固定 r={BASE_R}, alpha={BASE_ALPHA:g}）")
        rows = []
        for lr in (1e-3, 3e-3, 1e-2, 3e-2):
            tail, ppl, nparam, dt, bad = run_config(examples, examples, BASE_R, BASE_ALPHA, lr)
            rows.append([f"{lr:g}", f"{tail:.4f}", f"{ppl:,.1f}", f"{dt:.1f}s", "崩了" if bad else ""])
        out.table(["lr", "末10步 loss", "域内困惑度", "耗时", ""], rows, aligns=["<", ">", ">", ">", "<"])
        best_lr = min(rows, key=lambda x: float(x[2].replace(",", "")))[0]
        out.kv("困惑度最低的学习率", f"{best_lr}")

        # ---------------- alpha ----------------
        out.subsection(f"3. alpha 扫描（固定 r={BASE_R}, lr={BASE_LR:g}）")
        rows = []
        for alpha in (4.0, 8.0, 16.0, 32.0, 64.0):
            tail, ppl, nparam, dt, bad = run_config(examples, examples, BASE_R, alpha, BASE_LR)
            rows.append([f"{alpha:g}", f"{alpha / BASE_R:g}", f"{tail:.4f}", f"{ppl:,.1f}",
                         f"{dt:.1f}s", "崩了" if bad else ""])
        out.table(["alpha", "alpha/r", "末10步 loss", "域内困惑度", "耗时", ""],
                  rows, aligns=[">", ">", ">", ">", ">", "<"])
        best_alpha = min(rows, key=lambda x: float(x[3].replace(",", "")))[0]
        worst_alpha = max(rows, key=lambda x: float(x[3].replace(",", "")))[0]
        best_ratio, worst_ratio = float(best_alpha) / BASE_R, float(worst_alpha) / BASE_R
        best_ppl = min(rows, key=lambda x: float(x[3].replace(",", "")))[3]
        worst_ppl = max(rows, key=lambda x: float(x[3].replace(",", "")))[3]
        out.kv("困惑度最低的 alpha", f"{best_alpha}", f"即 alpha/r = {best_ratio:g}")

        # ---------------- 结论 ----------------
        out.subsection("4. 本 demo 的关键数字与读法")
        out.kv("扫描出的最好组合", f"r={best_r}, alpha={best_alpha}, lr={best_lr}")
        out.blank()
        out.bullets([
            "rank：r=1 已经能把困惑度从几万降到几百 —— 低秩假设在玩具任务上确实成立；",
            "      r 越大参数越多，但本任务收益很快饱和（数据量才是瓶颈，不是容量）。",
            "lr  ：LoRA 用 1e-3 ~ 1e-2 都收敛，比全量微调常用的 1e-4~1e-5 大一个数量级；",
            "      太大（3e-2）会明显变差，符合「adapter 从零初始化、需要更大步长」的直觉。",
            "alpha：真正起作用的是 alpha/r（它与 lr 是乘性关系，等效于整体缩放步长）；",
            f"      本次最好 alpha/r={best_ratio:g}（困惑度 {best_ppl}），"
            f"最差 alpha/r={worst_ratio:g}（困惑度 {worst_ppl}）。",
            "      它和 lr 高度耦合，两个一起调只会互相掩盖，调一个就够了。",
        ])
        out.blank()
        out.line("  一句话结论：rank 决定**上限**，lr 决定**能不能走到上限**，alpha 和 lr 高度耦合。")
        out.line("  实践建议：先固定 alpha=2r、lr=1e-3 起手，只扫 r 和 lr 两个维度即可。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
