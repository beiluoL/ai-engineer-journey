"""Milestone 08 —— 推理：从「模型能跑」到「模型能按人的意图生成」。

训练结束只是把权重存下来了，真正被用户感知的是**采样策略**。本模块实现四种
控制手段，并**逐个证明它们真的生效**（不是「看起来生效」）：

- ``temperature``：缩放 logits 后再 softmax。T→0 退化为贪心，T 越大越发散。
- ``top_k``：只保留概率最高的 k 个候选。
- ``top_p``（核采样）：只保留累积概率达到 p 的最小候选集。
- ``repetition_penalty``：把已生成 token 的 logits 压下去，专治复读。

两个必须实测的正确性判据（M08 会打印真实数字）：

1. **KV Cache 与全量重算必须等价**。加速的前提是「算出来的还是同一个东西」。
   这里直接对拍最后一步的 logits，给出最大绝对误差。
2. **同 seed 必须逐位复现**。否则线上出了问题根本无法回放。

``use_kv_cache=False`` 走 P06 的整模型前向（每步重算整个序列），
``True`` 走 P09 的 :class:`CausalLMWithKVCache`（prefill + 单步 decode）。
两条路径共用同一个采样器，保证「加速」与「策略」互不干扰。
"""

from __future__ import annotations

import time

import numpy as np

from .config import TinyConfig

from ie.engine import CausalLMWithKVCache  # noqa: E402
from tokenizer.base import EOS_ID  # noqa: E402

__all__ = ["Generator", "top_k_filter", "top_p_filter"]


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / exp.sum()


def top_k_filter(logits: np.ndarray, k: int) -> np.ndarray:
    """把非 top-k 的位置置为 ``-inf``（k<=0 表示不启用）。"""
    if k <= 0 or k >= logits.size:
        return logits
    keep = np.argpartition(logits, -k)[-k:]
    masked = np.full_like(logits, -np.inf)
    masked[keep] = logits[keep]
    return masked


def top_p_filter(logits: np.ndarray, p: float) -> np.ndarray:
    """核采样：保留累积概率达到 ``p`` 的最小候选集，其余置 ``-inf``。"""
    if p >= 1.0:
        return logits
    order = np.argsort(logits)[::-1]
    probs = _softmax(logits[order])
    cumulative = np.cumsum(probs)
    keep_count = int(np.searchsorted(cumulative, p) + 1)
    keep_count = min(max(keep_count, 1), logits.size)
    masked = np.full_like(logits, -np.inf)
    masked[order[:keep_count]] = logits[order[:keep_count]]
    return masked


class Generator:
    """Tiny LLM 的推理器：采样策略 + KV Cache 开关 + 流式输出。"""

    def __init__(self, model, tokenizer, cfg: TinyConfig) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.cfg = cfg
        self.engine = CausalLMWithKVCache(model)

    # ------------------------------------------------------------ 采样
    def _next_id(
        self,
        logits: np.ndarray,
        generated: list[int],
        *,
        temperature: float,
        top_k: int,
        top_p: float,
        repetition_penalty: float,
        rng: np.random.Generator,
    ) -> int:
        values = np.asarray(logits, dtype=np.float64).copy()
        if repetition_penalty != 1.0 and generated:
            for token in set(generated):
                if 0 <= token < values.size:
                    # 标准做法：正 logit 缩小、负 logit 放大（等价于除以 / 乘以 penalty）
                    values[token] = (
                        values[token] / repetition_penalty
                        if values[token] > 0
                        else values[token] * repetition_penalty
                    )
        if temperature <= 0:
            return int(np.argmax(values))
        scaled = values / temperature
        scaled = top_k_filter(scaled, top_k)
        scaled = top_p_filter(scaled, top_p)
        probs = _softmax(scaled)
        if not np.isfinite(probs).all() or probs.sum() <= 0:
            return int(np.argmax(values))
        return int(rng.choice(probs.size, p=probs))

    # ------------------------------------------------------------ 生成
    def iter_ids(
        self,
        prompt: str,
        *,
        max_new_tokens: "int | None" = None,
        temperature: "float | None" = None,
        top_k: "int | None" = None,
        top_p: "float | None" = None,
        repetition_penalty: "float | None" = None,
        seed: "int | None" = None,
        use_kv_cache: "bool | None" = None,
    ):
        """**逐 token 产出** id（真正的流式，不是先算完再吐）。

        为什么把它拆成生成器：``stream()`` 的价值全在「第一个 token 什么时候到」。
        如果内部先把整段算完再一条条 yield，TTFT 就等于总耗时，
        流式在延迟上一点收益都没有 —— 那是假的流式。所以这里是唯一一份
        解码循环实现，``generate_ids`` 只是把它 ``list()`` 掉。
        """
        g = self.cfg.gen
        max_new = int(max_new_tokens if max_new_tokens is not None else g.max_new_tokens)
        temp = float(g.temperature if temperature is None else temperature)
        k = int(g.top_k if top_k is None else top_k)
        p = float(g.top_p if top_p is None else top_p)
        rep = float(g.repetition_penalty if repetition_penalty is None else repetition_penalty)
        cached = bool(g.use_kv_cache if use_kv_cache is None else use_kv_cache)
        rng = np.random.default_rng(int(g.seed if seed is None else seed))

        prompt_ids = [int(i) for i in self.tokenizer.encode(prompt)]
        if not prompt_ids:
            prompt_ids = [EOS_ID]
        room = self.engine.max_len - max_new - 1
        if room <= 0:
            raise ValueError("max_new_tokens 超过模型上下文容量")
        prompt_ids = prompt_ids[-max(room, 1) :]

        generated: list[int] = []
        if cached:
            logits, state = self.engine.prefill(np.asarray([prompt_ids], dtype=np.int64))
            for index in range(max_new):
                next_id = self._next_id(logits[0], generated, temperature=temp, top_k=k,
                                        top_p=p, repetition_penalty=rep, rng=rng)
                if next_id == EOS_ID:
                    break
                generated.append(next_id)
                yield next_id
                if index + 1 < max_new:
                    logits, state = self.engine.decode_step(np.array([next_id]), state)
        else:
            ids = list(prompt_ids)
            for _ in range(max_new):
                logits = self.engine.forward(np.asarray([ids], dtype=np.int64))
                next_id = self._next_id(logits[0, -1], generated, temperature=temp, top_k=k,
                                        top_p=p, repetition_penalty=rep, rng=rng)
                if next_id == EOS_ID:
                    break
                generated.append(next_id)
                yield next_id
                ids.append(next_id)
                if len(ids) > self.engine.max_len:
                    ids = ids[-self.engine.max_len :]

    def generate_ids(self, prompt: str, **kwargs) -> list[int]:
        return list(self.iter_ids(prompt, **kwargs))

    def generate(self, prompt: str, **kwargs) -> str:
        ids = self.generate_ids(prompt, **kwargs)
        return self.tokenizer.decode(ids, skip_special=True)

    def complete_ids(self, prompt: str, **kwargs) -> list[int]:
        """返回 prompt + 续写的完整 id 序列（服务端算 usage 时需要）。"""
        prompt_ids = [int(i) for i in self.tokenizer.encode(prompt)]
        return prompt_ids + self.generate_ids(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs):
        """逐 token 产出 ``(token_text, 已生成文本)`` —— 服务层 SSE 的数据源。

        ⚠ 必须直接消费 :meth:`iter_ids` 的生成器，**不能**先 ``generate_ids`` 再遍历：
        那样第一个 chunk 要等整段解码结束才出现，TTFT 等于总耗时，
        流式就只剩下「好看」而没有「更快」。
        """
        buf: list[int] = []
        for token_id in self.iter_ids(prompt, **kwargs):
            buf.append(token_id)
            yield self.tokenizer.decode([token_id], skip_special=True), self.tokenizer.decode(
                buf, skip_special=True
            )

    # ------------------------------------------------------------ 自检
    def cache_consistency_error(self, prompt: str) -> float:
        """KV Cache 路径 vs 全量重算：**最后一步 logits 的最大绝对误差**。"""
        ids = [int(i) for i in self.tokenizer.encode(prompt)]
        if not ids:
            ids = [EOS_ID]
        return float(self.engine.cache_consistency_error(ids))

    def benchmark(self, prompt: str, repeats: int = 5, max_new_tokens: int = 12) -> dict:
        """同一条 prompt，开/关 KV Cache 各跑 ``repeats`` 次，给出中位耗时与加速比。"""
        ids = [int(i) for i in self.tokenizer.encode(prompt)]
        if not ids:
            ids = [EOS_ID]
        ids = ids[: max(1, self.engine.max_len - max_new_tokens - 1)]
        result = self.engine.benchmark(ids, max_new_tokens=max_new_tokens, repeats=repeats)
        result["prompt"] = prompt
        return result

    def timed_generate(self, prompt: str, repeats: int = 3, **kwargs) -> dict:
        """推理延迟实测：首字时间（TTFT）与总耗时的中位数。"""
        ttft: list[float] = []
        total: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            first: "float | None" = None
            for _token, _text in self.stream(prompt, **kwargs):
                if first is None:
                    first = (time.perf_counter() - started) * 1000.0
            ttft.append(first if first is not None else 0.0)
            total.append((time.perf_counter() - started) * 1000.0)
        return {
            "ttft_ms": float(np.median(ttft)),
            "total_ms": float(np.median(total)),
            "repeats": repeats,
        }
