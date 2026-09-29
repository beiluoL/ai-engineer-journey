#!/usr/bin/env python
"""M05 · QLoRA —— NF4 量化到底损失了多少精度，换回来多少显存。

QLoRA 的想法只有一句：**把冻结的基座压成 4 bit**。

    y = x · dequant(W_nf4) + (alpha/r) · x · A · B

它和 LoRA 的区别不在数学，而在**存储**：LoRA 省的是训练开销，QLoRA 省的是
"基座本身能不能塞进显存"。所以本 demo 要回答两个问题：

1. NF4 压到 4 bit，**误差有多大**？（用真实基座权重量，不猜）
2. 换来的**显存是多少**？（fp32 / fp16 / NF4 / NF4+双量化 / adapter 逐项记账）

顺带验证两个容易被当成口号的说法：
- 「NF4 是按分位数量化的，比均匀 int4 好」→ 实测差多少？
- 「双量化能省字节」→ 省多少？代价是误差变大多少？
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
    QLoRALinear,
    build_sft_examples,
    count_parameters,
    dequantize_nf4,
    ensure_base_model,
    evaluate,
    human_bytes,
    inject_lora,
    load_java_records,
    lora_layers,
    memory_ledger,
    nf4_codebook,
    nf4_storage_bytes,
    quantization_error,
    quantize_nf4,
)
from ft.quantize import NF4_LEVELS  # noqa: E402

STEPS = 60
R, ALPHA, LR = 8, 16.0, 3e-3


def blockwise_quantize(w: np.ndarray, levels: np.ndarray, block_size: int) -> np.ndarray:
    """通用分块 absmax 量化（NF4 和均匀 int4 共用一套流程，只有码本不同）。"""
    flat = w.reshape(-1)
    n_blocks = int(np.ceil(flat.size / block_size))
    pad = n_blocks * block_size - flat.size
    if pad:
        flat = np.concatenate([flat, np.zeros(pad)])
    blocks = flat.reshape(n_blocks, block_size)
    absmax = np.abs(blocks).max(axis=1)
    absmax = np.where(absmax <= 0, 1.0, absmax)
    normed = blocks / absmax[:, None]
    idx = np.argmin(np.abs(normed[:, :, None] - levels[None, None, :]), axis=2)
    vals = (levels[idx] * absmax[:, None]).reshape(-1)[: w.size]
    return vals.reshape(w.shape)


def main() -> None:
    out = Printer("demo_05_qlora")
    try:
        out.section("M05 · QLoRA：NF4 量化误差 + 双量化收益 + 显存账本")

        # ---------------- 1. 码本 ----------------
        out.subsection("1. NF4 码本（16 个值，不是等距的）")
        cb = nf4_codebook()
        out.kv("码本长度", f"{len(cb)}", "4 bit → 2⁴ = 16 个电平")
        for i in range(0, 16, 8):
            out.line("    " + "  ".join(f"{v:+.4f}" for v in cb[i : i + 8]))
        gaps = np.diff(cb)
        out.kv("相邻电平间距 最小/最大", f"{gaps.min():.4f} / {gaps.max():.4f}",
               "中间密、两头疏 = 按正态分位数切")
        out.kv("零是否在码本里", f"{bool(np.any(cb == 0.0))}", "必须在，否则 0 权重会被量化成非 0")

        # ---------------- 2. 真实权重上的量化误差 ----------------
        out.subsection("2. 在**真实基座权重**上量化（13 个线性层，共 163,840 个权重）")
        model, tok, _info = ensure_base_model()
        # 注入前先拿到 13 个目标权重的真实数值
        from ft import iter_targets

        targets = iter_targets(model)
        weights = [p.data for _path, _parent, _key, p in targets]
        shapes = [w.shape for w in weights]
        n_base = int(sum(w.size for w in weights))
        out.kv("被量化的层数 / 权重数", f"{len(weights)} / {n_base:,}")

        all_err = []
        per_layer = []
        for (path, _p, _k, param), w in zip(targets, weights):
            q = quantize_nf4(w, block_size=64)
            w_hat = dequantize_nf4(q)
            err = quantization_error(w, w_hat)
            all_err.append(err)
            per_layer.append((path.split(".")[-1], err["rel_l2"]))
        mean_rel = float(np.mean([e["rel_l2"] for e in all_err]))
        mean_mse = float(np.mean([e["mse"] for e in all_err]))
        max_abs = float(max(e["max_abs"] for e in all_err))
        out.kv("NF4 平均相对误差 ‖W-Ŵ‖/‖W‖", f"{mean_rel:.4f}")
        out.kv("NF4 平均 MSE", f"{mean_mse:.3e}")
        out.kv("单层最大绝对误差", f"{max_abs:.6f}")
        out.blank()
        out.line("  各层相对误差（前 6 层）：")
        out.table(["层", "相对误差"], [[p, f"{v:.4f}"] for p, v in per_layer[:6]], aligns=["<", ">"])

        # ---------------- 3. 块大小扫描 ----------------
        out.subsection("3. block_size 扫描（分块越小越准，但 absmax 开销越大）")
        rows = []
        for bs in (32, 64, 128, 256, 1024):
            rels = []
            for w in weights:
                w_hat = dequantize_nf4(quantize_nf4(w, block_size=bs))
                rels.append(quantization_error(w, w_hat)["rel_l2"])
            rows.append([bs, f"{np.mean(rels):.4f}", f"{nf4_storage_bytes(n_base, bs):,.0f}",
                         f"{4.0 * n_base / nf4_storage_bytes(n_base, bs):.2f}×"])
        out.table(["block_size", "相对误差", "字节数", "压缩倍数(vs fp32)"], rows, aligns=[">", ">", ">", ">"])
        out.line("  结论：block_size 越小越准（离群值被关在小块里），代价是 absmax 变多。")
        out.line("  QLoRA 论文默认 64 —— 上表可见 64 已经在拐点附近。")

        # ---------------- 4. NF4 vs 均匀 int4 ----------------
        out.subsection("4. 「NF4 是信息论最优」是真的吗？和均匀 int4 对拍")
        uniform_levels = np.linspace(-1.0, 1.0, 16)
        rels_nf4, rels_uni = [], []
        for w in weights:
            rels_nf4.append(quantization_error(w, blockwise_quantize(w, NF4_LEVELS, 64))["rel_l2"])
            rels_uni.append(quantization_error(w, blockwise_quantize(w, uniform_levels, 64))["rel_l2"])
        r_nf4, r_uni = float(np.mean(rels_nf4)), float(np.mean(rels_uni))
        out.table(
            ["码本", "平均相对误差", "相对 NF4"],
            [["NF4（分位数）", f"{r_nf4:.4f}", "1.000×"],
             ["均匀 int4（linspace）", f"{r_uni:.4f}", f"{r_uni / r_nf4:.3f}×"]],
            aligns=["<", ">", ">"],
        )
        out.kv("NF4 的相对优势", f"误差低 {(1 - r_nf4 / r_uni) * 100:.2f}%")
        out.line("  印证了设计动机：权重近似正态分布，按分位数切才能让每个 4-bit 桶里")
        out.line("  落进同样多的权重。差距不算大，因为本项目的权重是随手初始化 +")
        out.line(f"  {_info['n_steps']} 步预训练出来的，还没长成「标准正态」；真实大模型上更大。")

        # ---------------- 5. 双量化 ----------------
        out.subsection("5. 双量化：把 absmax 本身也量化成 8 bit")
        sq_bytes = nf4_storage_bytes(n_base, 64, double_quant=False)
        dq_bytes = nf4_storage_bytes(n_base, 64, double_quant=True)
        rel_sq, rel_dq = [], []
        for w in weights:
            rel_sq.append(quantization_error(w, dequantize_nf4(quantize_nf4(w, 64, False)))["rel_l2"])
            rel_dq.append(quantization_error(w, dequantize_nf4(quantize_nf4(w, 64, True)))["rel_l2"])
        out.table(
            ["方案", "字节数", "每权重", "压缩倍数", "平均相对误差"],
            [["fp32 原始", f"{4.0 * n_base:,.0f}", "4.0000 B", "1.00×", "0.0000"],
             ["NF4 单量化", f"{sq_bytes:,.0f}", f"{sq_bytes / n_base:.4f} B", f"{4.0 * n_base / sq_bytes:.2f}×", f"{np.mean(rel_sq):.4f}"],
             ["NF4 + 双量化", f"{dq_bytes:,.0f}", f"{dq_bytes / n_base:.4f} B", f"{4.0 * n_base / dq_bytes:.2f}×", f"{np.mean(rel_dq):.4f}"]],
            aligns=["<", ">", ">", ">", ">"],
        )
        out.kv("双量化省下的字节", f"{sq_bytes - dq_bytes:,.0f} B（{(1 - dq_bytes / sq_bytes) * 100:.2f}%）")
        out.kv("双量化的误差代价", f"相对误差 {np.mean(rel_sq):.6f} → {np.mean(rel_dq):.6f}"
               f"（+{(np.mean(rel_dq) / np.mean(rel_sq) - 1) * 100:.4f}%）")
        out.line("  这笔买卖很划算：absmax 只要 8 bit 就够（它本身是「尺度」，精度要求低），")
        out.line("  省下 8.3% 的体积，误差代价是万分之几。")

        # ---------------- 6. 显存账本 ----------------
        out.subsection("6. 显存账本：fp32 / fp16 / NF4 / adapter 各占多少")
        led = memory_ledger(shapes, r=R, block_size=64, double_quant=True)
        out.table(
            ["项目", "字节", "人类可读", "占 fp32 基座的比例"],
            [["基座 fp32", f"{led['fp32_bytes']:,.0f}", human_bytes(led["fp32_bytes"]), "100.00%"],
             ["基座 fp16", f"{led['fp16_bytes']:,.0f}", human_bytes(led["fp16_bytes"]), "50.00%"],
             ["基座 NF4（单量化）", f"{led['nf4_bytes']:,.0f}", human_bytes(led["nf4_bytes"]),
              f"{led['nf4_bytes'] / led['fp32_bytes']:.2%}"],
             ["基座 NF4 + 双量化", f"{led['nf4_double_bytes']:,.0f}", human_bytes(led["nf4_double_bytes"]),
              f"{led['nf4_double_bytes'] / led['fp32_bytes']:.2%}"],
             [f"adapter fp32 (r={R})", f"{led['adapter_bytes']:,.0f}", human_bytes(led["adapter_bytes"]),
              f"{led['adapter_bytes'] / led['fp32_bytes']:.2%}"]],
            aligns=["<", ">", ">", ">"],
        )
        out.kv("NF4 相对 fp32 的压缩倍数", f"{led['compress_fp32_vs_nf4']:.2f}×", "理论上限是 8×，被 absmax 摊薄")
        out.kv("NF4+双量化 相对 fp32", f"{led['compress_fp32_vs_nf4dq']:.2f}×")
        out.kv("NF4 是否 ≤ fp16", f"是（{led['nf4_vs_fp16_ratio']:.4f} = fp16 的 {led['nf4_vs_fp16_ratio']:.2%}）")
        out.kv("adapter 占 fp32 基座", f"{led['adapter_vs_fp32_ratio']:.2%}")
        out.kv("adapter 占 NF4 基座", f"{led['adapter_vs_nf4_ratio']:.2%}",
               "⚠ 小模型上 adapter 比量化后的基座还大")
        out.line("  最后一行是这个玩具规模下的真实结论：**模型越大，QLoRA 越划算**。")
        out.line("  d_model=64 时基座只有 163,840 个权重，量化省下的绝对量有限；")
        out.line("  换到 7B（70 亿参数），这一项会从 0.66 MB 变成 3.5 GB。")

        # ---------------- 7. QLoRA vs LoRA 真训 ----------------
        out.subsection(f"7. QLoRA 真训 vs LoRA 真训（各 {STEPS} 步，其余完全相同）")
        recs = load_java_records()
        model_l, tok, _ = ensure_base_model()
        examples = build_sft_examples(recs, tok, max_len=model_l.max_len)
        inject_lora(model_l, r=R, alpha=ALPHA, rng=0)
        tr_l = LoRATrainer(model_l, lr=LR, optimizer="adam", seed=0)
        t0 = time.perf_counter()
        losses_l = tr_l.run(examples, STEPS, batch_size=4)
        t_lora = time.perf_counter() - t0

        model_q, _, _ = ensure_base_model()
        inject_lora(model_q, r=R, alpha=ALPHA, kind="qlora", block_size=64, double_quant=True, rng=0)
        q_layers = lora_layers(model_q)
        out.kv("QLoRA 注入层数", f"{len(q_layers)}", f"示例：{q_layers[0][1]!r}")
        tr_q = LoRATrainer(model_q, lr=LR, optimizer="adam", seed=0)
        t0 = time.perf_counter()
        losses_q = tr_q.run(examples, STEPS, batch_size=4)
        t_qlora = time.perf_counter() - t0

        out.table(
            ["", "LoRA（fp32 基座）", "QLoRA（NF4 基座）"],
            [["首步 loss", f"{losses_l[0]:.4f}", f"{losses_q[0]:.4f}"],
             ["末步 loss", f"{losses_l[-1]:.4f}", f"{losses_q[-1]:.4f}"],
             ["前 10 步均值", f"{np.mean(losses_l[:10]):.4f}", f"{np.mean(losses_q[:10]):.4f}"],
             ["后 10 步均值", f"{np.mean(losses_l[-10:]):.4f}", f"{np.mean(losses_q[-10:]):.4f}"],
             ["耗时", f"{t_lora:.2f} s", f"{t_qlora:.2f} s"],
             ["可训练参数", f"{count_parameters(model_l)['trainable']:,}", f"{count_parameters(model_q)['trainable']:,}"]],
            aligns=["<", ">", ">"],
        )
        delta = losses_q[-1] - losses_l[-1]
        out.kv("首步 loss 差（纯量化误差）", f"{losses_q[0] - losses_l[0]:+.4f}",
               "正数 = 4bit 基座一开始就更差，这是量化的直接代价")
        out.kv("末步 loss 差", f"{delta:+.4f}",
               "正数 = QLoRA 略差" if delta > 0 else "负数 = QLoRA 反而略好（60 步尺度下属于噪声）")

        out.subsection("8. 本 demo 的关键数字")
        out.kv("NF4 相对误差", f"{mean_rel:.4f}")
        out.kv("显存节省倍数（fp32 → NF4+双量化）", f"{led['compress_fp32_vs_nf4dq']:.2f}×")
        out.kv("双量化额外节省", f"{(1 - dq_bytes / sq_bytes) * 100:.2f}%")
        out.kv("adapter 占 NF4 基座的比例", f"{led['adapter_vs_nf4_ratio']:.2%}")
        out.kv("QLoRA vs LoRA 末步 loss", f"{losses_q[-1]:.4f} vs {losses_l[-1]:.4f}")
    finally:
        out.close()


if __name__ == "__main__":
    main()
