"""Transformer Block：把注意力和前馈网络用残差 + LayerNorm 串起来。

一个 Block 的前向（Pre-LN 结构，训练更稳）：

    h   = x + MHA(LayerNorm(x))      # 子层 1：注意力 + 残差
    out = h + FFN(LayerNorm(h))      # 子层 2：前馈 + 残差

FFN：``Linear(d_model → d_ff) → ReLU → Linear(d_ff → d_model)``（本项目用 ReLU，
论文常用 GELU，玩具规模下 ReLU 足够，且手写更直观）。

残差连接是「让梯度直接流回浅层」的关键——没有它深层网络基本训不动。
"""

from __future__ import annotations

import numpy as np

from .autograd import Module, Parameter, Tensor, add, layernorm, linear, relu
from .multihead import MultiHeadAttention


class FeedForward(Module):
    """位置无关的前馈网络：放大 4 倍 → ReLU → 压回。"""

    def __init__(self, d_model: int, d_ff: int, scale: float = 0.02) -> None:
        self.d_model = d_model
        self.d_ff = d_ff
        self.W1 = Parameter(np.random.randn(d_model, d_ff) * scale)
        self.b1 = Parameter(np.zeros(d_ff))
        self.W2 = Parameter(np.random.randn(d_ff, d_model) * scale)
        self.b2 = Parameter(np.zeros(d_model))

    def forward(self, x: Tensor) -> Tensor:
        h = relu(linear(x, self.W1, self.b1))
        return linear(h, self.W2, self.b2)

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)


class TransformerBlock(Module):
    """一个完整的 Transformer Block。"""

    def __init__(self, d_model: int, n_heads: int, d_ff: int) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        self.ln1 = _LayerNorm(d_model)
        self.attn = MultiHeadAttention(d_model, n_heads)
        self.ln2 = _LayerNorm(d_model)
        self.ffn = FeedForward(d_model, d_ff)

    def forward(self, x: Tensor, mask: "np.ndarray | None" = None) -> Tensor:
        h = add(x, self.attn(self.ln1(x), mask))      # 注意力子层 + 残差
        out = add(h, self.ffn(self.ln2(h)))            # 前馈子层 + 残差
        return out

    def __call__(self, x: Tensor, mask: "np.ndarray | None" = None) -> Tensor:
        return self.forward(x, mask)


class _LayerNorm(Module):
    """LayerNorm 模块：包住 autograd 的 ``layernorm``，gamma/beta 是可学参数。"""

    def __init__(self, d_model: int, eps: float = 1e-5) -> None:
        self.d_model = d_model
        self.eps = eps
        self.gamma = Parameter(np.ones(d_model))
        self.beta = Parameter(np.zeros(d_model))

    def forward(self, x: Tensor) -> Tensor:
        return layernorm(x, self.gamma, self.beta, self.eps)

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)
