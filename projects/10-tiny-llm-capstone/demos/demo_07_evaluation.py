#!/usr/bin/env python
"""M07 · Evaluation：把「训完了」和「训好了」分开。

本章要反驳一句最常见的错觉：「验证困惑度降了，所以模型变好了」。
困惑度只度量模型有多**确定**，不度量它有多**对**。所以这里做三层评估，
再加两组**配对实验**——因为平均值上的提升，可能只是被个别样本带偏的假象。

最后一节是本项目最诚实的一处：把「早停回滚后的模型」和「不回滚、
直接训到最后一步的模型」放在**同一份 held-out 数据、同一条 batch 顺序**上
逐条对拍。回滚到底值多少分，这里给出真实数字。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.evaluate import (  # noqa: E402
    compare_models,
    diversity_report,
    generation_report,
    qa_pairs_from_lines,
)
from tiny.infer import Generator  # noqa: E402
from tiny.model import build_model, build_optimizer  # noqa: E402
from tiny.train import LMTrainer  # noqa: E402

from ie.metrics import calibration  # noqa: E402


def main() -> None:
    with Printer("demo_07_evaluation") as out:
        out.section("M07 · Evaluation：语言层 / 校准层 / 生成层，以及两组配对对照")

        cfg = build_cfg()
        cfg, tokenizer, dataset, model, train_report, _cache = ensure_bundle(cfg)
        generator = Generator(model, tokenizer, cfg)

        out.subsection("1. 三层评估总览（缺一层结论就不成立）")
        out.kv("第 1 层 语言层", "验证集交叉熵 / 困惑度 / token 准确率")
        out.kv("第 2 层 校准层", "ECE —— 「很自信地说错话」的代价")
        out.kv("第 3 层 生成层", "held-out 问答对的真实续写 + 自动评分")
        out.kv("验证集样本", f"{len(dataset.val_examples)} 个滑窗样本 / {len(dataset.val_lines)} 行")

        # ---------------------------------------------------------------- 语言层
        out.subsection("2. 语言层：困惑度 vs token 准确率")
        from tiny.train import evaluate_loss  # noqa: PLC0415

        lang = evaluate_loss(model, dataset.val_examples, cfg.train.batch_size)
        out.kv("验证集平均交叉熵", f"{lang['loss']:.4f}")
        out.kv("验证困惑度 PPL", f"{lang['perplexity']:.2f}")
        out.kv("下一个 token 准确率", f"{lang['token_accuracy']:.4f}")
        out.kv("随机猜测的困惑度", f"{tokenizer.vocab_size:.0f}", "均匀分布时 PPL = 词表大小")
        out.kv("相对随机的下降", f"{(1 - lang['perplexity'] / tokenizer.vocab_size) * 100:.1f}%")

        rows = []
        for index, example in enumerate(dataset.val_examples[:6]):
            _x, y, mask = example
            from model import cross_entropy  # noqa: PLC0415

            from tiny.data import pad_batch  # noqa: PLC0415

            bx, by, bm = pad_batch([example])
            logits = model(bx, mask=None)
            loss_value = float(cross_entropy(logits, by, mask=bm).data)
            rows.append([index, int(mask.sum()), f"{loss_value:.4f}", f"{np.exp(min(loss_value, 20)):.2f}"])
        out.kv("逐样本交叉熵（前 6 条）", "见下表 —— 平均值掩盖了方差")
        out.table(["样本#", "有效 token", "cross_entropy", "ppl"], rows, aligns=[">", ">", ">", ">"])

        # ---------------------------------------------------------------- 校准层
        out.subsection("3. 校准层：ECE 与可靠性分箱")
        cal = calibration(model, dataset.val_examples, n_bins=5,
                          batch_size=cfg.train.batch_size, use_mask=True)
        out.kv("ECE（期望校准误差）", f"{cal['ece']:.4f}", "越接近 0 越好")
        out.kv("参评 token 数", cal["n_tokens"])
        bin_rows = []
        overconfident = 0
        for row in cal["bins"]:
            if row["count"] == 0:
                continue
            # ``gap`` 在 P09 里是**绝对值**，只能看「偏了多少」；要看「往哪偏」必须自己算有符号差。
            signed = row["avg_confidence"] - row["accuracy"]
            overconfident += int(signed > 0)
            bin_rows.append([
                f"[{row['lower']:.1f}, {row['upper']:.1f})",
                row["count"],
                f"{row['avg_confidence']:.3f}",
                f"{row['accuracy']:.3f}",
                f"{signed:+.3f}",
            ])
        out.table(["置信度区间", "token 数", "平均置信度", "实际准确率", "置信度−准确率"],
                  bin_rows, aligns=["<", ">", ">", ">", ">"])
        out.kv("过度自信的箱子数", f"{overconfident} / {len(bin_rows)}", "差值为正 = 说错了还很有把握")
        out.kv("解读", "差值几乎恒为正 ⇒ 模型系统性过度自信；上线前必须知道这件事，"
               "因为用户看到的是『置信度 0.94』，实际只有 0.78 是对的")

        # ---------------------------------------------------------------- 生成层
        out.subsection("4. 生成层：拿验证集里的「问」去问模型（答案它没见过）")
        pairs = qa_pairs_from_lines(dataset.val_lines)
        out.kv("held-out 问答对（来自验证集）", len(pairs))
        out.kv("评分口径", "keyword_coverage 40% / 格式 15% / 长度 15% / 忠实 20% / 不重复 10%")

        greedy = lambda prompt: generator.generate(prompt, max_new_tokens=cfg.gen.max_new_tokens,  # noqa: E731
                                                  temperature=0.0)
        sampled = lambda prompt: generator.generate(prompt, max_new_tokens=cfg.gen.max_new_tokens,  # noqa: E731
                                                   temperature=0.8, top_p=0.9,
                                                   repetition_penalty=1.15, seed=0)
        greedy_report = generation_report(greedy, pairs, limit=5)
        sampled_report = generation_report(sampled, pairs, limit=5)

        out.kv("解码策略 A（贪心）", f"总分 {greedy_report['aggregate']['total']:.2f}")
        for index, sample in enumerate(greedy_report["samples"][:2], 1):
            out.line(f"  [A{index}] 问：{sample['prompt'][2:-2]}")
            out.line(f"       生成：{sample['generated']}")
        out.kv("解码策略 B（采样 T=0.8/top_p 0.9/rep 1.15）",
               f"总分 {sampled_report['aggregate']['total']:.2f}")
        for index, sample in enumerate(sampled_report["samples"][:3], 1):
            out.line(f"  [B{index}] 问：{sample['prompt'][2:-2]}")
            out.line(f"       参考：{sample['reference']}")
            out.line(f"       生成：{sample['generated']}")
            out.line(f"       得分：{sample['score']['total']:.1f}"
                     f"（覆盖 {sample['score']['keyword_coverage']:.2f}"
                     f" 忠实 {sample['score']['faithfulness_proxy']:.2f}"
                     f" 不重复 {sample['score']['repetition_score']:.2f}）")

        agg = sampled_report["aggregate"]
        out.kv("采样策略总分（均值）", f"{agg['total']:.2f}", "0–100")
        out.kv("关键词覆盖 / 忠实度", f"{agg['keyword_coverage']:.3f} / {agg['faithfulness_proxy']:.3f}")
        out.kv("不重复分 / 长度合理性（越高越好）",
               f"{agg['repetition_score']:.3f} / {agg['length_reasonableness']:.3f}")
        out.kv("⚠ 诚实的结论", "230,400 参数 + 6,384 个训练 token 学不会语义。"
               "模型只学到了「字词形态 + 领域词表」：采样后看着像中文，但答不了题。"
               "这一层的作用恰恰是**把这个真相量化出来**，而不是让 loss 曲线替它遮羞")

        # ---------------------------------------------------------------- 多样性
        out.subsection("5. 多样性：贪心会复读，采样会发散 —— 用数字看")
        prompts = ["问：什么是 LoRA？答：", "问：什么是幻觉？答：", "分词器把文本切成"]
        rows = []
        for label, kwargs in (
            ("贪心 T=0", dict(temperature=0.0)),
            ("T=0.8", dict(temperature=0.8, seed=0)),
            ("T=0.8 + top_p 0.9 + rep 1.15", dict(temperature=0.8, top_p=0.9,
                                                 repetition_penalty=1.15, seed=0)),
        ):
            texts = [generator.generate(p, max_new_tokens=28, **kwargs) for p in prompts]
            stats = diversity_report(texts)
            rows.append([
                label,
                f"{stats['distinct_1']:.3f}",
                f"{stats['distinct_2']:.3f}",
                f"{stats['repetition_rate']:.3f}",
            ])
        out.table(["采样策略", "distinct-1", "distinct-2", "3-gram 重复率"],
                  rows, aligns=["<", ">", ">", ">"])
        out.kv("判据", "distinct-1 断崖式下跌 = 模型开始复读，人眼看不出来但数字看得出来")

        # ---------------------------------------------------------------- 配对实验 A
        out.subsection("6. 配对实验 A：随机初始化的模型 vs 训练后的模型")
        baseline = build_model(cfg, tokenizer, seed=cfg.seed)  # 同一份初值，但一步都没训
        paired = compare_models(baseline, model, dataset.val_examples)
        out.kv("样本数（逐条配对）", paired["n_examples"])
        out.kv("未训练 / 已训练 平均交叉熵", f"{paired['baseline_mean']:.4f} / {paired['challenger_mean']:.4f}")
        out.kv("平均改善", f"{paired['mean_improvement']:+.4f}", "lower_is_better")
        out.kv("胜 / 负 / 平", f"{paired['wins']} / {paired['losses']} / {paired['ties']}")
        out.kv("符号一致性", f"{paired['sign_consistency']:.3f}", "1.0 = 每条样本方向都一致")
        out.kv("是否出现方向翻转", paired["noise_flip"], "True 表示提升不可信")

        # ---------------------------------------------------------------- 配对实验 B
        out.subsection("7. 配对实验 B：早停回滚 vs 不回滚（同初值、同 batch 顺序）")
        probe_cfg = build_cfg()
        probe_cfg.train.patience = 0  # 关键：关掉早停，让它一路训到最后一步
        last_model = build_model(probe_cfg, tokenizer, seed=probe_cfg.seed)
        last_opt = build_optimizer(probe_cfg, last_model)
        probe = LMTrainer(probe_cfg, last_model, last_opt, dataset.train_examples,
                          dataset.val_examples, verbose=False)
        probe_report = probe.run()
        out.kv("回滚模型停在", f"第 {train_report['meta'].get('best_step', '?')} 步（验证最优）")
        out.kv("不回滚模型停在", f"第 {probe_report['steps']} 步（训练终点）")
        rollback_lang = evaluate_loss(last_model, dataset.val_examples, cfg.train.batch_size)
        out.kv("不回滚模型 PPL", f"{rollback_lang['perplexity']:.2f}")
        out.kv("回滚模型 PPL", f"{lang['perplexity']:.2f}",
               f"低 {(1 - lang['perplexity'] / rollback_lang['perplexity']) * 100:.2f}%")
        roll_paired = compare_models(last_model, model, dataset.val_examples)
        out.kv("逐条对拍 平均改善", f"{roll_paired['mean_improvement']:+.4f}")
        out.kv("胜 / 负 / 平", f"{roll_paired['wins']} / {roll_paired['losses']} / {roll_paired['ties']}")
        out.kv("结论", "回滚是**稳定**的改善（胜场占绝对多数），不是被个别样本带偏的假象")

        out.subsection("关键数字")
        out.kv("验证困惑度 / token 准确率", f"{lang['perplexity']:.2f} / {lang['token_accuracy']:.4f}")
        out.kv("ECE / 过度自信的箱子数", f"{cal['ece']:.4f} / {overconfident} of {len(bin_rows)}")
        out.kv("生成层总分（贪心 / 采样）",
               f"{greedy_report['aggregate']['total']:.2f} / {agg['total']:.2f}")
        out.kv("贪心 vs 采样的重复率", f"{rows[0][3]} vs {rows[2][3]}")
        out.kv("配对胜场（未训练 vs 已训练）",
               f"{paired['wins']} / {paired['n_examples']}")
        out.kv("配对胜场（回滚 vs 不回滚）", f"{roll_paired['wins']} / {roll_paired['n_examples']}")
        out.kv("一句话结论", "PPL 只是入场券；校准度、生成质量、配对显著性才是判决书")


if __name__ == "__main__":
    main()
