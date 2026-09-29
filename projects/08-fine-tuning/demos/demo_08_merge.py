#!/usr/bin/env python
"""M08 · Merge / Load Adapter —— 合并回基座，还是只加载 adapter？

LoRA 有个常被忽略的性质：**它是可以"融化"回基座的**。

    W' = W + (alpha/r) · B @ A

因为 LoRA 分支是纯线性运算，完全可以把它加回 W，得到一个形状、结构、推理速度
完全不变的普通模型。于是部署有两个选项：

    ┌─ 合并（merge）  ：推理零额外开销，但每个任务一份完整权重，切任务要重新加载模型
    └─ 加载（load）   ：一个基座常驻，切任务只换几百 KB 的 adapter
                        代价：每次前向多两次小矩阵乘（x@A@B）

本 demo 用数值证明二者**完全等价**（最大绝对误差应 ~1e-15 量级），再用真实计时
给出两者的推理耗时差，最后展示"不合并、只加载 adapter"的标准用法。
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
    human_bytes,
    inject_lora,
    load_adapter,
    load_java_records,
    lora_layers,
    lora_overhead_report,
    max_abs_diff,
    merge_lora,
    save_adapter,
    time_forward,
    unmerge_lora,
)
from ft.paths import P08_MODELS  # noqa: E402

STEPS = 40
R, ALPHA, LR = 8, 16.0, 3e-3
ADAPTER = P08_MODELS / "adapters" / "demo08_adapter.npz"


def main() -> None:
    out = Printer("demo_08_merge")
    try:
        out.section("M08 · Merge / Load Adapter：合并等价性证明 + 两种部署方式的代价")

        model, tok, _info = ensure_base_model()
        recs = load_java_records()
        examples = build_sft_examples(recs, tok, max_len=model.max_len)

        # ---------------- 1. 训练一个 adapter ----------------
        out.subsection(f"1. 先训出一个 adapter（{STEPS} 步，r={R}）")
        inject_lora(model, r=R, alpha=ALPHA, rng=0)
        counts = count_parameters(model)
        trainer = LoRATrainer(model, lr=LR, optimizer="adam", seed=0)
        losses = trainer.run(examples, STEPS, batch_size=4)
        out.kv("训练 loss", f"{losses[0]:.4f} → {losses[-1]:.4f}")
        out.kv("注入后参数量", f"基座 {counts['base']:,} + adapter {counts['trainable']:,}"
               f" = {counts['total']:,}")
        n_layers = len(lora_layers(model))
        out.kv("LoRA 层数", f"{n_layers}")

        # ---------------- 2. 等价性证明 ----------------
        out.subsection("2. 数值证明：合并后 == 分离状态（同一输入，逐位对比）")
        probe = [
            np.random.randint(4, tok.vocab_size, (2, 32)),
            np.random.randint(4, tok.vocab_size, (4, 64)),
            np.random.randint(4, tok.vocab_size, (1, 128)),
        ]
        outs_before = [model(x, mask=None).data.copy() for x in probe]
        # 顺便记录 adapter 的 ΔW 规模，看它到底改了多少
        deltas = [np.abs(l.delta_weight()) for _p, l in lora_layers(model)]
        norms_w = [np.abs(l.W.data) for _p, l in lora_layers(model)]
        rel_delta = float(np.mean([d.mean() / (w.mean() + 1e-12) for d, w in zip(deltas, norms_w)]))

        backup = merge_lora(model)
        outs_after = [model(x, mask=None).data.copy() for x in probe]
        diffs = [max_abs_diff(a, b) for a, b in zip(outs_before, outs_after)]
        out.table(
            ["探针输入", "输出元素数", "合并前 vs 合并后 最大绝对误差"],
            [[f"shape {tuple(x.shape)}", f"{np.prod(outs_before[i].shape):,}", f"{diffs[i]:.3e}"]
             for i, x in enumerate(probe)],
            aligns=["<", ">", ">"],
        )
        out.kv("三个探针的最大绝对误差", f"{max(diffs):.3e}", "≈ 机器精度（float64 的 eps 是 2.2e-16）")
        out.kv("合并后 LoRA 层数", f"{len(lora_layers(model))}", "已全部变成普通线性层")
        out.kv("合并后参数量", f"{count_parameters(model)['total']:,}",
               f"比分离状态少 {counts['total'] - count_parameters(model)['total']:,}（A/B 消失）")
        out.kv("ΔW 的平均幅度 / W 的平均幅度", f"{rel_delta:.4%}", "adapter 确实只改了基座的一小部分")

        # ---------------- 3. 合并 vs 不合并 的推理耗时 ----------------
        out.subsection("3. 推理耗时对比（真实计时：分离 / 合并**交替**各测 7 轮，取中位数）")
        probe_x = probe[1]
        unmerge_lora(model, backup)   # 上一节把模型合并了，先还原回分离状态

        def bench_once(x, n: int = 10) -> float:
            for _ in range(3):
                model(x, mask=None)
            t = time.perf_counter()
            for _ in range(n):
                model(x, mask=None)
            return (time.perf_counter() - t) / n * 1000.0

        split_ms, merged_ms = [], []
        for _trial in range(7):
            split_ms.append(bench_once(probe_x))       # 分离状态
            backup = merge_lora(model)
            merged_ms.append(bench_once(probe_x))      # 合并状态
            unmerge_lora(model, backup)                # 还原回分离状态
        med_split = float(np.median(split_ms))
        med_merged = float(np.median(merged_ms))
        gap = (med_split - med_merged) / med_split * 100
        out.kv("分离状态（基座 + LoRA 分支）", f"{med_split:.3f} ms/次",
               f"7 轮: {[round(v, 2) for v in split_ms]}")
        out.kv("合并后（单一 W'）", f"{med_merged:.3f} ms/次",
               f"7 轮: {[round(v, 2) for v in merged_ms]}")
        out.kv("合并节省的推理时间（中位数）", f"{gap:.2f}%",
               f"绝对差 {med_split - med_merged:+.3f} ms/次")
        noise = (np.std(split_ms) / np.mean(split_ms)) * 100
        out.kv("同一状态的轮间波动（标准差）", f"{noise:.1f}%", "用来判断上面的差是不是真的")
        rep = lora_overhead_report(model, batch_size=probe_x.shape[0], seq_len=probe_x.shape[1])
        out.kv("LoRA 分支理论额外 MACs 占比", f"{rep['overhead_ratio']:.2%}")
        out.blank()
        if abs(gap) < noise:
            out.line(f"  ⚠ 实测差异（{gap:+.1f}%）小于轮间噪声（±{noise:.1f}%）—— **测不出来**。")
            out.line("  这不是实验失败，而是这个规模下的真实结论：d_model=64、seq=64 的前向")
            out.line("  耗时被 Python 层构建计算图的对象开销主导（每步几百个小 Tensor 分配），")
            out.line(f"  真正的矩阵乘占比很小，所以理论上的 {rep['overhead_ratio']:.1%} 额外 MACs 淹没了。")
            out.line("  换到 7B 模型（d_model=4096，matmul 主导）才会在计时上看到这笔开销。")
        else:
            out.line(f"  实测合并快 {gap:.1f}%，与理论 {rep['overhead_ratio']:.1%} 同量级。")

        # ---------------- 4. 不合并、只加载 adapter ----------------
        out.subsection("4. 另一种部署：不合并，只加载 adapter")
        save_adapter(model, ADAPTER, trainer=None, include_optimizer=False)
        size = ADAPTER.stat().st_size
        out.kv("adapter 文件", f"{human_bytes(size)}", "只有 A / B")
        fresh, _, _ = ensure_base_model()          # 干净的基座
        inject_lora(fresh, r=R, alpha=ALPHA, rng=0)  # 结构上先注入（B=0，输出=基座）
        before_load = fresh(probe_x, mask=None).data.copy()
        meta = load_adapter(fresh, ADAPTER)
        after_load = fresh(probe_x, mask=None).data
        out.kv("加载前后输出是否变化", f"{not np.allclose(before_load, after_load)}",
               "变了 = adapter 真的被装进去了")
        out.kv("加载后与「训练完的分离状态」是否一致",
               f"最大绝对误差 = {max_abs_diff(after_load, outs_before[1]):.3e}")
        out.kv("加载的层数", f"{len(meta['layers'])}")

        out.subsection("5. 两种方式的取舍")
        out.table(
            ["", "合并（merge）", "只加载 adapter（load）"],
            [["推理速度", "与基座完全相同", f"理论 +{rep['overhead_ratio']:.1%} MACs（实测 {gap:+.1f}%，见上）"],
             ["磁盘 / 显存", f"每任务一份 {human_bytes(4 * counts['base'])}", f"每任务 {human_bytes(size)}"],
             ["切任务", "重新加载整个模型", "换一个 adapter 文件（毫秒级）"],
             ["多任务同时服务", "每任务一份完整副本", "一份基座 + N 个 adapter 共享"],
             ["适合场景", "单任务、极致延迟", "多任务、频繁切换、显存紧张"]],
            aligns=["<", "<", "<"],
        )

        out.subsection("6. 本 demo 的关键数字")
        out.kv("合并前后最大绝对误差", f"{max(diffs):.3e}")
        out.kv("合并前后推理耗时（中位数）", f"{med_split:.3f} ms → {med_merged:.3f} ms（{gap:+.2f}%）")
        out.kv("LoRA 分支理论额外开销", f"{rep['overhead_ratio']:.2%}")
        out.kv("adapter 文件体积", f"{human_bytes(size)}", f"vs 合并后完整模型 {human_bytes(4 * counts['base'])}")
        out.blank()
        out.line("  一句话：合并换**推理速度**，不合并换**部署灵活性**。")
        out.line("  生产里常见做法是「开发时不合并（方便换任务）+ 上线前合并（省延迟）」，")
        out.line("  而 merge 能成立的前提，正是本 demo 第一节证明的那个等式。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
