"""纯 numpy 自回归引擎，支持与完整重算可切换的 KV Cache。"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np


@dataclass
class KVCacheState:
    keys: list[np.ndarray]
    values: list[np.ndarray]
    length: int


def _layernorm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray, eps: float) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    centered = x - mean
    variance = (centered * centered).mean(axis=-1, keepdims=True)
    return centered / np.sqrt(variance + eps) * gamma + beta


def _softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - np.max(x, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


def _weight(value) -> np.ndarray:
    return np.asarray(value.data, dtype=np.float64)


class CausalLMWithKVCache:
    """直接读取 P06 模型参数，以 numpy 实现完整与增量前向。"""

    def __init__(self, model) -> None:
        self.model = model
        self.max_len = int(model.max_len)
        self.n_heads = int(model.n_heads)
        self.d_model = int(model.d_model)
        self.head_dim = self.d_model // self.n_heads
        if self.d_model % self.n_heads:
            raise ValueError("d_model 必须可被 n_heads 整除")

    def _embed(self, ids: np.ndarray, start_pos: int = 0) -> np.ndarray:
        ids = np.asarray(ids, dtype=np.int64)
        positions = self.model.pos_enc.pe[start_pos : start_pos + ids.shape[-1]]
        return _weight(self.model.token_emb.weight)[ids] + positions

    def _split(self, x: np.ndarray) -> np.ndarray:
        batch, length, _ = x.shape
        return x.reshape(batch, length, self.n_heads, self.head_dim).transpose(0, 2, 1, 3)

    def _merge(self, x: np.ndarray) -> np.ndarray:
        batch, _heads, length, _dim = x.shape
        return x.transpose(0, 2, 1, 3).reshape(batch, length, self.d_model)

    def forward(self, ids: np.ndarray, return_cache: bool = False):
        ids = np.asarray(ids, dtype=np.int64)
        if ids.ndim == 1:
            ids = ids[None, :]
        if ids.ndim != 2 or ids.shape[1] == 0:
            raise ValueError("ids 必须是非空的一维或二维整数数组")
        if ids.shape[1] > self.max_len:
            raise ValueError(f"序列长度 {ids.shape[1]} 超过 max_len={self.max_len}")
        hidden = self._embed(ids)
        keys: list[np.ndarray] = []
        values: list[np.ndarray] = []
        length = ids.shape[1]
        causal = np.triu(np.full((length, length), -np.inf, dtype=np.float64), k=1)
        for block in self.model.decoder.blocks:
            normed = _layernorm(hidden, _weight(block.ln1.gamma), _weight(block.ln1.beta), block.ln1.eps)
            q = self._split(normed @ _weight(block.attn.Wq))
            k = self._split(normed @ _weight(block.attn.Wk))
            v = self._split(normed @ _weight(block.attn.Wv))
            scores = q @ k.transpose(0, 1, 3, 2) / np.sqrt(self.head_dim)
            context = _softmax(scores + causal) @ v
            hidden = hidden + self._merge(context) @ _weight(block.attn.Wo)
            normed = _layernorm(hidden, _weight(block.ln2.gamma), _weight(block.ln2.beta), block.ln2.eps)
            ff = np.maximum(0.0, normed @ _weight(block.ffn.W1) + _weight(block.ffn.b1))
            hidden = hidden + ff @ _weight(block.ffn.W2) + _weight(block.ffn.b2)
            keys.append(k.copy())
            values.append(v.copy())
        final = self.model.decoder.ln_f
        hidden = _layernorm(hidden, _weight(final.gamma), _weight(final.beta), final.eps)
        logits = hidden @ _weight(self.model.decoder.proj)
        if return_cache:
            return logits, KVCacheState(keys=keys, values=values, length=length)
        return logits

    def prefill(self, ids: np.ndarray) -> tuple[np.ndarray, KVCacheState]:
        logits, state = self.forward(ids, return_cache=True)
        return logits[:, -1, :], state

    def decode_step(self, token_ids: np.ndarray, state: KVCacheState) -> tuple[np.ndarray, KVCacheState]:
        token_ids = np.asarray(token_ids, dtype=np.int64).reshape(-1, 1)
        if state.length >= self.max_len:
            raise ValueError("KV Cache 已达到模型最大上下文长度")
        hidden = self._embed(token_ids, start_pos=state.length)
        new_keys: list[np.ndarray] = []
        new_values: list[np.ndarray] = []
        for index, block in enumerate(self.model.decoder.blocks):
            normed = _layernorm(hidden, _weight(block.ln1.gamma), _weight(block.ln1.beta), block.ln1.eps)
            q = self._split(normed @ _weight(block.attn.Wq))
            current_k = self._split(normed @ _weight(block.attn.Wk))
            current_v = self._split(normed @ _weight(block.attn.Wv))
            k = np.concatenate([state.keys[index], current_k], axis=2)
            v = np.concatenate([state.values[index], current_v], axis=2)
            context = _softmax(q @ k.transpose(0, 1, 3, 2) / np.sqrt(self.head_dim)) @ v
            hidden = hidden + self._merge(context) @ _weight(block.attn.Wo)
            normed = _layernorm(hidden, _weight(block.ln2.gamma), _weight(block.ln2.beta), block.ln2.eps)
            ff = np.maximum(0.0, normed @ _weight(block.ffn.W1) + _weight(block.ffn.b1))
            hidden = hidden + ff @ _weight(block.ffn.W2) + _weight(block.ffn.b2)
            new_keys.append(k)
            new_values.append(v)
        final = self.model.decoder.ln_f
        hidden = _layernorm(hidden, _weight(final.gamma), _weight(final.beta), final.eps)
        logits = hidden @ _weight(self.model.decoder.proj)
        return logits[:, -1, :], KVCacheState(new_keys, new_values, state.length + 1)

    @staticmethod
    def _choose(logits: np.ndarray, temperature: float, rng: np.random.Generator) -> int:
        if temperature <= 0:
            return int(np.argmax(logits))
        scaled = logits / temperature
        probs = np.exp(scaled - scaled.max())
        probs /= probs.sum()
        return int(rng.choice(probs.size, p=probs))

    def generate_ids(
        self,
        prompt_ids: list[int],
        max_new_tokens: int,
        *,
        use_kv_cache: bool = True,
        temperature: float = 0.0,
        seed: int = 0,
        stop_id: "int | None" = None,
    ) -> list[int]:
        if not prompt_ids:
            raise ValueError("prompt_ids 不能为空")
        if len(prompt_ids) + max_new_tokens > self.max_len:
            raise ValueError("prompt + max_new_tokens 超过模型上下文长度")
        rng = np.random.default_rng(seed)
        ids = list(map(int, prompt_ids))
        if use_kv_cache:
            last, state = self.prefill(np.asarray([ids], dtype=np.int64))
            for index in range(max_new_tokens):
                next_id = self._choose(last[0], temperature, rng)
                if stop_id is not None and next_id == stop_id:
                    break
                ids.append(next_id)
                if index + 1 < max_new_tokens:
                    last, state = self.decode_step(np.array([next_id]), state)
        else:
            for _ in range(max_new_tokens):
                logits = self.forward(np.asarray([ids], dtype=np.int64))
                next_id = self._choose(logits[0, -1], temperature, rng)
                if stop_id is not None and next_id == stop_id:
                    break
                ids.append(next_id)
        return ids

    def generate(self, tokenizer, prompt: str, max_new_tokens: int = 20, **kwargs) -> str:
        ids = self.generate_ids(tokenizer.encode(prompt), max_new_tokens, **kwargs)
        return tokenizer.decode(ids, skip_special=True)

    def benchmark(self, prompt_ids: list[int], max_new_tokens: int = 12, repeats: int = 5) -> dict:
        if repeats <= 0:
            raise ValueError("repeats 必须大于 0")
        timings: dict[bool, list[float]] = {False: [], True: []}
        outputs: dict[bool, list[int]] = {}
        for cached in (False, True):
            self.generate_ids(prompt_ids, 2, use_kv_cache=cached, stop_id=None)
        for _ in range(repeats):
            for cached in (False, True):
                start = time.perf_counter()
                outputs[cached] = self.generate_ids(
                    prompt_ids, max_new_tokens, use_kv_cache=cached,
                    temperature=0.0, seed=0, stop_id=None,
                )
                timings[cached].append((time.perf_counter() - start) * 1000.0)
        no_cache = float(np.median(timings[False]))
        cached = float(np.median(timings[True]))
        return {
            "no_cache_ms": no_cache,
            "kv_cache_ms": cached,
            "speedup": no_cache / cached,
            "outputs_equal": outputs[False] == outputs[True],
            "max_logit_error": self.cache_consistency_error(prompt_ids),
            "no_cache_trials_ms": timings[False],
            "kv_cache_trials_ms": timings[True],
            "n_generated": max_new_tokens,
        }

    def cache_consistency_error(self, prompt_ids: list[int], next_id: "int | None" = None) -> float:
        last, state = self.prefill(np.asarray([prompt_ids], dtype=np.int64))
        token = int(np.argmax(last[0])) if next_id is None else int(next_id)
        cached, _ = self.decode_step(np.array([token]), state)
        full = self.forward(np.asarray([prompt_ids + [token]], dtype=np.int64))[0, -1]
        return float(np.max(np.abs(cached[0] - full)))


__all__ = ["CausalLMWithKVCache", "KVCacheState"]
