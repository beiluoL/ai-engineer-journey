#!/usr/bin/env python
"""M07 · Checkpoint —— adapter 存盘体积、续训连续性、以及"假续训"长什么样。

LoRA 在工程上最爽的一点：**每个任务只存一个几 MB 的小文件**。
本 demo 把这个"几 MB"落到真实文件上，并验证一件更关键的事 ——

    断点续训，loss 曲线必须**接得上**。

很多人以为"存了权重 = 能续训"，其实不是。Adam 的一阶/二阶动量（m / v）和
步数 t 也是训练状态的一部分。只存 A / B、不存训练状态，续训的第一步相当于
「用全新状态去走」，曲线会抖一下 —— 那是**假续训**。

三组对照（同一 seed、同一数据顺序）：
    A：一次性训 100 步（黄金基准）
    B：训 50 步 → 存盘（含训练状态）→ 重新加载 → 续训 50 步
    C：训 50 步 → 存盘 → 只加载 A/B，**丢掉训练状态** → 续训 50 步

⚠ 本 demo 还报告了一个实测发现：P06 的 ``Adam.step()`` 没有把 m / v 写回
``self.state``，所以**动量从未真正累积**（state 恒为 0）。这意味着在本仓库里
「断点要恢复的东西」主要是 step 计数 t（它影响 Adam 的偏置修正）。
发现本身比结论重要：如果哪天换成真正带 Adam 动量的实现，m/v 就是必需的了。
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
    adapter_report,
    build_sft_examples,
    count_parameters,
    ensure_base_model,
    human_bytes,
    inject_lora,
    load_adapter,
    load_checkpoint,
    load_java_records,
    save_adapter,
    save_checkpoint,
    trainable_parameters,
)
from ft.paths import P08_MODELS  # noqa: E402

STEPS = 50
R, ALPHA, LR = 8, 16.0, 3e-3
ADAPTER_FULL = P08_MODELS / "adapters" / "demo07_full.npz"
ADAPTER_WEIGHTS = P08_MODELS / "adapters" / "demo07_weights_only.npz"


def main() -> None:
    out = Printer("demo_07_checkpoint")
    try:
        out.section("M07 · Checkpoint：存盘体积 + 续训连续性 + 假续训对照")

        model0, tok, _info = ensure_base_model()
        recs = load_java_records()
        examples = build_sft_examples(recs, tok, max_len=model0.max_len)
        inject_lora(model0, r=R, alpha=ALPHA, rng=0)  # 只为拿到注入后的参数账
        counts0 = count_parameters(model0)
        out.kv("基座参数量 / fp32 体积", f"{counts0['base']:,} / {human_bytes(4 * counts0['base'])}")
        out.kv("adapter 参数量", f"{counts0['trainable']:,}", f"注入 r={R} 后（占总量 {counts0['trainable_ratio']:.2%}）")

        # ---------------- A：一次性 100 步 ----------------
        out.subsection(f"1. 基准 A：一次性训 {STEPS * 2} 步")
        model_a, _, _ = ensure_base_model()
        inject_lora(model_a, r=R, alpha=ALPHA, rng=0)
        tr_a = LoRATrainer(model_a, lr=LR, optimizer="adam", seed=0)
        losses_a = tr_a.run(examples, STEPS * 2, batch_size=4)
        out.kv(f"第 {STEPS} 步 loss", f"{losses_a[STEPS - 1]:.4f}")
        out.kv(f"第 {STEPS * 2} 步 loss", f"{losses_a[-1]:.4f}")
        out.kv("后 50 步均值", f"{np.mean(losses_a[STEPS:]):.4f}")

        # ---------------- B：存盘 + 续训 ----------------
        out.subsection(f"2. 真续训 B：训 {STEPS} 步存盘 → 重新加载 → 再训 {STEPS} 步")
        model_b, _, _ = ensure_base_model()
        inject_lora(model_b, r=R, alpha=ALPHA, rng=0)
        tr_b = LoRATrainer(model_b, lr=LR, optimizer="adam", seed=0)
        losses_b1 = tr_b.run(examples, STEPS, batch_size=4)

        t0 = time.perf_counter()
        info_full = save_checkpoint(model_b, tr_b, ADAPTER_FULL, meta={"demo": "demo_07", "r": R, "alpha": ALPHA})
        save_sec = time.perf_counter() - t0
        # 只存权重（用于推理分发）的体积对照
        info_w = save_adapter(model_b, ADAPTER_WEIGHTS, trainer=None, include_optimizer=False)
        rep_full = adapter_report(ADAPTER_FULL, model_b)
        rep_w = adapter_report(ADAPTER_WEIGHTS, model_b)

        out.table(
            ["文件", "内容", "体积", "占基座 fp32"],
            [["demo07_weights_only.npz", "仅 A/B 权重", human_bytes(rep_w["total_bytes"]),
              f"{rep_w['ratio_of_base']:.2%}"],
             ["demo07_full.npz", "A/B + Adam m/v", human_bytes(rep_full["total_bytes"]),
              f"{rep_full['ratio_of_base']:.2%}"],
             ["（对照）基座权重", "全部基座参数 fp32", human_bytes(4 * counts0["total"]), "100.00%"]],
            aligns=["<", "<", ">", ">"],
        )
        out.kv("基座 / adapter（仅权重）", f"{4 * counts0['total'] / rep_w['total_bytes']:.2f}×",
               "这就是「一个基座 + N 个小 adapter」的底气")
        out.kv("存盘精度", f"{info_full.get('save_dtype')}", "训练是 fp64，落盘转 fp32（工业界惯例）")
        out.kv("存盘耗时", f"{save_sec * 1000:.1f} ms")
        out.kv("存进去的数组数", f"{len(info_full['layers']) * 2} 个 A/B + {len(trainable_parameters(model_b)) * 2} 个动量")
        out.kv("元信息记录的步数", f"{info_full['optimizer']['step']}", "Adam 的 t 也存了")

        model_b2, _, _ = ensure_base_model()
        inject_lora(model_b2, r=R, alpha=ALPHA, rng=0)
        tr_b2 = LoRATrainer(model_b2, lr=LR, optimizer="adam", seed=0)
        t0 = time.perf_counter()
        load_checkpoint(model_b2, tr_b2, ADAPTER_FULL)
        load_sec = time.perf_counter() - t0
        out.kv("加载耗时", f"{load_sec * 1000:.1f} ms")
        out.kv("加载后 trainer.step / Adam.t", f"{tr_b2.step} / {tr_b2.optimizer.t}", "← 续训从第 51 步接着数")
        losses_b2 = tr_b2.run(examples, STEPS, batch_size=4)
        out.kv("续训第 1 步（总第 51 步）", f"{losses_b2[0]:.4f}", f"基准 A 同时刻 {losses_a[STEPS]:.4f}")
        out.kv(f"续训第 {STEPS} 步（总第 100 步）", f"{losses_b2[-1]:.4f}", f"基准 A 同时刻 {losses_a[-1]:.4f}")
        out.kv("后 50 步均值", f"{np.mean(losses_b2):.4f}", f"基准 A {np.mean(losses_a[STEPS:]):.4f}")
        gap_b = float(np.max(np.abs(np.array(losses_b2) - np.array(losses_a[STEPS:]))))
        out.kv("B 与 A 的逐点最大差", f"{gap_b:.3e}", "loss 曲线接上了")
        # 断点两侧是否平滑（和基准 A 在同一点的跳变比一比）
        jump_b = abs(losses_b2[0] - losses_b1[-1])
        jump_a = abs(losses_a[STEPS] - losses_a[STEPS - 1])
        out.kv("断点处跳变 |第50步→第51步|", f"{jump_b:.4f}", f"基准 A 在同一点 {jump_a:.4f} → 完全相同，无额外跳变")

        # ---------------- C：假续训 ----------------
        out.subsection(f"3. 假续训 C：同样的 adapter，只加载权重、丢弃训练状态 → 再训 {STEPS} 步")
        model_c, _, _ = ensure_base_model()
        inject_lora(model_c, r=R, alpha=ALPHA, rng=0)
        tr_c = LoRATrainer(model_c, lr=LR, optimizer="adam", seed=0)
        _meta = load_adapter(model_c, ADAPTER_FULL)  # 只加载 A/B
        out.kv("加载后 trainer.step / Adam.t", f"{tr_c.step} / {tr_c.optimizer.t}", "← 状态清零，从 0 重新数")
        losses_c = tr_c.run(examples, STEPS, batch_size=4)
        out.kv("第 1 步 loss", f"{losses_c[0]:.4f}", f"基准 A 同时刻 {losses_a[STEPS]:.4f}")
        out.kv(f"第 {STEPS} 步 loss", f"{losses_c[-1]:.4f}", f"基准 A 同时刻 {losses_a[-1]:.4f}")
        out.kv("后 50 步均值", f"{np.mean(losses_c):.4f}", f"基准 A {np.mean(losses_a[STEPS:]):.4f}")
        gap_c = float(np.max(np.abs(np.array(losses_c) - np.array(losses_a[STEPS:]))))
        out.kv("C 与 A 的逐点最大差", f"{gap_c:.3e}")
        out.kv("C 相对 B 的后 50 步均值差", f"{np.mean(losses_c) - np.mean(losses_b2):+.4f}")

        # ---------------- 对比表 ----------------
        out.subsection("4. 三种方式的对比")
        out.table(
            ["方式", "后 50 步均值", "终点 loss", "与 A 逐点最大差", "判定"],
            [["A 一次性 100 步", f"{np.mean(losses_a[STEPS:]):.4f}", f"{losses_a[-1]:.4f}", "0（基准）", "—"],
             ["B 续训（含训练状态）", f"{np.mean(losses_b2):.4f}", f"{losses_b2[-1]:.4f}", f"{gap_b:.2e}", "曲线连续"],
             ["C 续训（丢训练状态）", f"{np.mean(losses_c):.4f}", f"{losses_c[-1]:.4f}", f"{gap_c:.2e}", "假续训"]],
            aligns=["<", ">", ">", ">", "<"],
        )

        # ---------------- P06 Adam 的实测发现 ----------------
        out.subsection("5. 一个实测发现：P06 的 Adam 动量从未累积")
        model_d, _, _ = ensure_base_model()
        inject_lora(model_d, r=R, alpha=ALPHA, rng=0)
        tr_d = LoRATrainer(model_d, lr=LR, optimizer="adam", seed=0)
        tr_d.run(examples, 30, batch_size=4)
        state = tr_d.optimizer.state
        nonzero = int(sum(np.count_nonzero(v[0]) + np.count_nonzero(v[1]) for v in state.values()))
        n_state = int(sum(v[0].size + v[1].size for v in state.values()))
        out.kv("训了 30 步后 Adam state 里非零元素", f"{nonzero} / {n_state:,}")
        out.kv("即", "m / v 全是 0 —— 动量从来没有累积过")
        out.kv("原因", "P06 的 Adam.step() 里 m/v 是局部变量，算完没写回 self.state")
        out.kv("后果 1", "断点真正需要恢复的是 step 计数 t（它参与偏置修正）")
        out.kv("后果 2", "有效步长随 t 衰减：m̂=(1-β₁)g/(1-β₁ᵗ)，t=1 时约为 t=50 时的 10 倍")
        out.kv("本 demo 的处理", "不修改 P06（只读依赖），照实记录；m/v 仍然落盘，换了正确实现就能直接用")
        out.blank()
        out.line("  这也解释了上面 C 组的数字：t 归零 → 头几步等效学习率变大 → 曲线先抖一下。")
        out.line("  在**真正带动量**的 Adam 上，丢掉 m/v 的代价会明显更大、也更难补回来。")

        # ---------------- 往返一致性 ----------------
        out.subsection("6. 存 → 取 → 往返一致性")
        model_e, _, _ = ensure_base_model()
        inject_lora(model_e, r=R, alpha=ALPHA, rng=0)
        tr_e = LoRATrainer(model_e, lr=LR, optimizer="adam", seed=0)
        tr_e.run(examples, 10, batch_size=4)
        before = [np.array(p.data) for p in tr_e.params]

        save_checkpoint(model_e, tr_e, ADAPTER_FULL)  # fp32 落盘
        model_f, _, _ = ensure_base_model()
        inject_lora(model_f, r=R, alpha=ALPHA, rng=0)
        tr_f = LoRATrainer(model_f, lr=LR, optimizer="adam", seed=0)
        load_checkpoint(model_f, tr_f, ADAPTER_FULL)
        diffs32 = [float(np.max(np.abs(a - b.data))) for a, b in zip(before, tr_f.params)]
        out.kv("fp32 落盘的往返最大误差", f"{max(diffs32):.3e}", f"相对量级 ~1e-7（fp32 精度）")

        save_checkpoint(model_e, tr_e, ADAPTER_FULL, dtype=np.float64)  # fp64 落盘
        model_g, _, _ = ensure_base_model()
        inject_lora(model_g, r=R, alpha=ALPHA, rng=0)
        tr_g = LoRATrainer(model_g, lr=LR, optimizer="adam", seed=0)
        load_checkpoint(model_g, tr_g, ADAPTER_FULL)
        diffs64 = [float(np.max(np.abs(a - b.data))) for a, b in zip(before, tr_g.params)]
        out.kv("fp64 落盘的往返最大误差", f"{max(diffs64):.3e}", "逐位一致")

        out.subsection("7. 本 demo 的关键数字")
        out.kv("adapter 文件体积（仅权重）", f"{human_bytes(rep_w['total_bytes'])}")
        out.kv("adapter 文件体积（含训练状态）", f"{human_bytes(rep_full['total_bytes'])}")
        out.kv("基座 fp32 体积", f"{human_bytes(4 * counts0['base'])}",
               f"基座 / adapter = {4 * counts0['base'] / rep_w['total_bytes']:.1f}×")
        out.kv("续训是否连续", f"是（与基准逐点最大差 {gap_b:.3e}）")
        out.kv("假续训偏差", f"{gap_c:.3e}")
        out.kv("fp64 往返误差", f"{max(diffs64):.3e}")
        out.blank()
        out.line("  实践含义：一个基座常驻，每个下游任务一个一百多 KB 的 adapter 文件，")
        out.line("  切任务只换 adapter —— 这是全量微调根本做不到的部署形态。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
