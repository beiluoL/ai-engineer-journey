"""数据集（M03）：清洗、无泄漏切分、自回归对齐、padding mask。"""

from __future__ import annotations

import numpy as np
import pytest

from tiny.data import (
    batch_iter,
    build_dataset,
    clean_lines,
    dataset_report,
    leakage_check,
    load_corpus,
    make_examples,
    pad_batch,
    split_lines,
)
from tiny.paths import CORPUS_TXT


def test_load_corpus_returns_non_empty_unique_lines(cfg):
    lines = load_corpus(cfg)
    assert len(lines) > 100
    assert CORPUS_TXT.is_file()


def test_clean_lines_drops_short_and_duplicate():
    lines = ["有效的一条测试句子", "短句", "有效的一条测试句子", "另外一条更长的句子"]
    kept, report = clean_lines(lines, 8, True)
    assert kept == ["有效的一条测试句子", "另外一条更长的句子"]
    assert report["dropped_short"] == 1
    assert report["dropped_dup"] == 1


def test_split_has_no_leakage_and_is_deterministic(corpus_lines):
    train_a, val_a = split_lines(corpus_lines, 0.2, seed=7)
    train_b, val_b = split_lines(corpus_lines, 0.2, seed=7)
    assert train_a == train_b and val_a == val_b  # 同 seed 必须完全一致
    assert leakage_check(train_a, val_a)["clean"]


def test_split_ratio_is_respected(corpus_lines):
    train, val = split_lines(corpus_lines, 0.2, seed=0)
    assert len(val) == max(1, round(len(corpus_lines) * 0.2))
    assert len(train) + len(val) == len(corpus_lines)


def test_make_examples_shifts_target_by_one():
    examples = make_examples([[1, 2, 3, 4, 5]], max_len=4, pack=False)
    x, y, mask = examples[0]
    assert list(x) == [1, 2, 3, 4]
    assert list(y) == [2, 3, 4, 5]
    assert mask.sum() == len(x)


def test_pack_mode_inserts_eos_between_samples():
    """pack 必须在样本之间插 <eos>，否则模型会学到不存在的跨样本因果。"""
    from tokenizer.base import EOS_ID

    examples = make_examples([[10, 11], [20, 21]], max_len=8, pack=True)
    flat = list(examples[0][0]) + [int(examples[0][1][-1])]
    assert EOS_ID in flat


def test_pad_batch_marks_padding_positions():
    examples = [
        (np.array([1, 2, 3]), np.array([2, 3, 4]), np.ones(3)),
        (np.array([9]), np.array([8]), np.ones(1)),
    ]
    x, y, mask = pad_batch(examples)
    assert x.shape == (2, 3)
    assert mask[0].tolist() == [1.0, 1.0, 1.0]
    assert mask[1].tolist() == [1.0, 0.0, 0.0]
    assert y[1, 1] == 0  # padding 位置用 PAD_ID


def test_batch_iter_covers_all_examples():
    examples = make_examples([[i, i + 1, i + 2] for i in range(10)], max_len=4, pack=False)
    seen = 0
    for x, y, mask in batch_iter(examples, 4):
        seen += x.shape[0]
    assert seen == len(examples)


def test_build_dataset_reports_no_leakage(cfg, tiny_dataset):
    report = dataset_report(tiny_dataset)
    assert report["leakage"]["clean"]
    assert report["train_examples"] > 0
    assert report["val_examples"] > 0


def test_split_rejects_corpus_that_cannot_form_a_val_set():
    """1 行语料切不出验证集 —— 必须显式报错，而不是悄悄给你一个空的 val。"""
    with pytest.raises(ValueError, match="切不出验证集"):
        split_lines(["只有一行有效语料"], 0.2, seed=0)
