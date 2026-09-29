"""Embedding 层：把 token 的 id 变成向量，再叠上位置编码。

数据流向（来自架构契约）：``id → (n, d_model)``。

两个细节值得说清楚：
1. **查表也要能回传梯度**。如果我用 ``W[id]`` 这种花式索引，反向会很麻烦。
   这里用 ``one-hot(id) @ W``：one-hot 是常量，``W`` 是 Parameter，于是权重梯度
   自动变成「把对应位置的梯度.scatter 回那一行」—— 这正是 Embedding 该有的行为，
   还不用手写 scatter/gather。
2. **位置编码是固定的正弦函数，不是可学参数**。它只是给每个位置一个唯一「指纹」，
   让模型能区分「猫吃鱼」和「鱼吃猫」。所以它是常量 Tensor，不进 ``parameters()``。
"""

from __future__ import annotations

import numpy as np

from .autograd import Parameter, Tensor, add, matmul


def _one_hot(ids: np.ndarray, vocab_size: int) -> np.ndarray:
    """把 id 数组变成 one-hot（保持前导 batch 维，最后一维是 vocab）。"""
    ids = np.asarray(ids, dtype=np.int64)
    if ids.ndim == 1:
        oh = np.zeros((ids.shape[0], vocab_size), dtype=np.float64)
        oh[np.arange(ids.shape[0]), ids] = 1.0
    else:  # (B, T)
        B, T = ids.shape
        oh = np.zeros((B, T, vocab_size), dtype=np.float64)
        oh[np.arange(B)[:, None], np.arange(T)[None, :], ids] = 1.0
    return oh


class TokenEmbedding:
    """词嵌入：``(V, d_model)`` 权重，按 id 取行 → ``(..., d_model)``。"""

    def __init__(self, vocab_size: int, d_model: int, scale: float = 0.02) -> None:
        self.vocab_size = vocab_size
        self.d_model = d_model
        # 小初始化，避免一上来 softmax 就饱和
        self.weight = Parameter(np.random.randn(vocab_size, d_model) * scale)

    def forward(self, ids: np.ndarray) -> Tensor:
        """``ids`` 是 ``(seq,)`` 或 ``(B, seq)`` 的整数数组，返回嵌入 Tensor。"""
        ids = np.asarray(ids, dtype=np.int64)
        oh = Tensor(_one_hot(ids, self.vocab_size))  # 常量
        return matmul(oh, self.weight)

    def __call__(self, ids: np.ndarray) -> Tensor:
        return self.forward(ids)


class PositionalEncoding:
    """正弦位置编码：``pe[pos, 2i] = sin(pos/10000^(2i/d))``，固定、不可学。"""

    def __init__(self, d_model: int, max_len: int = 512) -> None:
        self.d_model = d_model
        self.max_len = max_len
        # 预计算整张表，用的时候切片；这是常量，不进参数表
        pe = np.zeros((max_len, d_model), dtype=np.float64)
        pos = np.arange(max_len)[:, None].astype(np.float64)
        div = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
        pe[:, 0::2] = np.sin(pos * div)
        pe[:, 1::2] = np.cos(pos * div[: (d_model + 1) // 2])
        self.pe = pe

    def forward(self, seq_len: int) -> Tensor:
        """返回 ``(seq_len, d_model)`` 的常量位置编码，可广播到 batch。"""
        if seq_len > self.max_len:
            raise ValueError(f"序列长度 {seq_len} 超过 max_len={self.max_len}")
        return Tensor(self.pe[:seq_len], requires_grad=False)

    def __call__(self, seq_len: int) -> Tensor:
        return self.forward(seq_len)


def combine(
    token_emb: TokenEmbedding,
    pos_enc: PositionalEncoding,
    ids: np.ndarray,
) -> Tensor:
    """把 token 嵌入和位置编码加起来：``x = TokenEmb(ids) + PosEnc(len(ids))``。

    位置编码是 ``(seq, d_model)``，token 嵌入是 ``(B, seq, d_model)``，
    ``add`` 会自然把位置编码广播到整个 batch。
    """
    ids = np.asarray(ids, dtype=np.int64)
    seq_len = ids.shape[-1]
    x_tok = token_emb(ids)
    x_pos = pos_enc(seq_len)
    return add(x_tok, x_pos)
