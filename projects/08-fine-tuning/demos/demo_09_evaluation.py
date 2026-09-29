#!/usr/bin/env python
"""M09 · Fine-Tuned Model Evaluation —— 到底学会了没有？忘了没有？

评估微调效果必须同时看两个数，只看一个必然被骗：

    域内困惑度（Java 面试）  下降  → 学会了领域知识
    通用困惑度（P06 通用语料）不暴涨 → 没有灾难性遗忘

把模型训成"只会背 59 条答案的复读机"，域内指标也会很好看 —— 所以通用集是必须的。
本 demo 额外加了**全量微调**作为对照组：它在 demo_01 里 loss 更低，
这里要看它是不是把通用能力赔进去了。

定性部分（生成样例）会如实呈现：本项目是 d_model=64、2 层、预训练语料 1KB 量级
的玩具模型，生成质量**注定很差**。这不丢人 —— 指标与体感的差距本身就是结论：
它说明为什么真实场景要用 7B 起步的基座，也说明困惑度下降 ≠ 效果可用。
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
    build_lm_examples,
    build_sft_examples,
    ensure_base_model,
    evaluate,
    forgetting_report,
    generate_text,
    general_corpus,
    inject_lora,
    load_java_records,
    lora_layers,
    named_parameters,
)
from ft.sft_data import pad_batch  # noqa: E402
from model import Adam, cross_entropy  # noqa: E402

STEPS = 150
R, ALPHA, LR = 8, 16.0, 3e-3
PROMPT = "### 指令:\n请解释 Java 中 HashMap 的底层原理（以 JDK 8 为例）\n\n### 回答:\n"


def train_full(model, examples, n_steps, lr, batch_size=4, seed=0):
    """全量微调对照组：所有基座参数都进优化器。"""
    params = [p for _path, p in named_parameters(model)]
    opt = Adam(params, lr=lr)
    n = len(examples)
    n_batches = max(1, int(np.ceil(n / batch_size)))
    losses, perms = [], {}
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
    out = Printer("demo_09_evaluation")
    try:
        out.section("M09 · Evaluation：域内 / 通用困惑度对比 + 灾难性遗忘 + 定性生成")

        # ---------------- 1. 三套评估集 ----------------
        out.subsection("1. 三套评估集（全部来自真实 encode）")
        model, tok, _info = ensure_base_model()
        recs = load_java_records()
        domain = build_sft_examples(recs, tok, max_len=model.max_len)
        train_lines, held_lines = general_corpus()
        general_seen = build_lm_examples("\n".join(train_lines), tok, max_len=model.max_len)
        general_unseen = build_lm_examples("\n".join(held_lines), tok, max_len=model.max_len)
        out.table(
            ["评估集", "样本数", "计入 loss 的 token", "用途"],
            [["域内：Java 面试（答案区）", f"{len(domain)}", f"{sum(int(e.mask.sum()) for e in domain):,}", "有没有学会"],
             ["通用：预训练见过的语料", f"{len(general_seen)}", f"{sum(int(e.mask.sum()) for e in general_seen):,}", "有没有遗忘"],
             ["通用：预训练没见过的语料", f"{len(general_unseen)}", f"{sum(int(e.mask.sum()) for e in general_unseen):,}", "泛化参考"]],
            aligns=["<", ">", ">", "<"],
        )
        out.line("  注意：困惑度只在**同一个分词器**内部可比，跨分词器/跨数据集比较没有意义。")

        # ---------------- 2. 微调前 ----------------
        out.subsection("2. 微调前的基线")
        d0 = evaluate(model, domain)
        g0 = evaluate(model, general_seen)
        u0 = evaluate(model, general_unseen)
        out.kv("域内困惑度（Java 面试）", f"{d0['ppl']:,.2f}", f"CE={d0['mean_ce']:.4f}")
        out.kv("通用困惑度（见过）", f"{g0['ppl']:,.2f}", f"CE={g0['mean_ce']:.4f}")
        out.kv("通用困惑度（没见过）", f"{u0['ppl']:,.2f}", f"CE={u0['mean_ce']:.4f}")
        out.line(f"  读法：基座在通用语料上 CE={g0['mean_ce']:.2f}（预训练时见过这部分语料），")
        out.line(f"        但在 Java 领域上 CE={d0['mean_ce']:.2f} —— 这个差距就是「领域不适配」。")

        # ---------------- 3. LoRA 微调 ----------------
        out.subsection(f"3. LoRA 微调 {STEPS} 步（只算答案区 loss）")
        inject_lora(model, r=R, alpha=ALPHA, rng=0)
        trainer = LoRATrainer(model, lr=LR, optimizer="adam", seed=0)
        t0 = time.perf_counter()
        losses = trainer.run(domain, STEPS, batch_size=4)
        dt = time.perf_counter() - t0
        out.table(
            ["step", "loss"],
            [[f"{i + 1}", f"{losses[i]:.4f}"] for i in [0, 9, 29, 59, 89, 119, 149]],
            aligns=["<", ">"],
        )
        out.kv("训练 loss", f"{losses[0]:.4f} → {losses[-1]:.4f}"
               f"（↓{losses[0] - losses[-1]:.4f}）")
        out.kv("耗时", f"{dt:.1f} s")
        d1 = evaluate(model, domain)
        g1 = evaluate(model, general_seen)
        u1 = evaluate(model, general_unseen)
        out.kv("微调后 域内困惑度", f"{d1['ppl']:,.2f}")
        out.kv("微调后 通用困惑度（见过）", f"{g1['ppl']:,.2f}")
        out.kv("微调后 通用困惑度（没见过）", f"{u1['ppl']:,.2f}")

        # ---------------- 4. 全量微调对照 ----------------
        out.subsection(f"4. 对照组：全量微调 {STEPS} 步（把所有基座参数都改一遍）")
        model_full, _, _ = ensure_base_model()
        full_losses = train_full(model_full, domain, STEPS, lr=LR)
        d2 = evaluate(model_full, domain)
        g2 = evaluate(model_full, general_seen)
        u2 = evaluate(model_full, general_unseen)
        out.kv("训练 loss", f"{full_losses[0]:.4f} → {full_losses[-1]:.4f}")
        out.kv("微调后 域内困惑度", f"{d2['ppl']:,.2f}")
        out.kv("微调后 通用困惑度（见过）", f"{g2['ppl']:,.2f}")
        out.kv("微调后 通用困惑度（没见过）", f"{u2['ppl']:,.2f}")

        # ---------------- 5. 对比表 ----------------
        out.subsection("5. 三种状态的对比")
        out.table(
            ["困惑度", "基座（未微调）", f"LoRA r={R}", "全量微调"],
            [["域内（Java 面试）", f"{d0['ppl']:,.1f}", f"{d1['ppl']:,.1f}", f"{d2['ppl']:,.1f}"],
             ["通用（见过）", f"{g0['ppl']:,.1f}", f"{g1['ppl']:,.1f}", f"{g2['ppl']:,.1f}"],
             ["通用（没见过）", f"{u0['ppl']:,.1f}", f"{u1['ppl']:,.1f}", f"{u2['ppl']:,.1f}"]],
            aligns=["<", ">", ">", ">"],
        )
        out.table(
            ["变化", "LoRA", "全量微调"],
            [["域内下降", f"{(1 - d1['ppl'] / d0['ppl']) * 100:.2f}%", f"{(1 - d2['ppl'] / d0['ppl']) * 100:.2f}%"],
             ["通用（见过）变化", f"{(g1['ppl'] / g0['ppl'] - 1) * 100:+.2f}%", f"{(g2['ppl'] / g0['ppl'] - 1) * 100:+.2f}%"],
             ["通用（没见过）变化", f"{(u1['ppl'] / u0['ppl'] - 1) * 100:+.2f}%", f"{(u2['ppl'] / u0['ppl'] - 1) * 100:+.2f}%"]],
            aligns=["<", ">", ">"],
        )

        # ---------------- 6. 遗忘判定 ----------------
        out.subsection("6. 灾难性遗忘判定（通用语料困惑度是否暴涨）")
        fr_lora = forgetting_report(
            {"ppl_before": d0["ppl"], "ppl_after": d1["ppl"], "drop_pct": (1 - d1["ppl"] / d0["ppl"]) * 100, "better": d1["ppl"] < d0["ppl"]},
            {"ppl_before": g0["ppl"], "ppl_after": g1["ppl"]}, tolerance=0.10,
        )
        fr_full = forgetting_report(
            {"ppl_before": d0["ppl"], "ppl_after": d2["ppl"], "drop_pct": (1 - d2["ppl"] / d0["ppl"]) * 100, "better": d2["ppl"] < d0["ppl"]},
            {"ppl_before": g0["ppl"], "ppl_after": g2["ppl"]}, tolerance=0.10,
        )
        out.kv("LoRA：域内下降", f"{fr_lora['domain_drop_pct']:.2f}%")
        out.kv("LoRA：通用困惑度变化", f"{fr_lora['general_rise_pct']:+.2f}%", f"容忍度 ±{fr_lora['tolerance_pct']:.0f}%")
        out.kv("LoRA 判定", fr_lora["verdict"])
        out.kv("全量：域内下降", f"{fr_full['domain_drop_pct']:.2f}%")
        out.kv("全量：通用困惑度变化", f"{fr_full['general_rise_pct']:+.2f}%")
        out.kv("全量判定", fr_full["verdict"])

        out.blank()
        out.line("  但先别急着下结论 —— 上面这个指标被「记忆」主导了：")
        out.line(f"    基座在预训练**见过**的语料上困惑度是 {g0['ppl']:.1f}，而在**没见过**的通用文本上是 {u0['ppl']:,.1f}")
        out.line(f"    （差 {u0['ppl'] / g0['ppl']:.1f} 倍）。预训练只跑了 {_info['n_steps']} 步，这个差距说明基座")
        out.line("    对通用语料的低困惑度主要来自**记忆**而不是泛化，任何微调都会打散它。")
        out.blank()
        out.line("  换个更公允的判据 —— 看**没见过**的通用语料（真正的泛化）：")
        out.table(
            ["未见通用语料困惑度", "微调前", "微调后", "变化", "判定"],
            [["LoRA r=8", f"{u0['ppl']:,.1f}", f"{u1['ppl']:,.1f}", f"{(u1['ppl'] / u0['ppl'] - 1) * 100:+.2f}%",
              "变好" if u1["ppl"] < u0["ppl"] else "变差"],
             ["全量微调", f"{u0['ppl']:,.1f}", f"{u2['ppl']:,.1f}", f"{(u2['ppl'] / u0['ppl'] - 1) * 100:+.2f}%",
              "变好" if u2["ppl"] < u0["ppl"] else "变差"]],
            aligns=["<", ">", ">", ">", "<"],
        )
        out.line("  两者在未见通用语料上**都变好了** —— 因为 Java 答案本身也是中文技术文本，")
        out.line("  等于又给这个欠训练的基座喂了通用语料。")
        out.blank()
        out.line("  ⚠ 一个**推翻常识**的实测结果（值得写进文档）：")
        # ΔW 相对基座的幅度：本 demo 自己训出来的 adapter，不是从别处抄来的数字
        layers = [la for _p, la in lora_layers(model)]
        dw_ratio = float(np.mean([np.abs(la.scaling * (la.A.data @ la.B.data)).mean() for la in layers])
                         / np.mean([np.abs(la.W.data).mean() for la in layers]))
        out.line(f"    教科书常说「LoRA 比全量微调更抗遗忘」。本次实测相反 ——")
        out.line(f"    在预训练语料上，LoRA 涨 {fr_lora['general_rise_pct']:+.0f}%，全量只涨 {fr_full['general_rise_pct']:+.0f}%。")
        out.line("    原因不是 LoRA 本身有问题，而是：① 基座本来就欠训练，")
        out.line(f"    ② LoRA 的等效 ΔW 幅度并不小 —— 本 demo 实测 mean|ΔW|/mean|W| = {dw_ratio * 100:.1f}%，")
        out.line("       而全量微调每步只挪动一点点，反而整体偏移更小。")
        out.line("    结论：「LoRA 更抗遗忘」的前提是**基座本身泛化良好**，不能无条件相信。")
        out.blank()
        out.line("  真正值得记住的是**判据的形式**：域内必须降、通用不能涨、两者要同时看。")

        # ---------------- 7. 定性生成 ----------------
        out.subsection("7. 定性对比：同一道题，微调前后各生成一段")
        model_base, tok2, _ = ensure_base_model()
        out.line(f"  prompt: {PROMPT!r}")
        out.blank()
        out.line("  【基座（未微调）】")
        out.line(f"    {generate_text(model_base, tok2, PROMPT, max_new_tokens=40, temperature=0.8, seed=0)!r}")
        out.line("  【LoRA 微调后】")
        out.line(f"    {generate_text(model, tok2, PROMPT, max_new_tokens=40, temperature=0.8, seed=0)!r}")
        out.line("  【参考答案（数据集里的 output）】")
        out.line(f"    {recs[0]['output'][:80]}…")
        out.blank()
        out.line("  如实呈现：两段生成都是**乱码级别**的。这不是 bug —— d_model=64、2 层、")
        out.line("  预训练语料只有 1KB 量级，模型根本没有能力生成连贯中文。")
        out.line("  但它确实学会了「答案区的 token 分布」：困惑度从几万降到几百是真的。")
        out.line("  结论：**困惑度下降是必要条件，不是充分条件**；定性评测必须单独做。")

        out.subsection("8. 本 demo 的关键数字")
        out.kv("域内困惑度 微调前 → 后（LoRA）", f"{d0['ppl']:,.1f} → {d1['ppl']:,.1f}（↓{(1 - d1['ppl'] / d0['ppl']) * 100:.2f}%）")
        out.kv("通用困惑度（见过）前 → 后", f"{g0['ppl']:,.1f} → {g1['ppl']:,.1f}（{fr_lora['general_rise_pct']:+.2f}%）")
        out.kv("通用困惑度（没见过）前 → 后", f"{u0['ppl']:,.1f} → {u1['ppl']:,.1f}（{(u1['ppl'] / u0['ppl'] - 1) * 100:+.2f}%）")
        out.kv("灾难性遗忘判定（严格口径）", f"LoRA: {fr_lora['verdict']} / 全量: {fr_full['verdict']}")
        out.kv("域内困惑度：LoRA vs 全量", f"{d1['ppl']:,.1f} vs {d2['ppl']:,.1f}", "全量更低（容量更大）")
    finally:
        out.close()


if __name__ == "__main__":
    main()
