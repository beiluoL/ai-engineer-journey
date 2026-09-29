#!/usr/bin/env python3
"""Demo 05 —— 多头注意力：把 d_model 切成 h 份并行算注意力再拼回。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_05_multihead.py

输出同时打到 stdout 和 demos/out/demo_05_multihead.py.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import MultiHeadAttention, Tensor, causal_mask, scaled_dot_product_attention, sum  # noqa: E402

from _demo_common import run  # noqa: E402


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> int:
    np.random.seed(0)
    print("Project 06 — Mini Transformer LLM")
    print("Demo 05: Multi-Head Attention")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 构造多头注意力")
    D, H = 16, 4
    mha = MultiHeadAttention(d_model=D, n_heads=H)
    print(f"  d_model = {D}, n_heads = {H}, d_k = D/H = {D // H}")
    print(f"  线性投影权重形状（Wq/Wk/Wv/Wo 各 {D}x{D}）")
    print(f"  参数个数 : {len(mha.parameters())}  （应为 4）")

    rule("2. 未批处理输入 (seq, d_model) → (seq, d_model)")
    seq = 7
    x = Tensor(np.random.randn(seq, D))
    out = mha(x)
    print(f"  输入形状   : {x.data.shape}")
    print(f"  输出形状   : {out.data.shape}  （应等于 (seq, d_model)）")
    print(f"  输出是否有限 : {np.isfinite(out.data).all()}")

    rule("3. 批处理输入 (B, seq, d_model) → (B, seq, d_model)")
    xb = Tensor(np.random.randn(2, seq, D))
    out_b = mha(xb)
    print(f"  批输入形状 : {xb.data.shape}")
    print(f"  批输出形状 : {out_b.data.shape}")

    rule("4. 切头后逐头注意力的权重（每行和为 1）")
    qh = mha._split_heads(x)
    kh = mha._split_heads(x)
    vh = mha._split_heads(x)
    print(f"  切头后 Q 形状 : {qh.data.shape}  (n_heads, seq, d_k)")
    _, attn = scaled_dot_product_attention(qh, kh, vh, return_attn=True)
    # attn: (n_heads, seq, seq)
    for h in range(H):
        row_sums = attn[h].sum(axis=-1)
        print(f"    head {h}: 各行权重之和 = {np.round(row_sums, 6)}")
    print("  → 每个头各自学到一份注意力分布，并行、互不干扰。")

    rule("5. 梯度能流回 Wq")
    s = sum(out)
    s.backward()
    print(f"  Wq.grad 形状   : {mha.Wq.grad.shape}")
    print(f"  Wq.grad 有梯度 : {mha.Wq.grad is not None}")
    print(f"  Wq.grad 有限   : {np.isfinite(mha.Wq.grad).all()}")

    rule("Demo 05 结束")
    print("  下一步：Demo 06 —— Transformer Block（注意力 + 残差 + FFN）。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_05_multihead.txt", main))
