#!/usr/bin/env python3
"""Demo 06 —— Transformer Block：注意力 + 残差 + LayerNorm + FFN。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_06_block.py

输出同时打到 stdout 和 demos/out/demo_06_block.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import FeedForward, Tensor, TransformerBlock, sum  # noqa: E402

from _demo_common import run  # noqa: E402


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> int:
    np.random.seed(0)
    print("Project 06 — Mini Transformer LLM")
    print("Demo 06: Transformer Block")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 构造一个 Block")
    D, H, FF = 16, 4, 32
    blk = TransformerBlock(d_model=D, n_heads=H, d_ff=FF)
    print(f"  d_model={D}, n_heads={H}, d_ff={FF}")
    print(f"  子模块：ln1 / attn / ln2 / ffn")
    print(f"  参数个数 : {len(blk.parameters())}")

    rule("2. 前向：形状自洽")
    seq = 7
    x = Tensor(np.random.randn(seq, D))
    y = blk(x)
    print(f"  输入形状   : {x.data.shape}")
    print(f"  输出形状   : {y.data.shape}  （应等于 (seq, d_model)）")

    rule("3. 残差连接：输出 = 子层输出 + 输入")
    # 把注意力子层临时置零，看残差是否保留输入
    blk.attn.Wq.data[:] = 0.0
    blk.attn.Wk.data[:] = 0.0
    blk.attn.Wv.data[:] = 0.0
    blk.attn.Wo.data[:] = 0.0
    blk.ffn.W1.data[:] = 0.0
    blk.ffn.W2.data[:] = 0.0
    # LN 是恒等（gamma=1,beta=0）时，子层全零 → 残差应≈输入（再经最终 ln 之前）
    y_zero = blk(x)
    print(f"  子层全零时，输出是否仍有限 : {np.isfinite(y_zero.data).all()}")
    print(f"  子层全零时，输出与输入是否接近（残差生效）: "
          f"{np.allclose(y_zero.data, x.data, atol=1e-4)}")

    rule("4. 前馈网络（FFN）中间形状")
    ffn = FeedForward(d_model=D, d_ff=FF)
    h = ffn(x)
    print(f"  FFN 输入 形状 : {x.data.shape}")
    print(f"  FFN 输出 形状 : {h.data.shape}  （d_model → d_ff → d_model）")
    print(f"  FFN 中间放大倍数 d_ff/d_model = {FF // D}")

    rule("5. 梯度流")
    s = sum(y)
    s.backward()
    all_grad = all(p.grad is not None for p in blk.parameters())
    print(f"  Block 内所有参数都拿到梯度 : {all_grad}")

    rule("Demo 06 结束")
    print("  下一步：Demo 07 —— DecoderStack（堆叠 N 层 + 输出投影 → logits）。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_06_block.txt", main))
