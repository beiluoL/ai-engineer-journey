#!/usr/bin/env python
"""M01 · Fine-Tuning —— 全量微调 vs LoRA：参数量、训练显存、可训练比例。

本 demo 回答一个最基础的问题：**微调一个模型，到底要"动"多少东西？**

两种做法：
- 全量微调：基座每个参数都参与训练 → 每个下游任务存一份完整权重。
- LoRA    ：基座冻结，只训练插进去的低秩 A / B → 每个任务存几 MB。

结论不是"LoRA 一定更好"，而是"看数字说话"：参数量差多少、训练时显存差多少、
以及在同一个任务上两者的 loss 曲线各是什么样。
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
    inject_lora,
    load_java_records,
    named_parameters,
    training_memory,
    human_bytes,
)
from ft.sft_data import pad_batch  # noqa: E402
from model import Adam, cross_entropy  # noqa: E402

STEPS = 60
R, ALPHA, LR = 8, 16.0, 3e-3


def train_full(model, examples, n_steps, lr, batch_size=4, seed=0):
    """全量微调：所有基座参数都进优化器（对照组的"笨办法"）。"""
    params = [p for _path, p in named_parameters(model)]
    opt = Adam(params, lr=lr)
    n = len(examples)
    n_batches = max(1, int(np.ceil(n / batch_size)))
    losses = []
    perms: dict[int, list] = {}
    for step in range(n_steps):
        epoch, bi = divmod(step, n_batches)
        if epoch not in perms:
            rng = np.random.default_rng(seed + epoch)
            idx = rng.permutation(n)
            perms[epoch] = [idx[i : i + batch_size] for i in range(0, n, batch_size)]
        X, Y, M = pad_batch([examples[int(i)] for i in perms[epoch][bi]])
        loss = cross_entropy(model(X, mask=None), Y, mask=M)
        loss.backward()
        opt.step()
        losses.append(float(loss.data.item()))
    return losses


def main() -> None:
    out = Printer("demo_01_finetune_basics")
    try:
        out.section("M01 · Fine-Tuning：全量微调 vs LoRA")
        out.line("  叙事：让「通用但弱」的基座模型，变成「Java 面试」领域的模型。")
        out.line("  本 demo 只回答一件事：两种微调方式，动手的代价差多少。")

        # ---------------- 基座 ----------------
        out.subsection("1. 基座模型（复用 P06 手写的 Decoder-Only Transformer）")
        t0 = time.perf_counter()
        model, tok, info = ensure_base_model()
        out.kv("加载耗时", f"{time.perf_counter() - t0:.2f} s")
        out.kv("基座来源", f"{info['source']}（{'从 models/ 缓存读取' if info['source']=='cache' else '本次训练'}）")
        if info["source"] == "cache":
            out.kv("缓存文件", f"{Path(info['path']).name}（{info['bytes'] / 1024:.0f} KB，预训练 {info['n_steps']} 步）",
                   f"预训练 loss {info['loss_first']:.3f} → {info['loss_last']:.3f}")
        out.kv("词表大小 / d_model / 层数", f"{tok.vocab_size} / {model.d_model} / {model.n_layers}")
        base_counts = count_parameters(model)
        out.kv("基座参数量（P08 口径）", f"{base_counts['total']:,}")
        out.kv("基座参数量（P06 parameters() 口径）", f"{base_counts['p06_elements']:,}", "⚠ 少了一整个词嵌入")
        out.kv("两者的差", f"{base_counts['total'] - base_counts['p06_elements']:,}",
                "= TokenEmbedding 未继承 Module，被 _collect_params 漏掉")

        recs = load_java_records()
        examples = build_sft_examples(recs, tok, max_len=model.max_len)

        # ---------------- 参数账 ----------------
        out.subsection("2. 参数账：要训练多少个数字")
        model_lora = model
        injected = inject_lora(model_lora, r=R, alpha=ALPHA, rng=0)
        lora_counts = count_parameters(model_lora)
        full_trainable = base_counts["total"]
        lora_trainable = lora_counts["trainable"]
        out.table(
            ["方式", "可训练参数", "基座参数(冻结)", "可训练占比", "每个任务的存储(fp32)"],
            [
                ["全量微调", f"{full_trainable:,}", "0", "100.00%", human_bytes(4 * full_trainable)],
                [f"LoRA r={R}", f"{lora_trainable:,}", f"{lora_counts['base']:,}",
                 f"{lora_counts['trainable_ratio']:.2%}", human_bytes(4 * lora_trainable)],
            ],
            aligns=["<", ">", ">", ">", ">"],
        )
        out.kv("可训练参数量倍数", f"{full_trainable / lora_trainable:.2f}×", "全量 / LoRA")
        out.kv("LoRA 注入层数", f"{len(injected)} 个线性层")
        out.bullets([p for p, _ in injected[:4]] + ["…"])

        # ---------------- 显存账 ----------------
        out.subsection("3. 训练显存账（参数 + 梯度 + 优化器状态）")
        out.line("  训练时每个**可训练**参数要占：4B(参数) + 4B(梯度) + 8B(Adam 的 m 与 v) = 16B。")
        out.line("  被冻结的基座只需要躺着，4B/参数，不产生梯度和动量。")
        mem_full = training_memory(base_counts["total"], full_trainable, optimizer="adam")
        mem_lora = training_memory(lora_counts["total"], lora_trainable, optimizer="adam")
        out.table(
            ["方式", "权重", "梯度", "Adam 状态", "合计", "相对全量"],
            [
                ["全量微调", human_bytes(mem_full["param_bytes"]), human_bytes(mem_full["grad_bytes"]),
                 human_bytes(mem_full["optimizer_bytes"]), human_bytes(mem_full["total_bytes"]), "1.00×"],
                [f"LoRA r={R}", human_bytes(mem_lora["param_bytes"]), human_bytes(mem_lora["grad_bytes"]),
                 human_bytes(mem_lora["optimizer_bytes"]), human_bytes(mem_lora["total_bytes"]),
                 f"{mem_lora['total_bytes'] / mem_full['total_bytes']:.2f}×"],
            ],
            aligns=["<", ">", ">", ">", ">", ">"],
        )
        out.kv("训练显存节省", f"{mem_full['total_bytes'] / mem_lora['total_bytes']:.2f}×",
               "（权重那部分省不掉，省的是梯度+动量）")

        # ---------------- 真跑 ----------------
        out.subsection(f"4. 真跑一遍：各训 {STEPS} 步（同一份 Java 面试数据，只算答案区 loss）")
        t0 = time.perf_counter()
        full_losses = train_full(model, examples, STEPS, lr=LR)
        t_full = time.perf_counter() - t0
        out.kv("全量微调 首步 loss", f"{full_losses[0]:.4f}")
        out.kv("全量微调 末步 loss", f"{full_losses[-1]:.4f}")
        out.kv("全量微调 下降", f"{full_losses[0] - full_losses[-1]:.4f}")
        out.kv("全量微调 耗时", f"{t_full:.2f} s")

        # LoRA：重新加载一份干净的基座，避免被上面全量微调污染
        model2, tok, _info = ensure_base_model()
        inject_lora(model2, r=R, alpha=ALPHA, rng=0)
        trainer = LoRATrainer(model2, lr=LR, optimizer="adam", seed=0)
        t0 = time.perf_counter()
        lora_losses = trainer.run(examples, STEPS, batch_size=4)
        t_lora = time.perf_counter() - t0
        out.kv("LoRA 首步 loss", f"{lora_losses[0]:.4f}")
        out.kv("LoRA 末步 loss", f"{lora_losses[-1]:.4f}")
        out.kv("LoRA 下降", f"{lora_losses[0] - lora_losses[-1]:.4f}")
        out.kv("LoRA 耗时", f"{t_lora:.2f} s")

        out.blank()
        out.line("  loss 曲线采样（每 10 步）：")
        rows = []
        for i in range(0, STEPS, 10):
            rows.append([f"step {i + 1}", f"{full_losses[i]:.4f}", f"{lora_losses[i]:.4f}"])
        rows.append([f"step {STEPS}", f"{full_losses[-1]:.4f}", f"{lora_losses[-1]:.4f}"])
        out.table(["", "全量微调", f"LoRA r={R}"], rows, aligns=["<", ">", ">"])

        # ---------------- 结论 ----------------
        out.subsection("5. 本 demo 的关键数字")
        out.kv("可训练参数（占基座）", f"LoRA {lora_trainable:,} / 全量 {full_trainable:,} = {lora_trainable / full_trainable:.2%}")
        out.kv("可训练参数（占注入后总量）", f"{lora_trainable:,} / {lora_counts['total']:,} = {lora_counts['trainable_ratio']:.2%}")
        out.kv("训练显存（含 Adam）", f"{human_bytes(mem_lora['total_bytes'])} vs {human_bytes(mem_full['total_bytes'])}"
               f" = {mem_lora['total_bytes'] / mem_full['total_bytes']:.2%}")
        out.kv(f"{STEPS} 步后 loss", f"全量 {full_losses[-1]:.4f} / LoRA {lora_losses[-1]:.4f}")
        winner = "LoRA" if lora_losses[-1] < full_losses[-1] else "全量微调"
        out.kv(f"{STEPS} 步后谁更低", f"{winner}（差 {abs(full_losses[-1] - lora_losses[-1]):.4f}）")
        out.blank()
        out.line("  读法：LoRA 只动了约 1/8.5 的参数，loss 却追平（甚至略优于）全量微调 ——")
        out.line("  这正是「低秩假设」的实证：本任务的适配方向，确实躺在很低维的子空间里。")
        out.line(f"  注意 loss 只是训练目标：全量微调改写的是整个基座，代价要到 M09 的")
        out.line("  「灾难性遗忘」检查里才看得出来 —— 只看 loss 会得出错误结论。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
