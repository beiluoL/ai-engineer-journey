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
from ie.benchmark import Benchmark, tasks_from_records  # noqa: E402


def main() -> None:
    with Printer("demo_02_benchmark") as out:
        out.section("M02 · Benchmark：任务定义、统一打分与排行")
        heldout = data_split(heldout_size=8).heldout[:6]
        benchmark = Benchmark("Java held-out v1", tasks_from_records(heldout))
        references = {record["instruction"]: record["output"] for record in heldout}

        def reference(prompt: str) -> str:
            return references[prompt]

        def concise(prompt: str) -> str:
            text = references[prompt]
            first = text.split("。")[0]
            return first + "。"

        def weak(_prompt: str) -> str:
            return "Java 中需要根据具体情况分析。"

        ranking = benchmark.compare({"参考答案": reference, "首句摘要": concise, "弱基线": weak})
        out.kv("任务集", benchmark.name)
        out.kv("任务数", len(benchmark.tasks))
        out.kv("主题数", len({task.topic for task in benchmark.tasks}))
        out.subsection("总分排行（全部由规则评分真实计算）")
        out.table(
            ["排名", "模型", "总分", "关键词", "格式", "长度", "忠实度", "去重复"],
            [[row["rank"], row["model"], f"{row['total']:.2f}",
              f"{row['keyword_coverage']:.3f}", f"{row['format_compliance']:.3f}",
              f"{row['length_reasonableness']:.3f}", f"{row['faithfulness_proxy']:.3f}",
              f"{row['repetition_score']:.3f}"] for row in ranking],
            aligns=[">", "<", ">", ">", ">", ">", ">", ">"],
        )
        out.subsection("结论")
        out.kv("第一名", f"{ranking[0]['model']}（{ranking[0]['total']:.2f}）")
        out.line("  同一任务、同一评分函数、同一汇总口径，模型间结果才可比较。")


if __name__ == "__main__":
    main()
