"""数据加载：把 token id 序列变成自回归训练批次。

两件事：
1. **滑动窗口**：用前 ``context_len`` 个 token 预测第 ``context_len+1`` 个，
   ``x = ids[i:i+L]``，``y = ids[i+1:i+L+1]``，逐位错开（这就是「自回归」）。
2. **批处理 + 补齐**：一个 batch 里句子长短不一，按 batch 内最长者右侧 pad，
   pad 位置用 ``pad_id`` 占位，并给出 ``mask``（1=真实 / 0=pad），训练时
   只对这些真实位置算 loss。

设计上例子来自「语料按行切分」，每行长度不同 → 天然触发补齐逻辑；
短于 ``context_len`` 的行直接用整行滑窗，长行则切块。
"""

from __future__ import annotations

import numpy as np


def build_examples(
    ids: list[int],
    context_len: int,
    pad_id: int = 0,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """从一条 id 序列造出所有自回归样本 ``(x, y)``。

    这里把整条 ``ids`` 当作一个长序列滑窗（窗口长 ``context_len``），
    产出若干个等长样本。若想演示「变长补齐」，请用 :class:`DataLoader` 配合
    多段语料（见 :func:`examples_from_lines`）。
    """
    examples: list[tuple[np.ndarray, np.ndarray]] = []
    n = len(ids)
    for i in range(0, n - context_len):
        x = np.array(ids[i : i + context_len], dtype=np.int64)
        y = np.array(ids[i + 1 : i + context_len + 1], dtype=np.int64)
        examples.append((x, y))
    return examples


def examples_from_lines(
    id_lines: list[list[int]],
    context_len: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """把多行语料各自变成自回归样本；行长不同 → batch 内需要补齐。

    每行如果比 ``context_len`` 短，用整行做窗口（x=行[:-1], y=行[1:]）；
    若更长，则切成若干个长度为 ``context_len`` 的窗口。
    """
    examples: list[tuple[np.ndarray, np.ndarray]] = []
    for line in id_lines:
        L = len(line)
        if L < 2:
            continue
        if L - 1 <= context_len:
            x = np.array(line[:-1], dtype=np.int64)
            y = np.array(line[1:], dtype=np.int64)
            examples.append((x, y))
        else:
            for i in range(0, L - context_len):
                x = np.array(line[i : i + context_len], dtype=np.int64)
                y = np.array(line[i + 1 : i + context_len + 1], dtype=np.int64)
                examples.append((x, y))
    return examples


def _pad_batch(pairs: list[tuple[np.ndarray, np.ndarray]], pad_id: int):
    """把一个 batch 的 (x, y) 右侧补齐到 batch 内最大长度，返回 X, Y, mask。"""
    max_len = max(len(x) for x, _ in pairs)
    X = np.full((len(pairs), max_len), pad_id, dtype=np.int64)
    Y = np.full((len(pairs), max_len), pad_id, dtype=np.int64)
    mask = np.zeros((len(pairs), max_len), dtype=np.float64)
    for i, (x, y) in enumerate(pairs):
        L = len(x)
        X[i, :L] = x
        Y[i, :L] = y
        mask[i, :L] = 1.0
    return X, Y, mask


class DataLoader:
    """按 batch 产出 ``(X, Y, mask)`` 的迭代器，支持打乱。"""

    def __init__(
        self,
        examples: list[tuple[np.ndarray, np.ndarray]],
        batch_size: int,
        pad_id: int = 0,
        shuffle: bool = True,
    ) -> None:
        self.examples = examples
        self.batch_size = batch_size
        self.pad_id = pad_id
        self.shuffle = shuffle

    def __len__(self) -> int:
        return max(1, (len(self.examples) + self.batch_size - 1) // self.batch_size)

    def __iter__(self):
        idx = np.arange(len(self.examples))
        if self.shuffle:
            # 尊重全局 np.random（测试/demo 用 np.random.seed(0) 控制即可复现）
            idx = np.random.permutation(len(self.examples))
        for start in range(0, len(self.examples), self.batch_size):
            batch_idx = idx[start : start + self.batch_size]
            pairs = [self.examples[i] for i in batch_idx]
            yield _pad_batch(pairs, self.pad_id)
