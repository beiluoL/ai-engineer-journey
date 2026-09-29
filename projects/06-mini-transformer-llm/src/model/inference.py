"""推理：模型一个 token 一个 token 地采样，构造出后续文本。

自回归生成的循环：
1. 把当前上下文（最多 ``context_len`` 个 token）喂进模型，取**最后一个位置**的 logits。
2. 按策略选下一个 token：
   - ``temperature <= 0`` → **贪心**：直接取 argmax（最确定）。
   - ``temperature > 0`` → 用 ``1/temperature`` 缩放 logits 后 softmax 采样；
     ``top_k`` 可选：只保留概率最高的 k 个，其余置 -inf 再采样（更聚焦、少胡说）。
3. 拼到序列后面；遇到 ``<eos>`` 就停。

复杂度关键：每步都只用到「上一步已生成的 token + 新采的 1 个」，所以时间随生成长度线性增长。
"""

from __future__ import annotations

import numpy as np

from .autograd import Tensor
from .decoder import TransformerLM
from tokenizer.base import EOS_ID, UNK_ID


def generate_ids(
    model: TransformerLM,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 20,
    temperature: float = 1.0,
    top_k: "int | None" = None,
    rng: "np.random.Generator | None" = None,
) -> list[int]:
    """由 ``prompt`` 继续生成至多 ``max_new_tokens`` 个新 token，返回**完整 id 列表**。

    比 :func:`generate` 更低一层：测试需要直接检查「生成的 token 是否都在词表内、
    数量是否正确」，所以这里把 id 暴露出来。
    """
    rng = rng or np.random
    ids = list(tokenizer.encode(prompt))
    ctx_len = model.max_len

    for _ in range(max_new_tokens):
        # 只保留最近的 ctx_len 个 token，避免超出位置编码长度
        ctx = ids[-ctx_len:] if len(ids) > ctx_len else ids
        x = np.array([ctx], dtype=np.int64)
        logits: Tensor = model(x, mask=None)
        last = logits.data[0, -1, :]  # (vocab,)

        if temperature <= 0:
            next_id = int(np.argmax(last))
        else:
            logits_t = last / temperature
            if top_k is not None and top_k > 0:
                k = min(top_k, len(logits_t))
                thr = np.sort(logits_t)[-k]
                logits_t = np.where(logits_t < thr, -np.inf, logits_t)
            p = np.exp(logits_t - np.max(logits_t))
            p = p / p.sum()
            next_id = int(rng.choice(len(p), p=p))

        if next_id == EOS_ID:
            break
        ids.append(next_id)

    return ids


def generate(
    model: TransformerLM,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 20,
    temperature: float = 1.0,
    top_k: "int | None" = None,
    rng: "np.random.Generator | None" = None,
) -> str:
    """由 ``prompt`` 继续生成至多 ``max_new_tokens`` 个新 token，返回完整文本。"""
    ids = generate_ids(model, tokenizer, prompt, max_new_tokens, temperature, top_k, rng)
    return tokenizer.decode(ids, skip_special=True)


def logits_of_prefix(model: TransformerLM, tokenizer, prompt: str) -> np.ndarray:
    """工具函数：返回 prompt 最后一个位置的 logits（供 demo 展示分布用）。"""
    ids = tokenizer.encode(prompt)
    ctx = ids[-model.max_len:] if len(ids) > model.max_len else ids
    x = np.array([ctx], dtype=np.int64)
    return model(x, mask=None).data[0, -1, :]
