#!/usr/bin/env python3
"""Demo 08 —— DataLoader：滑动窗口做自回归 + 批处理补齐。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_08_dataloader.py

输出同时打到 stdout 和 demos/out/demo_08_dataloader.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import DataLoader, build_examples, examples_from_lines  # noqa: E402
from tokenizer import BPETokenizer  # noqa: E402
from tokenizer.sample_corpus import SAMPLE_CORPUS  # noqa: E402

from _demo_common import run  # noqa: E402


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> int:
    np.random.seed(0)
    print("Project 06 — Mini Transformer LLM")
    print("Demo 08: DataLoader（滑动窗口 + 批处理 + 补齐）")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 滑动窗口：用前 L 个 token 预测第 L+1 个")
    ids = list(range(12))
    ex = build_examples(ids, context_len=5)
    print(f"  id 序列长度 = {len(ids)}，context_len = 5")
    print(f"  滑窗样本数 = {len(ex)}  （应 = 12 - 5 = 7）")
    print("  前 3 个样本（x 预测 y，逐位错开）：")
    for i, (x, y) in enumerate(ex[:3]):
        print(f"    #{i}  x={x.tolist()}  →  y={y.tolist()}")

    rule("2. 多行语料 → 变长样本（batch 内需要补齐）")
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    lines = SAMPLE_CORPUS.splitlines()[:5]
    id_lines = [tok.encode(ln) for ln in lines if ln.strip()]
    ex_lines = examples_from_lines(id_lines, context_len=16)
    print(f"  取前 5 行语料，context_len=16")
    print(f"  变长样本总数 = {len(ex_lines)}")
    print(f"  各样本长度：{[len(x) for x, _ in ex_lines]}  （长短不一 → 需补齐）")

    rule("3. 批处理 + 补齐到 batch 内最长，并给 mask")
    # 用一对人为构造的变长样本，直观看补齐
    toy = [
        (np.array([1, 2, 3]), np.array([2, 3, 4])),
        (np.array([5, 6, 7, 8, 9]), np.array([6, 7, 8, 9, 10])),
    ]
    dl = DataLoader(toy, batch_size=2, pad_id=0, shuffle=False)
    X, Y, M = next(iter(dl))
    print(f"  batch 内最长序列 = 5 → X/Y 形状 = {X.shape}")
    print("  X (右侧用 pad_id=0 补齐)：")
    print("    " + str(X.tolist()))
    print("  Y：")
    print("    " + str(Y.tolist()))
    print("  mask（1=真实 token，0=pad，pad 不计入 loss）：")
    print("    " + str(M.tolist()))

    rule("4. 真实语料上的 DataLoader 一个 batch")
    dl2 = DataLoader(ex_lines, batch_size=4, pad_id=0, shuffle=False)
    X2, Y2, M2 = next(iter(dl2))
    print(f"  batch 形状 : X={X2.shape}, Y={Y2.shape}, mask={M2.shape}（三者一致）")
    print(f"  batch 内最长序列长度 : {X2.shape[1]}")
    print(f"  真实 token 占比 : {M2.sum() / M2.size:.1%}")

    rule("Demo 08 结束")
    print("  下一步：Demo 09 —— 训练循环（loss 必须肉眼可见地下降）。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_08_dataloader.txt", main))
