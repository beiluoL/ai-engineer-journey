#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import base_bundle  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.metrics import evaluate, perplexity  # noqa: E402


def main() -> None:
    with Printer("demo_01_evaluation") as out:
        out.section("M01 · Evaluation：困惑度之外")
        model, _tok, info, split, _train, examples = base_bundle(heldout_size=8, max_len=128)
        result = evaluate(model, examples, batch_size=2, n_bins=10)
        full_ppl = perplexity(model, examples, batch_size=2, use_mask=False)
        out.kv("基座来源", info.get("source", "unknown"))
        out.kv("held-out 样本", len(split.heldout))
        out.kv("全序列困惑度", f"{full_ppl:.4f}")
        out.kv("答案区困惑度", f"{result['ppl']:.4f}")
        out.kv("Token Accuracy", f"{result['token_accuracy']:.4%}")
        out.kv("ECE", f"{result['ece']:.4f}")
        out.kv("答案区覆盖率", f"{result['coverage']:.2%}", f"{result['answer_tokens']}/{result['total_tokens']} tokens")

        out.subsection("可靠性分箱表")
        out.table(
            ["置信区间", "样本数", "平均置信度", "实际准确率", "差距"],
            [[f"[{row['lower']:.1f}, {row['upper']:.1f}]", row["count"],
              f"{row['avg_confidence']:.4f}", f"{row['accuracy']:.4f}", f"{row['gap']:.4f}"]
             for row in result["bins"]],
            aligns=["<", ">", ">", ">", ">"],
        )
        misleading = result["token_accuracy"] > 0 and result["ece"] > 0.10
        out.subsection("结论")
        out.kv("出现“困惑度尚可但校准差”", "是" if misleading else "否")
        if result["ppl"] > 1000:
            out.line("  实测答案区困惑度仍很高；这个玩具基座既不准确，也谈不上校准良好。")
        out.line("  ECE 与可靠性表揭示概率可信度，不能由困惑度或命中率替代。")


if __name__ == "__main__":
    main()
