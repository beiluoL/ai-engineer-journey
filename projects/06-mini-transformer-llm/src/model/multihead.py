"""多头注意力：把 d_model 切成 h 份，每份各自算一次注意力，再拼回去。

为什么要多头：单头注意力只能学一种「该看哪里」的模式；多头让模型同时关注
语法、指代、远近等不同关系。实现上不需要 h 个独立权重——一份大 ``Wq`` 切分即可：

    Q = X @ Wq   → reshape(seq, h, d_k) → transpose(seq, h, d_k)
    对每头做 scaled_dot_product_attention，再把头拼回 (seq, d_model)
    最后过输出线性 Wo

所有 reshape / transpose 都是带反向的 autograd 算子，所以 ``Wq/Wk/Wv/Wo`` 的反向
梯度会自动正确流回。
"""

from __future__ import annotations

import numpy as np

from .autograd import (
    Module,
    Parameter,
    Tensor,
    linear,
    matmul,
    reshape,
    transpose,
)
from .attention import scaled_dot_product_attention


class MultiHeadAttention(Module):
    """多头自注意力：``X (seq, d_model)`` → ``(seq, d_model)``。"""

    def __init__(self, d_model: int, n_heads: int, scale: float = 0.02) -> None:
        if d_model % n_heads != 0:
            raise ValueError(f"d_model({d_model}) 必须能被 n_heads({n_heads}) 整除")
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        # 四个线性投影，都是 Parameter（共享一份大权重，再切头）
        self.Wq = Parameter(np.random.randn(d_model, d_model) * scale)
        self.Wk = Parameter(np.random.randn(d_model, d_model) * scale)
        self.Wv = Parameter(np.random.randn(d_model, d_model) * scale)
        self.Wo = Parameter(np.random.randn(d_model, d_model) * scale)

    def _split_heads(self, x: Tensor) -> Tensor:
        """(B, seq, d_model) → (B, n_heads, seq, d_k)（未批处理则先补 batch 维）。"""
        was_2d = x.data.ndim == 2
        if was_2d:
            x = reshape(x, (1, x.data.shape[0], self.d_model))
        B, T, _ = x.data.shape
        x = reshape(x, (B, T, self.n_heads, self.d_k))
        x = transpose(x, [0, 2, 1, 3])  # (B, n_heads, seq, d_k)
        if was_2d:
            x = reshape(x, (self.n_heads, x.data.shape[2], self.d_k))
        return x

    def _merge_heads(self, x: Tensor) -> Tensor:
        """(B, n_heads, seq, d_k) → (B, seq, d_model)（未批处理去掉 batch 维）。"""
        was_2d = x.data.ndim == 3
        if was_2d:
            x = reshape(x, (1, x.data.shape[0], x.data.shape[1], self.d_k))
        x = transpose(x, [0, 2, 1, 3])  # (B, seq, n_heads, d_k)
        B, T, _, _ = x.data.shape
        x = reshape(x, (B, T, self.d_model))
        if was_2d:
            x = reshape(x, (T, self.d_model))
        return x

    def forward(self, x: Tensor, mask: "np.ndarray | None" = None) -> Tensor:
        q = self._split_heads(linear(x, self.Wq))
        k = self._split_heads(linear(x, self.Wk))
        v = self._split_heads(linear(x, self.Wv))
        ctx = scaled_dot_product_attention(q, k, v, mask=mask)
        ctx = self._merge_heads(ctx)
        return linear(ctx, self.Wo)

    def __call__(self, x: Tensor, mask: "np.ndarray | None" = None) -> Tensor:
        return self.forward(x, mask)
