"""``ft.sft_data`` —— 指令数据 → id 序列，以及那个"只在答案区"的 mask。

mask 是这个模块存在的全部理由：如果 mask 全 1，模型会花一半力气去学
「怎么复述用户的问题」。下面每个断言都在确保 mask 落在正确的地方。
"""

from __future__ import annotations

import numpy as np
import pytest

from ft import (
    build_lm_examples,
    build_sft_examples,
    dataset_stats,
    load_java_records,
    pad_batch,
    render_example,
    visualize_example,
)
from ft.sft_data import EOS_ID, PAD_ID


def test_records_loaded(records):
    assert len(records) == 59
    assert set(records[0]) == {"instruction", "input", "output"}


def test_render_example_has_prompt_and_answer():
    p, a = render_example({"instruction": "问题", "input": "", "output": "答案"})
    assert "### 指令:" in p
    assert "### 回答:" in p
    assert "### 输入:" not in p
    assert a == "答案"


def test_render_example_includes_input_when_present():
    p, _ = render_example({"instruction": "问题", "input": "上下文", "output": "答案"})
    assert "### 输入:" in p
    assert "上下文" in p


# ---------------------------------------------------------------- mask


def test_mask_length_matches_sequence(sft_examples):
    for e in sft_examples:
        assert e.mask.shape[0] == e.y.shape[0] == e.x.shape[0]


def test_mask_is_one_only_in_answer_region(sft_examples, tokenizer):
    """mask[i] 必须恰好在「目标 token 属于回答」时为 1。"""
    for e in sft_examples:
        n_prompt = e.n_prompt
        # 位置 i 预测的是 ids[i+1]；前 n_prompt 个 token 属于 prompt
        if n_prompt > 0:
            assert np.all(e.mask[: n_prompt - 1] == 0.0), "prompt 区混进了 loss"
        assert np.all(e.mask[n_prompt - 1 :] == 1.0), "答案区被漏掉了"


def test_mask_covers_answer_tokens(sft_examples):
    for e in sft_examples:
        n_answer_in_window = e.length - max(0, e.n_prompt - 1)
        assert int(e.mask.sum()) == n_answer_in_window


def test_mask_is_binary(sft_examples):
    for e in sft_examples:
        assert set(np.unique(e.mask)).issubset({0.0, 1.0})


def test_mask_coverage_is_between_60_and_95_percent(sft_examples):
    total = sum(e.length for e in sft_examples)
    answer = sum(int(e.mask.sum()) for e in sft_examples)
    assert 0.60 < answer / total < 0.95


def test_x_and_y_are_shifted_by_one(sft_examples):
    """自回归：y[i] 必须是 x[i+1]。"""
    for e in sft_examples:
        assert np.array_equal(e.y[:-1], e.x[1:])


def test_eos_is_inside_answer_region(sft_examples):
    """EOS 必须属于答案区，否则模型学不会停。"""
    for e in sft_examples:
        assert e.y[-1] == EOS_ID
        assert e.mask[-1] == 1.0


def test_all_ids_in_vocab(sft_examples, tokenizer):
    for e in sft_examples:
        assert e.x.min() >= 0 and e.x.max() < tokenizer.vocab_size
        assert e.y.min() >= 0 and e.y.max() < tokenizer.vocab_size


def test_prompt_has_no_unk(sft_examples, tokenizer):
    """模板字符必须能被分词器表达（否则 mask 再对也没用）。"""
    unk = tokenizer.token_to_id["<unk>"]
    for e in sft_examples[:10]:
        ids = tokenizer.encode(e.prompt_text)
        assert unk not in ids, "prompt 模板里出现了 <unk>"


# ---------------------------------------------------------------- 截断


def test_truncation_keeps_the_answer(sft_examples, tokenizer, records):
    """超长样本从左侧截断，答案必须完整留在窗口里（丢 prompt 不丢监督信号）。"""
    for e, rec in zip(sft_examples, records):
        answer_ids = tokenizer.encode(e.answer_text) + [EOS_ID]
        k = len(answer_ids)
        assert k <= e.length, "答案本身被截断了 —— 截断策略有问题"
        assert e.y[-(k - 1):].tolist() == answer_ids[1:]


def test_no_example_exceeds_max_len(sft_examples):
    for e in sft_examples:
        assert e.length <= 256


def test_stats_are_consistent(sft_examples, tokenizer, records):
    st = dataset_stats(records, tokenizer, max_len=256)
    assert st["n_records"] == len(sft_examples) == 59
    assert st["total_tokens"] == sum(e.length for e in sft_examples)
    assert st["vocab_size"] == tokenizer.vocab_size
    assert st["len_min"] <= st["len_mean"] <= st["len_max"]


# ---------------------------------------------------------------- 通用语料样本


def test_lm_examples_mask_is_all_one(tokenizer):
    ex = build_lm_examples("今天天气不错，我们去爬山吧。", tokenizer, max_len=64)
    assert len(ex) >= 1
    for e in ex:
        assert np.all(e.mask == 1.0)


def test_lm_examples_cover_all_tokens(tokenizer):
    """非重叠滑窗必须覆盖整段文本（每个窗口贡献 max_len-1 个 token）。"""
    text = " ".join(["一"] * 100)
    ids = tokenizer.encode(text)
    ex = build_lm_examples(text, tokenizer, max_len=64, stride=64)
    covered = sum(e.length for e in ex)
    assert covered >= len(ids) - len(ex) - 1
    assert covered > len(ids) * 0.9


# ---------------------------------------------------------------- 批处理


def test_pad_batch_shapes(sft_examples):
    X, Y, M = pad_batch(sft_examples[:4])
    assert X.shape == Y.shape == M.shape
    assert X.shape[0] == 4
    assert X.shape[1] == max(e.length for e in sft_examples[:4])


def test_pad_batch_uses_pad_id_and_zero_mask(sft_examples):
    X, Y, M = pad_batch(sft_examples[:4])
    lengths = [e.length for e in sft_examples[:4]]
    for i, L in enumerate(lengths):
        if L < X.shape[1]:
            assert np.all(X[i, L:] == PAD_ID)
            assert np.all(M[i, L:] == 0.0)


def test_pad_batch_preserves_real_tokens(sft_examples):
    X, Y, M = pad_batch(sft_examples[:4])
    for i, e in enumerate(sft_examples[:4]):
        assert np.array_equal(X[i, : e.length], e.x)
        assert np.array_equal(Y[i, : e.length], e.y)
        assert np.array_equal(M[i, : e.length], e.mask)


# ---------------------------------------------------------------- 可视化


def test_visualize_example_contains_mask_row(sft_examples, tokenizer):
    text = visualize_example(sft_examples[0], tokenizer, max_show=40)
    assert "mask" in text
    assert "答案区占比" in text
    assert "·" in text and "1" in text


def test_visualize_shows_truncation_warning(sft_examples, tokenizer):
    for e in sft_examples:
        if e.truncated:
            assert "截断" in visualize_example(e, tokenizer)
            return
