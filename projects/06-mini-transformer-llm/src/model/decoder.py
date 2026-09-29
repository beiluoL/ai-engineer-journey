"""DecoderStack：把 N 个 Block 堆起来，再接最终 LayerNorm + 输出投影。

输出投影 ``(d_model → vocab)`` 把每个位置的隐藏向量变成词表上的 logits，
下一步交给交叉熵算损失。到这里，整条前向链路就闭环了：

    ids → Embedding → [Block × N] → LayerNorm → 线性投影 → logits(seq, vocab)

``TransformerLM`` 是把「Embedding + DecoderStack」缝在一起的整机，训练和推理都直接用它。
"""

from __future__ import annotations

import numpy as np

from .autograd import Module, Parameter, Tensor, linear
from .block import TransformerBlock
from .embedding import PositionalEncoding, TokenEmbedding, combine


class DecoderStack(Module):
    """N 层 Transformer Block + 最终 LayerNorm + 输出投影。"""

    def __init__(self, d_model: int, n_heads: int, d_ff: int, n_layers: int, vocab_size: int) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab_size = vocab_size
        self.blocks = [TransformerBlock(d_model, n_heads, d_ff) for _ in range(n_layers)]
        self.ln_f = _FinalLayerNorm(d_model)
        self.proj = Parameter(np.random.randn(d_model, vocab_size) * 0.02)

    def forward(self, x: Tensor, mask: "np.ndarray | None" = None) -> Tensor:
        h = x
        for block in self.blocks:
            h = block(h, mask)
        h = self.ln_f(h)
        return linear(h, self.proj)  # (..., d_model) → (..., vocab)

    def __call__(self, x: Tensor, mask: "np.ndarray | None" = None) -> Tensor:
        return self.forward(x, mask)


class _FinalLayerNorm(Module):
    """最终 LayerNorm（gamma/beta 可学）。"""

    def __init__(self, d_model: int, eps: float = 1e-5) -> None:
        self.gamma = Parameter(np.ones(d_model))
        self.beta = Parameter(np.zeros(d_model))
        self.eps = eps

    def forward(self, x: Tensor) -> Tensor:
        from .autograd import layernorm

        return layernorm(x, self.gamma, self.beta, self.eps)

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)


class TransformerLM(Module):
    """整机：Embedding + 位置编码 + DecoderStack，一条前向得到 logits。"""

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        n_heads: int,
        d_ff: int,
        n_layers: int,
        max_len: int = 512,
    ) -> None:
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.max_len = max_len
        self.token_emb = TokenEmbedding(vocab_size, d_model)
        self.pos_enc = PositionalEncoding(d_model, max_len)
        self.decoder = DecoderStack(d_model, n_heads, d_ff, n_layers, vocab_size)

    def forward(self, ids: np.ndarray, mask: "np.ndarray | None" = None) -> Tensor:
        """``ids`` 形状 ``(B, seq)``，返回 logits ``(B, seq, vocab)``。

        若 ``mask`` 为 None，自动按当前序列长度生成因果掩码。
        """
        ids = np.asarray(ids, dtype=np.int64)
        seq_len = ids.shape[-1]
        if seq_len > self.max_len:
            raise ValueError(f"序列长度 {seq_len} 超过 max_len={self.max_len}")
        if mask is None:
            from .attention import causal_mask

            mask = causal_mask(seq_len)
        x = combine(self.token_emb, self.pos_enc, ids)
        return self.decoder(x, mask)

    def __call__(self, ids: np.ndarray, mask: "np.ndarray | None" = None) -> Tensor:
        return self.forward(ids, mask)

    @property
    def context_len(self) -> int:
        return self.max_len
