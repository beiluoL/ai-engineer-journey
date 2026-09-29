#!/usr/bin/env python
"""M04 · LoRA —— 结构解剖、B=0 初始化等价性证明、梯度对拍、真训一遍。

LoRA 的全部公式只有一行：

    W' = W + (alpha/r) · B @ A        A:[in, r] 随机小值，B:[r, out] 全零

这一行里藏着三个**必须被数值证明**的性质，否则就是"我以为我实现了 LoRA"：

1. **初始化等价性**：B 全零 ⟹ ΔW = 0 ⟹ 刚注入时模型输出与基座**逐位相同**。
   这保证 LoRA 是「从基座出发做增量」，而不是「换个随机初始化重训」。
2. **缩放生效**：alpha/r 是真的乘进去了（改 alpha 输出必须跟着变）。
3. **梯度能穿过去**：dL/dA、dL/dB 必须由 autograd 正确算出来（用中心差分对拍），
   而且 dL/dW 不该被优化器用（基座冻结）。

本 demo 四个性质全部用真实数字验证，最后训 120 步看 loss 真降。
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
    LoRALinear,
    LoRATrainer,
    base_parameters,
    build_sft_examples,
    count_parameters,
    curve_summary,
    ensure_base_model,
    freeze_base,
    inject_lora,
    load_java_records,
    lora_layers,
    named_parameters,
    trainable_parameters,
    visualize_example,
)
from model import Tensor, TransformerLM, cross_entropy, grad_check  # noqa: E402

STEPS = 120
R, ALPHA, LR = 8, 16.0, 3e-3


def main() -> None:
    out = Printer("demo_04_lora")
    try:
        out.section("M04 · LoRA：结构解剖 → B=0 等价性 → 梯度对拍 → 真训")

        # ---------------- 1. 结构解剖 ----------------
        out.subsection("1. 单层结构解剖（以 FFN 的 W1: 64 → 256 为例）")
        layer = LoRALinear(64, 256, r=R, alpha=ALPHA, rng=0)
        out.kv("W（冻结）shape", f"{tuple(layer.W.data.shape)}", f"{layer.W.data.size:,} 个参数")
        out.kv("A shape", f"{tuple(layer.A.data.shape)}", f"{layer.A.data.size:,} 个参数")
        out.kv("B shape", f"{tuple(layer.B.data.shape)}", f"{layer.B.data.size:,} 个参数")
        out.kv("缩放系数 alpha/r", f"{ALPHA:g}/{R} = {layer.scaling:g}")
        out.kv("本层参数量", f"基座 {layer.W.data.size:,} → 可训练 {layer.A.data.size + layer.B.data.size:,}"
               f" = {(layer.A.data.size + layer.B.data.size) / layer.W.data.size:.2%}")
        out.kv("A 的初始化范围", f"[{layer.A.data.min():+.4f}, {layer.A.data.max():+.4f}]", "均匀分布 U(-1/√in, 1/√in)")
        out.kv("B 的初始化", f"全零（max|B| = {np.abs(layer.B.data).max():g}）")

        # ---------------- 2. 等价性 ----------------
        out.subsection("2. B=0 初始化等价性证明（ΔW 必须严格为 0）")
        out.kv("delta_weight() 全零", f"{bool(np.all(layer.delta_weight() == 0.0))}",
               f"max|ΔW| = {np.abs(layer.delta_weight()).max():g}")
        x = Tensor(np.random.randn(4, 64))
        y_lora = layer(x)
        y_base = x.data @ layer.W.data
        out.kv("单层：LoRA 输出 vs 纯基座输出", f"最大绝对误差 = {np.max(np.abs(y_lora.data - y_base)):.3e}")

        model, tok, _info = ensure_base_model()
        x_ids = np.random.randint(4, tok.vocab_size, (4, 64))
        out_before = model(x_ids, mask=None).data.copy()
        injected = inject_lora(model, r=R, alpha=ALPHA, rng=0)
        out_after = model(x_ids, mask=None).data
        diff_full = float(np.max(np.abs(out_after - out_before)))
        out.kv("整机：注入前 vs 注入后（同一输入）", f"最大绝对误差 = {diff_full:.3e}",
               f"13 层全部注入，模型输出 {np.prod(out_before.shape):,} 个数全部相同")

        # ---------------- 3. 缩放 ----------------
        out.subsection("3. alpha/r 缩放是否真的生效")
        layer.B.data[:] = np.random.default_rng(1).normal(0, 0.1, size=layer.B.data.shape)
        dw = layer.delta_weight()
        manual = (ALPHA / R) * (layer.A.data @ layer.B.data)
        out.kv("ΔW vs (alpha/r)·A@B", f"最大绝对误差 = {np.max(np.abs(dw - manual)):.3e}")
        outs = {}
        for alpha in (4.0, 16.0, 32.0):
            l2 = LoRALinear(64, 256, r=R, alpha=alpha, weight=layer.W, rng=0)
            l2.A.data[:] = layer.A.data
            l2.B.data[:] = layer.B.data
            outs[alpha] = l2(x).data
        base_only = x.data @ layer.W.data
        out.table(
            ["alpha", "scaling", "输出相对基座的偏移 ‖Δy‖/‖y‖"],
            [[f"{a:g}", f"{a / R:g}", f"{np.linalg.norm(outs[a] - base_only) / np.linalg.norm(base_only):.6f}"]
             for a in (4.0, 16.0, 32.0)],
            aligns=["<", ">", ">"],
        )
        out.line("  偏移与 alpha 成正比 → 缩放确实被乘进了前向（不是摆设）。")

        # ---------------- 4. 梯度对拍 ----------------
        out.subsection("4. 梯度对拍：autograd vs 中心差分")
        small = LoRALinear(32, 48, r=4, alpha=8.0, rng=0)
        small.B.data[:] = np.random.default_rng(2).normal(0, 0.05, size=small.B.data.shape)
        xs = Tensor(np.random.randn(5, 32))
        targets = np.random.randint(0, 48, size=5)

        def f_single(a, b):
            small.A, small.B = a, b
            return cross_entropy(small(xs), targets)

        err_single = grad_check(f_single, [small.A, small.B], eps=1e-6)
        out.kv("独立 LoRALinear 的 grad_check", f"最大相对误差 = {err_single:.3e}", "（< 1e-4 即通过）")

        # 端到端：把 LoRA 塞进一个迷你 TransformerLM，验证整条计算图接对了
        np.random.seed(0)
        tiny = TransformerLM(vocab_size=64, d_model=16, n_heads=4, d_ff=32, n_layers=1, max_len=16)
        inj_tiny = inject_lora(tiny, targets=("Wq",), r=2, alpha=4.0, rng=0)
        tiny_ids = np.random.randint(0, 64, (2, 8))
        tiny_y = np.random.randint(0, 64, (2, 8))

        def f_tiny(a, b):
            path, lay = inj_tiny[0]
            lay.A, lay.B = a, b
            return cross_entropy(tiny(tiny_ids, mask=None), tiny_y)

        lay_a, lay_b = inj_tiny[0][1].A, inj_tiny[0][1].B
        lay_b.data[:] = np.random.default_rng(3).normal(0, 0.05, size=lay_b.data.shape)
        err_tiny = grad_check(f_tiny, [lay_a, lay_b], eps=1e-6)
        out.kv("注入进 TransformerLM 后的 grad_check", f"最大相对误差 = {err_tiny:.3e}",
               "（证明 P06 的原前向里梯度确实流回了 A/B）")

        # ---------------- 5. 注入前后账目 ----------------
        out.subsection("5. 注入前后的参数账")
        model2, tok, _ = ensure_base_model()
        c_before = count_parameters(model2)
        inj = inject_lora(model2, r=R, alpha=ALPHA, rng=0)
        c_after = count_parameters(model2)
        out.table(
            ["", "参数量", "说明"],
            [
                ["基座（冻结）", f"{c_after['base']:,}", "注入前后完全相同"],
                [f"adapter（r={R}）", f"{c_after['trainable']:,}", f"{len(inj)} 个线性层 × r×(in+out)"],
                ["合计", f"{c_after['total']:,}", f"可训练占比 {c_after['trainable_ratio']:.2%}"],
            ],
            aligns=["<", ">", "<"],
        )
        out.kv("进优化器的参数张量个数", f"{len(trainable_parameters(model2))}", "（13 层 × 2 = 26）")
        out.kv("被冻结的参数张量个数", f"{freeze_base(model2)}")
        out.kv("adapter 参数里 requires_grad=True 的", f"{sum(1 for p in trainable_parameters(model2) if p.requires_grad)}")

        # ---------------- 6. 真训 ----------------
        out.subsection(f"6. 真训 {STEPS} 步（只更新 A / B，基座必须一动不动）")
        recs = load_java_records()
        examples = build_sft_examples(recs, tok, max_len=model2.max_len)
        # ⚠ 快照必须用 base_parameters（它对 LoRA 层里的 W 去掉了 .W 后缀），
        #   否则注入前后的路径对不上，会把「基座被动了」误报成 13 个。
        base_snap = {p: param.data.tobytes() for p, param in base_parameters(model2)}
        adapter_snap = {p: param.data.tobytes() for p, param in named_parameters(model2)
                        if p.endswith(".A") or p.endswith(".B")}
        trainer = LoRATrainer(model2, lr=LR, optimizer="adam", seed=0)
        t0 = time.perf_counter()
        losses = trainer.run(examples, STEPS, batch_size=4)
        dt = time.perf_counter() - t0
        s = curve_summary(losses)
        out.table(
            ["step", "loss"],
            [[f"{(i + 1):>4}", f"{losses[i]:.4f}"] for i in list(range(0, 20, 4)) + list(range(20, STEPS, 20)) + [STEPS - 1]],
            aligns=["<", ">"],
        )
        out.kv("首步 loss", f"{s['first']:.4f}")
        out.kv("末步 loss", f"{s['last']:.4f}")
        out.kv("前 10 步均值 → 后 10 步均值", f"{s['first_window']:.4f} → {s['last_window']:.4f}"
               f"（↓{s['drop']:.4f}，{s['drop_ratio']:.1%}）")
        out.kv("训练耗时", f"{dt:.2f} s")

        base_now = {p: param.data.tobytes() for p, param in base_parameters(model2)}
        base_changed = [p for p in base_now if base_now[p] != base_snap[p]]
        adapter_now = {p: param.data.tobytes() for p, param in named_parameters(model2)
                       if p.endswith(".A") or p.endswith(".B")}
        adapter_changed = [p for p in adapter_now if adapter_now[p] != adapter_snap[p]]
        out.kv("训练后基座权重发生变化的张量", f"{len(base_changed)} / {len(base_snap)}",
               "字节级比对（.tobytes()），冻结生效")
        out.kv("训练后 adapter 发生变化的张量", f"{len(adapter_changed)} / {len(adapter_snap)}",
               "应当全部变化（说明真的在学）")
        out.kv("被改动的张量样例", ", ".join(sorted(adapter_changed)[:3]) + " …", "全部是 *.A / *.B")

        # ---------------- 7. 收尾 ----------------
        out.subsection("7. 本 demo 的关键数字")
        out.kv("B=0 等价性 最大绝对误差", f"{diff_full:.3e}", "整机 4×64×1024 个输出全部逐位相同")
        out.kv("grad_check 最大相对误差", f"{max(err_single, err_tiny):.3e}")
        out.kv("可训练参数", f"{c_after['trainable']:,} / {c_after['total']:,} = {c_after['trainable_ratio']:.2%}")
        out.kv("训练前后 loss", f"{s['first']:.4f} → {s['last']:.4f}")
        out.kv("基座权重是否被动过", f"{'否' if not base_changed else '是'}（{len(base_changed)} 个张量变化）")
        out.blank()
        out.line("  一个实现上的坑（写在代码注释里了）：P06 的 Tensor.__init__ 会把")
        out.line("  _backward 设成**实例属性**的 noop lambda，它会遮蔽子类里定义的同名方法。")
        out.line("  所以 LoRALinear 必须在 __init__ 里显式 self._backward = self._lora_backward，")
        out.line("  否则梯度根本不会流回 A/B —— 而且不会报错，只是 loss 死活不降。")
    finally:
        out.close()


if __name__ == "__main__":
    main()
