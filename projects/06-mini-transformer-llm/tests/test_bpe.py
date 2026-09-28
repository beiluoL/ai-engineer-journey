"""BPE 分词器的测试：训练循环 / 合并优先级 / 往返一致性 / 优雅停止 / 落盘。"""

from __future__ import annotations

import json

import pytest

from tokenizer import BPETokenizer, CharTokenizer

#: 语料里出现过的整句（字符全在词表内），用来测往返一致性
IN_VOCAB_SENTENCE = "Tokenization 把文本切成 token，token 是模型的最小单位。"


# ---------- 训练循环 ----------


def test_train_merges_the_most_frequent_pair() -> None:
    tok = BPETokenizer.train("ab ab ab ab cd", 100)
    assert ("a", "b") == tok.merges[0]
    assert "ab" in tok.vocab


def test_merge_order_is_frequency_then_lexicographic() -> None:
    # ab 出现 3 次，xy 出现 1 次 —— ab 必须先被合并
    tok = BPETokenizer.train("ab ab ab xy", 100)
    assert tok.merges[0] == ("a", "b")
    # 同频次时按字典序，保证训练可复现
    tok2 = BPETokenizer.train("pq rs", 100)
    assert tok2.merges[0] == ("p", "q")


def test_training_is_deterministic(corpus: str) -> None:
    a = BPETokenizer.train(corpus, 500)
    b = BPETokenizer.train(corpus, 500)
    assert a.id_to_token == b.id_to_token
    assert a.merges == b.merges


def test_vocab_size_is_a_hard_cap(corpus: str) -> None:
    char_tok = CharTokenizer.build(corpus)
    tok = BPETokenizer.train(corpus, char_tok.vocab_size + 40)  # 基础字符 + 40 次合并
    assert tok.vocab_size == char_tok.vocab_size + 40
    assert len(tok.merges) == 40


def test_vocab_size_too_small_raises() -> None:
    with pytest.raises(ValueError, match="太小"):
        BPETokenizer.train("abcdefgh", 6)


def test_stop_gracefully_when_no_pairs_left() -> None:
    # 只有 3 个字符的语料，最多合并 2 次，请求 5000 只能提前停
    tok = BPETokenizer.train("abc", 5000)
    assert tok.vocab_size < 5000
    assert len(tok.merges) == 2
    assert tok.id_to_token[4:] == ["a", "b", "c", "ab", "abc"]


def test_base_vocab_size_excludes_merges(corpus: str, bpe_tok: BPETokenizer) -> None:
    assert bpe_tok.base_vocab_size == 4 + len({c for c in corpus})
    assert bpe_tok.vocab_size == bpe_tok.base_vocab_size + len(bpe_tok.merges)


def test_train_accepts_list_of_lines() -> None:
    tok = BPETokenizer.train(["ab ab", "ab ab cd"], 100)
    assert tok.merges[0] == ("a", "b")


def test_merges_never_cross_whitespace() -> None:
    tok = BPETokenizer.train("ab cd ab cd ef gh", 200)
    for token in tok.id_to_token[4:]:
        if any(ch.isspace() for ch in token):
            assert len(token) == 1, f"空白被并进了 token：{token!r}"


def test_chinese_bigrams_get_merged(corpus: str, bpe_tok: BPETokenizer) -> None:
    # 中文逐字起手，高频二字词（如「模型」「token」里的组合）应该被并成一个 token
    merged = {a + b for a, b in bpe_tok.merges}
    chinese_merges = [m for m in merged if any("\u4e00" <= ch <= "\u9fff" for ch in m)]
    assert chinese_merges, "中文语料上竟然没学到任何中文合并"
    assert len(chinese_merges) > 3


# ---------- 压缩率（BPE 存在的理由） ----------


def test_bpe_is_shorter_than_char_level(corpus: str, bpe_tok: BPETokenizer) -> None:
    char_tok = CharTokenizer.build(corpus)
    assert len(bpe_tok.encode(IN_VOCAB_SENTENCE)) < len(
        char_tok.encode(IN_VOCAB_SENTENCE)
    )


def test_more_merges_means_shorter_sequence(corpus: str) -> None:
    base = CharTokenizer.build(corpus).vocab_size
    small = BPETokenizer.train(corpus, base + 20)
    large = BPETokenizer.train(corpus, base + 200)
    assert len(large.encode(IN_VOCAB_SENTENCE)) < len(
        small.encode(IN_VOCAB_SENTENCE)
    )


def test_compression_ratio_on_repeated_words() -> None:
    tok = BPETokenizer.train("transformer transformer transformer", 100)
    ids = tok.encode("transformer")
    assert len(ids) < len("transformer")


# ---------- 往返一致性 ----------


def test_roundtrip_in_vocab_sentence(bpe_tok: BPETokenizer) -> None:
    assert bpe_tok.decode(bpe_tok.encode(IN_VOCAB_SENTENCE)) == IN_VOCAB_SENTENCE


def test_roundtrip_chinese_only(bpe_tok: BPETokenizer) -> None:
    s = "注意力机制让模型自己决定该看哪里"
    assert bpe_tok.decode(bpe_tok.encode(s)) == s


def test_roundtrip_every_line_of_corpus(corpus: str, bpe_tok: BPETokenizer) -> None:
    for line in corpus.splitlines():
        assert bpe_tok.decode(bpe_tok.encode(line)) == line


def test_roundtrip_mixed_text_when_trained_on_it(mixed_text: str, corpus: str) -> None:
    base = CharTokenizer.build(corpus + "\n" + mixed_text).vocab_size
    tok = BPETokenizer.train(corpus + "\n" + mixed_text, base + 200)
    assert tok.decode(tok.encode(mixed_text)) == mixed_text


def test_unknown_chars_fall_back_to_unk(bpe_tok: BPETokenizer, mixed_text: str) -> None:
    ids = bpe_tok.encode(mixed_text)
    assert 1 in ids  # 语料里没见过的字符 → <unk>
    assert all(0 <= i < bpe_tok.vocab_size for i in ids)


def test_roundtrip_empty(bpe_tok: BPETokenizer) -> None:
    assert bpe_tok.encode("") == []
    assert bpe_tok.decode([]) == ""


def test_encode_cache_is_consistent(bpe_tok: BPETokenizer) -> None:
    first = bpe_tok.encode(IN_VOCAB_SENTENCE)
    second = bpe_tok.encode(IN_VOCAB_SENTENCE)
    assert first == second


def test_pieces_join_back_to_original(bpe_tok: BPETokenizer) -> None:
    assert "".join(bpe_tok.pieces(IN_VOCAB_SENTENCE)) == IN_VOCAB_SENTENCE


# ---------- 特殊 token ----------


def test_add_special_tokens(bpe_tok: BPETokenizer) -> None:
    ids = bpe_tok.encode(IN_VOCAB_SENTENCE, add_special_tokens=True)
    assert ids[0] == 2 and ids[-1] == 3
    assert bpe_tok.decode(ids, skip_special=True) == IN_VOCAB_SENTENCE


def test_decode_rejects_out_of_range_id(bpe_tok: BPETokenizer) -> None:
    with pytest.raises(ValueError, match="越界"):
        bpe_tok.decode([bpe_tok.vocab_size])


# ---------- 落盘 ----------


def test_save_payload_contains_vocab_and_merges(bpe_tok: BPETokenizer, workdir) -> None:
    path = bpe_tok.save(workdir / "bpe.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["kind"] == "bpe"
    assert payload["num_merges"] == len(bpe_tok.merges)
    assert len(payload["merges"]) == len(bpe_tok.merges)
    assert payload["merges"][0] == list(bpe_tok.merges[0])


def test_load_roundtrip_keeps_behaviour(bpe_tok: BPETokenizer, workdir) -> None:
    path = bpe_tok.save(workdir / "bpe.json")
    loaded = BPETokenizer.load(path)
    assert loaded.id_to_token == bpe_tok.id_to_token
    assert loaded.merges == bpe_tok.merges  # 顺序必须原样回来，否则编码结果会变
    assert loaded.encode(IN_VOCAB_SENTENCE) == bpe_tok.encode(IN_VOCAB_SENTENCE)
    assert loaded.decode(loaded.encode(IN_VOCAB_SENTENCE)) == IN_VOCAB_SENTENCE


def test_load_rejects_wrong_kind(bpe_tok: BPETokenizer, workdir) -> None:
    path = workdir / "wrong.json"
    path.write_text(json.dumps({"kind": "char", "vocab": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="类型不匹配"):
        BPETokenizer.load(path)


def test_saved_and_loaded_agree_on_mixed_text(mixed_text: str, corpus: str, workdir) -> None:
    text = corpus + "\n" + mixed_text
    tok = BPETokenizer.train(text, CharTokenizer.build(text).vocab_size + 200)
    loaded = BPETokenizer.load(tok.save(workdir / "bpe.json"))
    assert loaded.pieces(mixed_text) == tok.pieces(mixed_text)
