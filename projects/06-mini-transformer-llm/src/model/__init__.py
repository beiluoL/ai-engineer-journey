"""Project 06 —— model 包：从零手写的 Decoder-Only Transformer。

    from model import (
        Tensor, Parameter, Module,           # 自动微分基础
        matmul, add, mul, sub, sum, mean, log, softmax, cross_entropy, layernorm,
        grad_check,
        TokenEmbedding, PositionalEncoding, combine,
        scaled_dot_product_attention, causal_mask,
        MultiHeadAttention,
        TransformerBlock, FeedForward,
        DecoderStack, TransformerLM,
        build_examples, examples_from_lines, DataLoader,
        SGD, Adam, Trainer,
        generate,
    )

所有算子都是 numpy 实现，没有 torch。维度约定见 milestones/01-project-architecture.md。
"""

from __future__ import annotations

from .autograd import (
    Module,
    Parameter,
    Tensor,
    add,
    cross_entropy,
    div,
    grad_check,
    layernorm,
    log,
    matmul,
    mean,
    mul,
    neg,
    relu,
    reshape,
    softmax,
    sub,
    sum,
    transpose,
)
from .embedding import PositionalEncoding, TokenEmbedding, combine
from .attention import causal_mask, scaled_dot_product_attention
from .multihead import MultiHeadAttention
from .block import FeedForward, TransformerBlock
from .decoder import DecoderStack, TransformerLM
from .dataloader import DataLoader, build_examples, examples_from_lines
from .training import Adam, SGD, Trainer
from .inference import generate, generate_ids, logits_of_prefix

__all__ = [
    "Tensor",
    "Parameter",
    "Module",
    "grad_check",
    "matmul",
    "add",
    "mul",
    "sub",
    "div",
    "neg",
    "sum",
    "mean",
    "log",
    "relu",
    "softmax",
    "transpose",
    "reshape",
    "layernorm",
    "cross_entropy",
    "TokenEmbedding",
    "PositionalEncoding",
    "combine",
    "causal_mask",
    "scaled_dot_product_attention",
    "MultiHeadAttention",
    "FeedForward",
    "TransformerBlock",
    "DecoderStack",
    "TransformerLM",
    "build_examples",
    "examples_from_lines",
    "DataLoader",
    "SGD",
    "Adam",
    "Trainer",
    "generate",
    "generate_ids",
    "logits_of_prefix",
]
