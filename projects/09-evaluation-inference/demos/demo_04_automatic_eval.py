#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import data_split  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.autoeval import derive_keywords, rank_answers  # noqa: E402


def main() -> None:
    with Printer("demo_04_automatic_eval") as out:
        out.section("M04 · Automatic Evaluation：零 LLM 的规则化评分")
        records = data_split(heldout_size=8).heldout[:5]
        refs = [record["output"] for record in records]
        keywords = [derive_keywords(reference, limit=6) for reference in refs]
        candidates = {
            "参考答案": refs,
            "首句摘要": [reference.split("。")[0] + "。" for reference in refs],
            "重复回答": [(reference[:20] + "。") * 6 for reference in refs],
            "空回答": ["" for _ in refs],
        }
        ranking = rank_answers(candidates, refs, keywords)
        out.kv("评估题数", len(refs))
        out.kv("评分器", "关键词40% + 格式15% + 长度15% + 忠实度20% + 去重复10%")
        out.subsection("自动评分排行")
        out.table(
            ["排名", "候选", "总分", "关键词", "格式", "长度", "忠实度", "去重复"],
            [[index, row["model"], f"{row['total']:.2f}",
              f"{row['keyword_coverage']:.3f}", f"{row['format_compliance']:.3f}",
              f"{row['length_reasonableness']:.3f}", f"{row['faithfulness_proxy']:.3f}",
              f"{row['repetition_score']:.3f}"] for index, row in enumerate(ranking, 1)],
            aligns=[">", "<", ">", ">", ">", ">", ">", ">"],
        )
        out.subsection("结论")
        out.kv("最高分", f"{ranking[0]['model']} {ranking[0]['total']:.2f}")
        out.kv("最低分", f"{ranking[-1]['model']} {ranking[-1]['total']:.2f}")
        out.line("  重复度惩罚让“堆关键词但反复复读”的回答无法靠长度刷分。")


if __name__ == "__main__":
    main()
