"""Milestone 04（Embedding）+ Milestone 05（Transformer Block）—— 模型装配与自检。

P06 已经把 Embedding / Attention / Multi-Head / Block / Decoder 全都手写实现并
验证过了，所以本模块**一行结构代码都不重写**，只做三件「工程侧」的事：

1. **按配置装配**：:func:`build_model` 是模型唯一的构造入口，
   ``vocab_size`` 从分词器来、``seed`` 从配置来，杜绝「同一份配置两次建出两个模型」。
2. **参数账本**：:func:`parameter_report` 把参数按组件拆开。
   这一步看着像记账，实际上是**第一个能发现配置写错的探针** ——
   你会发现 Embedding + 输出投影就占了 Tiny LLM 的六成参数，
   于是「把 d_model 调大」到底贵在哪，一眼就有答案。
3. **结构自检**：:func:`forward_sanity` 用三个不变量证明这台机器是**因果**的、
   **确定**的、**不越界**的。其中因果性最关键 ——
   注意力掩码写错了模型照样能训、loss 照样会降，只是偷偷看到了答案。

维度约定（沿用 P06）：``ids`` 形状 ``(B, T)`` → logits 形状 ``(B, T, V)``。
"""

from __future__ import annotations

import numpy as np

from .config import TinyConfig, resolve_vocab_size

from model import Adam, SGD, TransformerLM  # noqa: E402
from model.autograd import Parameter  # noqa: E402

__all__ = [
    "build_model",
    "build_optimizer",
    "forward_sanity",
    "parameter_report",
    "set_seed",
    "walk_parameters",
]


def set_seed(seed: int) -> None:
    """固定 numpy 全局随机源。

    注意：这只管住**新建参数**的初值。训练过程的随机性（batch 顺序、采样）
    由 :class:`random.Random` / ``np.random.default_rng(seed)`` 各自带种子控制。
    """
    np.random.seed(int(seed))


def build_model(cfg: TinyConfig, tokenizer=None, seed: "int | None" = None) -> TransformerLM:
    """按配置构造 :class:`TransformerLM`（唯一的模型构造入口）。"""
    if tokenizer is not None:
        resolve_vocab_size(cfg, tokenizer)
    if cfg.model.vocab_size <= 0:
        raise ValueError(
            "model.vocab_size 还没有确定：请先传入分词器，或显式配置 model.vocab_size"
        )
    cfg.validate()
    set_seed(cfg.seed if seed is None else seed)
    return TransformerLM(
        vocab_size=cfg.model.vocab_size,
        d_model=cfg.model.d_model,
        n_heads=cfg.model.n_heads,
        d_ff=cfg.model.d_ff,
        n_layers=cfg.model.n_layers,
        max_len=cfg.model.max_len,
    )


def build_optimizer(cfg: TinyConfig, model: TransformerLM):
    """按配置构造优化器（P06 手写的 SGD / Adam）。"""
    params = [p for _name, p in walk_parameters(model)]
    if cfg.optim.optimizer == "sgd":
        # P06 的 SGD 是纯 ``w -= lr * g``，没有 momentum 参数 —— 别照搬 torch 的签名
        return SGD(params, lr=cfg.optim.lr)
    if cfg.optim.optimizer == "adam":
        return Adam(
            params,
            lr=cfg.optim.lr,
            betas=cfg.optim.betas,
            eps=cfg.optim.eps,
        )
    raise ValueError(f"未知优化器：{cfg.optim.optimizer!r}")


def walk_parameters(module, prefix: str = "") -> list[tuple[str, Parameter]]:
    """递归收集 ``(名字, Parameter)``，名字形如 ``decoder.blocks.0.attn.Wq``。

    为什么不用 ``__dict__`` 拍平一层：Block 是嵌套在 DecoderStack 里的 list，
    需要能定位到「第几层」才能做分层参数账。
    """
    found: list[tuple[str, Parameter]] = []
    if isinstance(module, Parameter):
        return [(prefix or "param", module)]
    if isinstance(module, (list, tuple)):
        for index, item in enumerate(module):
            found.extend(walk_parameters(item, f"{prefix}.{index}" if prefix else str(index)))
        return found
    namespace = getattr(module, "__dict__", None)
    if not namespace:
        return found
    for key, value in namespace.items():
        if key.startswith("_"):
            continue
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Parameter):
            found.append((name, value))
        elif hasattr(value, "__dict__") or isinstance(value, (list, tuple)):
            found.extend(walk_parameters(value, name))
    return found


def parameter_report(model: TransformerLM, dtype_bytes: int = 8) -> dict:
    """参数账本：总数、分组、体积。

    分组规则按前缀归类（token_emb / decoder.blocks / decoder.proj / 其它），
    目的是回答「模型的参数都花在哪了」。
    """
    named = walk_parameters(model)
    groups: dict[str, int] = {}
    for name, param in named:
        if name.startswith("token_emb"):
            key = "token_embedding"
        elif name.startswith("decoder.blocks"):
            key = "transformer_blocks"
        elif name.startswith("decoder.proj"):
            key = "output_projection"
        elif name.startswith("decoder.ln_f"):
            key = "final_layernorm"
        else:
            key = "other"
        groups[key] = groups.get(key, 0) + int(param.data.size)
    total = int(sum(groups.values()))
    return {
        "total": total,
        "groups": groups,
        "n_tensors": len(named),
        "bytes": total * dtype_bytes,
        "mib": total * dtype_bytes / (1024 ** 2),
        "trainable": total,
    }


def forward_sanity(model: TransformerLM, seq_len: int = 8, batch: int = 2, seed: int = 0) -> dict:
    """三个不变量自检：**形状对 / 因果对 / 确定**。

    - 形状：logits 必须是 ``(B, T, V)``，且不含 nan。
    - 因果：把第 ``t`` 个位置**之后**的 token 全部改掉，
      第 ``t`` 个及之前的 logits **必须逐位不变**。这是掩码正确的判据。
    - 确定：同一输入跑两次，结果逐位相同（P08 的确定性补丁生效的前提）。
    """
    rng = np.random.default_rng(seed)
    vocab = int(model.vocab_size)
    length = min(int(seq_len), int(model.max_len))
    ids = rng.integers(0, vocab, size=(batch, length)).astype(np.int64)

    logits = model(ids, mask=None).data
    shape_ok = logits.shape == (batch, length, vocab)
    finite = bool(np.all(np.isfinite(logits)))

    # ---- 因果性：改未来，看过去
    split_at = max(1, length // 2)
    tampered = ids.copy()
    tampered[:, split_at:] = (tampered[:, split_at:] + 7) % vocab
    logits2 = model(tampered, mask=None).data
    past_error = float(np.max(np.abs(logits[:, :split_at] - logits2[:, :split_at])))
    # 未来位置**应该**变（否则说明注意力压根没起作用）
    future_error = float(np.max(np.abs(logits[:, split_at:] - logits2[:, split_at:])))

    # ---- 确定性：同一输入两次
    logits3 = model(ids, mask=None).data
    determinism_error = float(np.max(np.abs(logits - logits3)))

    return {
        "shape": tuple(logits.shape),
        "shape_ok": bool(shape_ok),
        "finite": finite,
        "causal_past_max_error": past_error,
        "causal_future_max_error": future_error,
        "determinism_max_error": determinism_error,
        "causal_ok": bool(past_error == 0.0 and future_error > 0.0),
        "deterministic_ok": bool(determinism_error == 0.0),
        "passed": bool(shape_ok and finite and past_error == 0.0 and future_error > 0.0
                       and determinism_error == 0.0),
    }
