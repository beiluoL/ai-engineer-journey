"""注意力机制：Transformer 的心脏。

核心公式就一句（``scaled_dot_product_attention``）：

    scores = Q @ K^T / sqrt(d_k) + mask
    attn   = softmax(scores)          # 每行是一个「注意力分布」，和为 1
    out    = attn @ V

``mask`` 用来挡住「未来」：解码器做自回归，第 i 个 token 只能看 0..i，
不能偷看 i+1 之后。本项目用上三角全 ``-inf`` 的因果掩码实现（softmax 遇 -inf → 0）。

形状约定（和真实 DL 一致）：
- 未批处理：``Q,K,V`` 都是 ``(seq, d_k)``，输出 ``(seq, d_k)``。
- 批处理：``(B, seq, d_k)``，输出 ``(B, seq, d_k)``。
全部走 autograd 的 ``matmul`` / ``softmax`` / ``add``，梯度自动通。
"""

from __future__ import annotations

import numpy as np

from .autograd import Tensor, add, matmul, softmax, transpose


def causal_mask(seq_len: int) -> np.ndarray:
    """生成因果掩码：下三角（含对角线）为 0，上三角为 -inf。

    加到 ``scores`` 上之后，未来位置的注意力权重在 softmax 后被压成 0。

    注意不能用 ``0 * -np.inf``（numpy 里是 nan），所以用 ``np.where`` 精确赋值。
    """
    m = np.triu(np.ones((seq_len, seq_len), dtype=np.float64), k=1)
    return np.where(m == 1.0, -np.inf, 0.0).astype(np.float64)


def scaled_dot_product_attention(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    mask: "np.ndarray | None" = None,
    scale: "float | None" = None,
    return_attn: bool = False,
) -> "Tensor | tuple[Tensor, np.ndarray]":
    """缩放点积注意力。``q,k,v`` 形状 ``(..., seq, d_k)``，输出同形。

    ``return_attn=True`` 时额外返回注意力权重矩阵 ``(..., seq, seq)``
    —— 它的每一行是一个softmax分布、和为 1，是验证「注意力」语义的关键。
    """
    d_k = q.data.shape[-1]
    # Q @ K^T / sqrt(d_k)
    scores = matmul(q, transpose(k, list(range(k.data.ndim - 2)) + [k.data.ndim - 1, k.data.ndim - 2]))
    scores = scores * (1.0 / np.sqrt(d_k) if scale is None else 1.0 / scale)
    if mask is not None:
        scores = add(scores, Tensor(np.asarray(mask, dtype=np.float64)))
    attn = softmax(scores, axis=-1)
    out = matmul(attn, v)
    if return_attn:
        return out, attn.data
    return out
