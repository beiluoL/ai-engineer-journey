#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _emit import Printer  # noqa: E402
from ie.evalset import build_evaluation_set  # noqa: E402
from ie.paths import ensure_deps_importable  # noqa: E402

ensure_deps_importable()
from ft import load_java_records  # noqa: E402


def main() -> None:
    with Printer("demo_03_evaluation_dataset") as out:
        out.section("M03 · Evaluation Dataset：held-out、分层与防泄漏")
        records = load_java_records()
        split = build_evaluation_set(records, heldout_size=12, seed=0)
        report = split.report
        out.kv("原始记录", report["input_size"])
        out.kv("归一化去重后", report["unique_size"])
        out.kv("去重删除", report["duplicates_removed"])
        out.kv("训练集", report["train_size"])
        out.kv("held-out", report["heldout_size"])
        out.kv("instruction 交集", report["overlap_count"])
        out.kv("泄漏检查", "通过（无交集）" if report["leakage_free"] else "失败")
        out.subsection("held-out 分层")
        out.table(
            ["主题/长度层", "样本数"],
            [[name, count] for name, count in report["heldout_strata"].items()],
            aligns=["<", ">"],
        )
        out.subsection("可复现抽样")
        again = build_evaluation_set(records, heldout_size=12, seed=0)
        same = [r["instruction"] for r in split.heldout] == [r["instruction"] for r in again.heldout]
        out.kv("同 seed 两次 held-out 完全一致", same)
        out.line("  先切 held-out、再训练 adapter；否则 P08 全量微调数据会污染评估结论。")


if __name__ == "__main__":
    main()
