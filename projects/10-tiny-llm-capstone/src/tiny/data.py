"""Milestone 03 —— 数据集：从原始语料到「能直接喂进训练循环」的 batch。

这一层要解决的都是「看不见但会毁掉结论」的问题：

1. **切分必须无泄漏**。按行随机切 train/val 之后，要显式做一次交集检查。
   泄漏不会报错，只会让验证困惑度虚高——你是看不出来的。
2. **滑窗不能跨样本**。pack 模式把语料首尾相接能省 padding，但如果不放分隔符，
   模型会学到「上一行的结尾接下一行的开头」这种根本不存在的因果关系。
   所以这里在每个样本之间插 ``<eos>``，让模型知道边界在哪。
3. **padding 必须被 mask 掉**。不 mask 的话模型会花大力气去预测 ``<pad>``，
   loss 会「下降」，但下降的方向全是错的。

产出物统一是 ``(x, y, mask)`` 三元组：``x`` 输入 id、``y`` 目标 id（右移一位）、
``mask`` 标记哪些位置真的要算 loss。P09 的评估指标也是这个约定，直接对接。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import TinyConfig
from .paths import CORPUS_TXT

from tokenizer.base import EOS_ID, PAD_ID  # noqa: E402

__all__ = [
    "Dataset",
    "batch_iter",
    "build_dataset",
    "clean_lines",
    "dataset_report",
    "load_corpus",
    "make_examples",
    "pad_batch",
    "split_lines",
]


# ------------------------------------------------------------------ 语料读取
def load_corpus(
    cfg: TinyConfig,
    path: "str | Path | None" = None,
) -> list[str]:
    """读语料：本项目自带的领域语料（+ 可选 P06 通用语料）。

    ``include_general=True`` 时把 P06 的 ``SAMPLE_CORPUS`` 也混进来，
    模拟真实场景里的「通用语料 + 领域语料混合预训练」。
    """
    target = Path(path) if path is not None else (
        CORPUS_TXT if cfg.data.corpus is None else Path(cfg.data.corpus)
    )
    if not target.is_file():
        raise FileNotFoundError(f"找不到语料文件：{target}")
    lines = [line.strip() for line in target.read_text(encoding="utf-8").splitlines()]
    lines = [line for line in lines if line]
    if cfg.data.include_general:
        from tokenizer.sample_corpus import SAMPLE_CORPUS

        lines += [line.strip() for line in SAMPLE_CORPUS.splitlines() if line.strip()]
    return lines


def clean_lines(lines: list[str], min_chars: int = 8, dedup: bool = True) -> tuple[list[str], dict]:
    """清洗：去空行、去超短行、去重。返回 ``(保留的行, 统计)``。

    为什么要有 ``min_chars``：短行（比如单独一个标点）在滑窗里几乎全是噪声，
    而且会让「平均 token 数」这类统计失真。
    """
    kept: list[str] = []
    seen: set[str] = set()
    dropped_short = 0
    dropped_dup = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < min_chars:
            dropped_short += 1
            continue
        if dedup:
            if stripped in seen:
                dropped_dup += 1
                continue
            seen.add(stripped)
        kept.append(stripped)
    report = {
        "input_lines": len(lines),
        "kept": len(kept),
        "dropped_short": dropped_short,
        "dropped_dup": dropped_dup,
    }
    return kept, report


def split_lines(lines: list[str], val_ratio: float, seed: int = 0) -> tuple[list[str], list[str]]:
    """按行随机切分；**同一次 seed 必然得到同一次切分**（用 Random 而非全局 shuffle）。"""
    if not 0.0 < val_ratio < 1.0:
        raise ValueError(f"val_ratio 必须落在 (0, 1)，当前 {val_ratio}")
    if len(lines) < 2:
        raise ValueError(
            f"语料只有 {len(lines)} 行，切不出验证集：请至少准备 2 行有效语料"
        )
    rng = random.Random(seed)
    order = list(lines)
    rng.shuffle(order)
    n_val = max(1, int(round(len(order) * val_ratio)))
    n_val = min(n_val, len(order) - 1)  # 至少留一条给训练集
    return order[n_val:], order[:n_val]


def leakage_check(train: list[str], val: list[str]) -> dict:
    """train / val 是否出现了完全相同的行 —— 出现即泄漏。"""
    overlap = sorted(set(train) & set(val))
    return {
        "overlap": len(overlap),
        "examples": overlap[:3],
        "clean": not overlap,
    }


# ------------------------------------------------------------------ 样本构造
def make_examples(
    id_lines: list[list[int]],
    max_len: int,
    *,
    pack: bool = True,
    stride: "int | None" = None,
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """把 id 行变成 ``(x, y, mask)`` 自回归样本。

    - ``pack=True``：所有行用 ``<eos>`` 串起来再滑窗。省 padding，但**必须**
      用分隔符告诉模型「这里是边界」。
    - ``pack=False``：每行一个样本，长度不足的靠 :func:`pad_batch` 补齐。
    """
    if max_len < 2:
        raise ValueError(f"max_len 至少为 2，当前 {max_len}")
    examples: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    if pack:
        flat: list[int] = []
        for ids in id_lines:
            flat.extend(int(i) for i in ids)
            flat.append(EOS_ID)
        step = stride or max_len
        if step <= 0 or step > max_len:
            raise ValueError(f"stride 必须落在 (0, max_len={max_len}]，当前 {step}")
        if len(flat) <= max_len:
            # 语料太短，退化成整条一个样本
            x = np.array(flat[:-1], dtype=np.int64)
            y = np.array(flat[1:], dtype=np.int64)
            return [(x, y, np.ones_like(x, dtype=np.float64))]
        for start in range(0, len(flat) - max_len, step):
            window = flat[start : start + max_len + 1]
            x = np.array(window[:-1], dtype=np.int64)
            y = np.array(window[1:], dtype=np.int64)
            examples.append((x, y, np.ones_like(x, dtype=np.float64)))
        return examples

    for ids in id_lines:
        if len(ids) < 2:
            continue
        window = list(int(i) for i in ids)[: max_len + 1]
        x = np.array(window[:-1], dtype=np.int64)
        y = np.array(window[1:], dtype=np.int64)
        examples.append((x, y, np.ones_like(x, dtype=np.float64)))
    return examples


def pad_batch(
    examples: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """把一批变长样本右补齐成方阵，并返回 mask（1=真实 / 0=padding）。"""
    if not examples:
        raise ValueError("examples 不能为空")
    length = max(len(x) for x, _y, _m in examples)
    batch = len(examples)
    x = np.full((batch, length), PAD_ID, dtype=np.int64)
    y = np.full((batch, length), PAD_ID, dtype=np.int64)
    mask = np.zeros((batch, length), dtype=np.float64)
    for row, (xi, yi, mi) in enumerate(examples):
        size = len(xi)
        x[row, :size] = xi
        y[row, :size] = yi
        mask[row, :size] = mi
    return x, y, mask


def batch_iter(
    examples: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    batch_size: int,
    *,
    rng: "random.Random | None" = None,
    drop_last: bool = False,
):
    """按 batch 产出 ``(x, y, mask)``；给 ``rng`` 就先打乱顺序。"""
    order = list(range(len(examples)))
    if rng is not None:
        rng.shuffle(order)
    for start in range(0, len(order), batch_size):
        chunk = order[start : start + batch_size]
        if drop_last and len(chunk) < batch_size:
            continue
        yield pad_batch([examples[i] for i in chunk])


# ------------------------------------------------------------------ 装配
@dataclass
class Dataset:
    """一次切分的全部产物。"""

    train_lines: list[str]
    val_lines: list[str]
    train_examples: list[tuple[np.ndarray, np.ndarray, np.ndarray]]
    val_examples: list[tuple[np.ndarray, np.ndarray, np.ndarray]]
    meta: dict = field(default_factory=dict)


def build_dataset(cfg: TinyConfig, tokenizer, corpus: "list[str] | None" = None) -> Dataset:
    """语料 → 清洗 → 切分 → 编码 → 滑窗，一条龙产出 :class:`Dataset`。"""
    raw = corpus if corpus is not None else load_corpus(cfg)
    kept, clean_report = clean_lines(raw, cfg.data.min_chars, cfg.data.dedup)
    train_lines, val_lines = split_lines(kept, cfg.data.val_ratio, cfg.data.seed)
    leak = leakage_check(train_lines, val_lines)
    if not leak["clean"]:
        raise ValueError(
            f"train/val 出现 {leak['overlap']} 条重复行，数据集泄漏：{leak['examples']}"
        )

    train_ids = [list(map(int, tokenizer.encode(line))) for line in train_lines]
    val_ids = [list(map(int, tokenizer.encode(line))) for line in val_lines]
    train_examples = make_examples(
        train_ids, cfg.model.max_len, pack=cfg.data.pack, stride=cfg.data.stride
    )
    val_examples = make_examples(
        val_ids, cfg.model.max_len, pack=cfg.data.pack, stride=cfg.data.stride
    )

    train_tokens = sum(len(ids) for ids in train_ids)
    val_tokens = sum(len(ids) for ids in val_ids)
    meta = {
        **clean_report,
        "train_lines": len(train_lines),
        "val_lines": len(val_lines),
        "train_tokens": train_tokens,
        "val_tokens": val_tokens,
        "train_examples": len(train_examples),
        "val_examples": len(val_examples),
        "max_len": cfg.model.max_len,
        "pack": cfg.data.pack,
        "stride": cfg.data.stride,
        "leakage": leak,
        "max_len_truncated_rate": _truncation_rate(val_ids, cfg.model.max_len),
    }
    return Dataset(train_lines, val_lines, train_examples, val_examples, meta)


def _truncation_rate(id_lines: list[list[int]], max_len: int) -> float:
    """有多少行超过了 ``max_len``（超过就会被切掉尾巴）。"""
    if not id_lines:
        return 0.0
    long = sum(1 for ids in id_lines if len(ids) > max_len)
    return long / len(id_lines)


def dataset_report(ds: Dataset) -> dict:
    """给 demo / 报告用的数据集体检表。"""
    meta = dict(ds.meta)
    meta["train_example_shape"] = list(ds.train_examples[0][0].shape) if ds.train_examples else []
    meta["batches_per_epoch"] = (
        (len(ds.train_examples) + 7) // 8
    )
    return meta
