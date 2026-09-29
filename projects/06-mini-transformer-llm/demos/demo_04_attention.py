#!/usr/bin/env python3
"""Demo 04 —— 注意力机制：缩放点积注意力 + 因果掩码。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_04_attention.py

输出同时打到 stdout 和 demos/out/demo_04_attention.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import Tensor, causal_mask, scaled_dot_product_attention  # noqa: E402

from _demo_common import run  # noqa: E402


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> int:
    np.random.seed(0)
    print("Project 06 — Mini Transformer LLM")
    print("Demo 04: Attention（scaled_dot_product_attention + causal_mask）")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 因果掩码：挡住未来")
    T = 6
    m = causal_mask(T)
    print(f"  序列长度 T = {T}，掩码形状 {m.shape}")
    print("  掩码矩阵（下三角=0，上三角=-inf）：")
    for row in m:
        cells = ["  -inf" if np.isneginf(v) else f"{v:5.1f}" for v in row]
        print("    " + " ".join(cells))
    lower = np.tril(np.ones((T, T), dtype=bool), k=-1)
    upper = np.triu(np.ones((T, T), dtype=bool), k=1)
    print(f"  下三角全为 0 : {np.all(m[lower] == 0)}")
    print(f"  上三角全为 -inf : {np.all(np.isneginf(m[upper]))}")

    rule("2. 缩放点积注意力：scores = QKᵀ/√d_k → softmax → ·V")
    seq, d_k = 6, 8
    q = Tensor(np.random.randn(seq, d_k))
    k = Tensor(np.random.randn(seq, d_k))
    v = Tensor(np.random.randn(seq, d_k))
    out, attn = scaled_dot_product_attention(q, k, v, return_attn=True)
    print(f"  Q/K/V 形状    : ({seq}, {d_k})")
    print(f"  注意力权重形状 : {attn.shape}  (seq, seq)")
    print(f"  输出形状       : {out.data.shape}")
    print(f"  每行注意力权重之和（应≈1）：{np.round(attn.sum(axis=-1), 6)}")
    print("  注意力权重矩阵（每行是一个分布）：")
    for i, row in enumerate(attn):
        print("    pos %d: " % i + " ".join(f"{w:.3f}" for w in row))

    rule("3. 加因果掩码后：未来位置权重被压成 0")
    out_c, attn_c = scaled_dot_product_attention(q, k, v, mask=causal_mask(seq), return_attn=True)
    print(f"  上三角权重最大值（应≈0）：{attn_c[upper].max():.2e}")
    print("  加掩码后的注意力矩阵（第 0 行只能看自己，第 5 行能看全部）：")
    for i, row in enumerate(attn_c):
        print("    pos %d: " % i + " ".join(f"{w:.3f}" for w in row))

    rule("4. 缩放的作用：除以 √d_k 防止点积过大导致 softmax 饱和")
    # 不缩放时 scores 量级 ~ d_k；缩放后 ~ 1
    scores_unscaled = (q.data @ k.data.T)
    scores_scaled = scores_unscaled / np.sqrt(d_k)
    print(f"  未缩放 scores 典型量级 |max| = {np.abs(scores_unscaled).max():.3f}")
    print(f"  缩放后 scores 典型量级 |max| = {np.abs(scores_scaled).max():.3f}")
    print("  → 缩放让 softmax 不至于过早饱和，梯度才流得动。")

    rule("Demo 04 结束")
    print("  下一步：Demo 05 —— 多头注意力（把 d_model 切成 h 份）。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_04_attention.txt", main))
