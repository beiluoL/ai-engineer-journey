"""字符级分词器的测试：词表构造 / 往返一致性 / 特殊 token / 落盘。"""

from __future__ import annotations

import json

import pytest

from tokenizer import SPECIAL_TOKENS, CharTokenizer


# ---------- 词表构造 ----------


def test_special_tokens_occupy_first_ids(char_tok: CharTokenizer) -> None:
    assert char_tok.id_to_token[:4] == list(SPECIAL_TOKENS)
    assert (char_tok.vocab["<pad>"], char_tok.vocab["<unk>"]) == (0, 1)
    assert (char_tok.vocab["<bos>"], char_tok.vocab["<eos>"]) == (2, 3)


def test_vocab_size_is_specials_plus_unique_chars(corpus: str, char_tok: CharTokenizer) -> None:
    assert char_tok.vocab_size == 4 + len(set(corpus))


def test_build_accepts_list_of_lines() -> None:
    lines = ["第一行 abc 123", "第二行 def 456"]
    tok = CharTokenizer.build(lines)
    # 多行语料按 "\n" 拼接，所以换行符本身也会进词表
    assert tok.vocab_size == CharTokenizer.build("\n".join(lines)).vocab_size
    assert tok.vocab_size == 4 + len(set("\n".join(lines)))


def test_build_empty_corpus_only_has_specials() -> None:
    tok = CharTokenizer.build("")
    assert tok.vocab_size == 4
    assert tok.encode("任") == [1]  # 全都是 unk


def test_min_freq_drops_rare_chars() -> None:
    corpus = "啊啊啊 啊啊啊 哦"
    tok_freq1 = CharTokenizer.build(corpus)
    tok_freq2 = CharTokenizer.build(corpus, min_freq=2)
    assert tok_freq1.vocab_size == 4 + len({"啊", "哦", " "})
    assert tok_freq2.vocab_size == 4 + len({"啊", " "})  # "哦" 只出现一次，被压掉
    assert tok_freq2.encode("哦") == [1]


def test_vocab_is_sorted_by_frequency(corpus: str, char_tok: CharTokenizer) -> None:
    # 空格在语料里出现最多，应排在普通字符的第一位（id=4）
    most_common_char = max(set(corpus), key=corpus.count)
    assert char_tok.vocab[most_common_char] == 4


def test_constructor_rejects_broken_vocab() -> None:
    with pytest.raises(ValueError, match="前 4 个"):
        CharTokenizer({"<pad>": 1, "<unk>": 0, "<bos>": 2, "<eos>": 3})


# ---------- 往返一致性 ----------


def test_roundtrip_chinese(char_tok: CharTokenizer) -> None:
    s = "注意力机制让模型自己决定该看哪里"
    assert char_tok.decode(char_tok.encode(s)) == s


def test_roundtrip_mixed_chinese_english_digits(char_tok: CharTokenizer) -> None:
    s = "Transformer 在 2017 年被提出，复杂度是 O(n^2)。"
    assert char_tok.decode(char_tok.encode(s)) == s


def test_roundtrip_empty_string(char_tok: CharTokenizer) -> None:
    assert char_tok.encode("") == []
    assert char_tok.decode([]) == ""


def test_roundtrip_newlines_and_spaces(char_tok: CharTokenizer) -> None:
    s = "Attention\n2017 年\n"
    assert char_tok.decode(char_tok.encode(s)) == s


def test_out_of_vocab_char_maps_to_unk(char_tok: CharTokenizer) -> None:
    ids = char_tok.encode("𝕏")  # 语料里绝不可能出现的字符
    assert ids == [1]
    assert char_tok.decode(ids) == "<unk>"


def test_encode_is_char_by_char(char_tok: CharTokenizer) -> None:
    assert char_tok.encode("模型") == [char_tok.vocab["模"], char_tok.vocab["型"]]


# ---------- 特殊 token ----------


def test_add_special_tokens_wraps_bos_eos(char_tok: CharTokenizer) -> None:
    ids = char_tok.encode("模型", add_special_tokens=True)
    assert ids[0] == 2 and ids[-1] == 3
    assert char_tok.decode(ids, skip_special=True) == "模型"


def test_skip_special_keeps_them_when_false(char_tok: CharTokenizer) -> None:
    ids = char_tok.encode("模型", add_special_tokens=True)
    assert char_tok.decode(ids) == "<bos>模型<eos>"


def test_pieces_returns_token_strings(char_tok: CharTokenizer) -> None:
    assert char_tok.pieces("ab") == ["a", "b"]


def test_count_tokens_matches_encode(char_tok: CharTokenizer) -> None:
    assert char_tok.count_tokens("你好世界") == 4


# ---------- 越界与类型 ----------


def test_decode_rejects_out_of_range_id(char_tok: CharTokenizer) -> None:
    with pytest.raises(ValueError, match="越界"):
        char_tok.decode([char_tok.vocab_size])


def test_decode_rejects_non_int_id(char_tok: CharTokenizer) -> None:
    with pytest.raises(TypeError):
        char_tok.decode(["1"])  # type: ignore[list-item]


# ---------- 落盘 ----------


def test_save_writes_readable_json(char_tok: CharTokenizer, workdir) -> None:
    path = char_tok.save(workdir / "char_vocab.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["kind"] == "char"
    assert payload["vocab_size"] == char_tok.vocab_size
    assert "<unk>" in payload["vocab"]


def test_save_creates_parent_directory(char_tok: CharTokenizer, workdir) -> None:
    path = char_tok.save(workdir / "nested" / "deep" / "vocab.json")
    assert path.exists()


def test_load_roundtrip_keeps_behaviour(char_tok: CharTokenizer, workdir) -> None:
    path = char_tok.save(workdir / "char_vocab.json")
    loaded = CharTokenizer.load(path)
    assert loaded.vocab_size == char_tok.vocab_size
    assert loaded.id_to_token == char_tok.id_to_token
    s = "Attention 让模型自己决定看哪里。"
    assert loaded.encode(s) == char_tok.encode(s)
    assert loaded.decode(loaded.encode(s)) == s


def test_load_rejects_wrong_kind(char_tok: CharTokenizer, workdir) -> None:
    path = workdir / "wrong.json"
    path.write_text(json.dumps({"kind": "bpe", "vocab": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="类型不匹配"):
        CharTokenizer.load(path)


def test_load_missing_file(workdir) -> None:
    with pytest.raises(FileNotFoundError):
        CharTokenizer.load(workdir / "nope.json")
