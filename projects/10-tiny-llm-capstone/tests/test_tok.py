"""分词器（M02）：训练、落盘、往返、压缩率、OOV 归因。"""

from __future__ import annotations

import copy

from tiny.tok import (
    build_tokenizer,
    encode_lines,
    load_tokenizer,
    oov_chars,
    roundtrip_report,
    save_tokenizer,
    tokenizer_stats,
)


def test_char_tokenizer_roundtrip_is_exact_on_training_lines(cfg, char_tokenizer, corpus_lines):
    """训练集上必须 100% 往返 —— 这是分词器正确性的底线。"""
    from tiny.data import clean_lines, split_lines

    kept, _ = clean_lines(corpus_lines, cfg.data.min_chars, cfg.data.dedup)
    train_lines, _val = split_lines(kept, cfg.data.val_ratio, cfg.data.seed)
    report = roundtrip_report(char_tokenizer, train_lines)
    assert report["ok"] == report["total"]
    assert report["pass_rate"] == 1.0


def test_save_then_load_produces_identical_encodings(workdir, cfg, char_tokenizer):
    path = workdir / "tok.json"
    save_tokenizer(char_tokenizer, path)
    restored = load_tokenizer(path)
    sample = "问：什么是 KV Cache？答：KV Cache 缓存已算过的 K 和 V。"
    assert restored.encode(sample) == char_tokenizer.encode(sample)
    assert restored.vocab_size == char_tokenizer.vocab_size


def test_bpe_compresses_better_than_char(cfg, corpus_lines):
    """BPE 存在的意义就是压缩：同样的文本，token 数必须比「一字一 token」少。"""
    from tiny.data import clean_lines, split_lines

    kept, _ = clean_lines(corpus_lines, cfg.data.min_chars, cfg.data.dedup)
    train_lines, _val = split_lines(kept, cfg.data.val_ratio, cfg.data.seed)

    bpe_cfg = small_config_copy(cfg)
    bpe_cfg.tokenizer.kind = "bpe"
    bpe_cfg.tokenizer.vocab_size = 1280
    bpe = build_tokenizer(bpe_cfg, train_lines)
    bpe_tokens = sum(len(bpe.encode(line)) for line in kept)
    char_tokens = sum(len(line) for line in kept)  # 字符级的上界
    assert bpe_tokens < char_tokens
    stats = tokenizer_stats(bpe, kept)
    assert stats["chars_per_token"] > 1.0
    assert stats["unk_rate"] >= 0.0


def small_config_copy(cfg):
    return copy.deepcopy(cfg)


def test_roundtrip_failures_are_attributed_to_oov(cfg, corpus_lines):
    """本项目实测：往返失败**全部**由验证集 OOV 字符引起，不该有实现 bug。"""
    from tiny.data import clean_lines, split_lines

    kept, _ = clean_lines(corpus_lines, cfg.data.min_chars, cfg.data.dedup)
    train_lines, val_lines = split_lines(kept, cfg.data.val_ratio, cfg.data.seed)
    bpe_cfg = small_config_copy(cfg)
    bpe_cfg.tokenizer.kind = "bpe"
    bpe_cfg.tokenizer.vocab_size = 1280
    bpe = build_tokenizer(bpe_cfg, train_lines)  # 词表只用训练集
    report = roundtrip_report(bpe, val_lines)
    assert report["other_caused"] == 0
    assert report["all_failures_explained_by_oov"]


def test_oov_chars_detects_unknown_characters(cfg, char_tokenizer):
    assert oov_chars(char_tokenizer, "分词器") == []
    assert oov_chars(char_tokenizer, "𝕏𝕐") != []


def test_encode_lines_shape(cfg, char_tokenizer):
    lines = ["第一行测试文本", "第二行测试文本"]
    encoded = encode_lines(char_tokenizer, lines)
    assert len(encoded) == 2
    assert all(isinstance(i, int) for row in encoded for i in row)
