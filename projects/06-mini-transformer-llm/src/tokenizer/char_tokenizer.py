"""字符级分词器 —— 最简单、也最「中文友好」的一档。

为什么先写它：
中文没有空格，词边界要靠分词器自己找。字符级直接绕开这个问题 —— 一个汉字
一个 id，词表就是「见过的字符集」。它有两个不可替代的用途：

1. **基线**：后面所有子词方案都要拿它对比压缩率，否则「BPE 更好」只是口号。
2. **上限保证**：词表 = 字符集，永远不会 `<unk>` 掉一个常用字。

代价也很直白：序列长。`transformer` 这个英文单词要 12 个 token，
而 BPE 可能只要 2~3 个 —— 序列越长，Attention 的 O(n²) 越贵。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Sequence

from .base import SPECIAL_TOKENS, Tokenizer, _as_text


class CharTokenizer(Tokenizer):
    """字符级分词器：词表 = 语料里出现过的字符 + 4 个特殊 token。"""

    kind = "char"

    def __init__(self, vocab: dict[str, int]) -> None:
        """``vocab`` 是 字符 → id 的完整映射，前 4 个必须是特殊 token。"""
        self._vocab = dict(vocab)
        for i, tok in enumerate(SPECIAL_TOKENS):
            if self._vocab.get(tok) != i:
                raise ValueError(f"词表前 4 个必须是 {SPECIAL_TOKENS}，{tok} 的 id 不对")
        if len(set(self._vocab.values())) != len(self._vocab):
            raise ValueError("词表里有重复 id")
        self._id_to_token: list[str] = [""] * len(self._vocab)
        for tok, i in self._vocab.items():
            self._id_to_token[i] = tok

    # ---------- 构建 ----------

    @classmethod
    def build(cls, corpus: str | Sequence[str], *, min_freq: int = 1) -> "CharTokenizer":
        """统计语料字符集建词表。

        ``min_freq`` 用来压掉只出现过一两次的生僻字：它们既学不到表示，
        又白占一行 Embedding。被压掉的字符在 encode 时会落到 ``<unk>``。
        """
        text = _as_text(corpus)
        counts = Counter(text)
        vocab: dict[str, int] = {tok: i for i, tok in enumerate(SPECIAL_TOKENS)}
        next_id = len(SPECIAL_TOKENS)
        for ch, freq in counts.most_common():
            if freq < min_freq:
                continue
            if ch in vocab:  # 语料里真出现了 "<pad>" 这种字面量，不重复占位
                continue
            vocab[ch] = next_id
            next_id += 1
        return cls(vocab)

    # ---------- 词表 ----------

    @property
    def id_to_token(self) -> list[str]:
        return list(self._id_to_token)

    @property
    def vocab(self) -> dict[str, int]:
        """字符 → id（只读副本）。"""
        return dict(self._vocab)

    # ---------- 编解码 ----------

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        unk = self._vocab["<unk>"]
        ids = [self._vocab.get(ch, unk) for ch in text]
        if add_special_tokens:
            ids = [self._vocab["<bos>"]] + ids + [self._vocab["<eos>"]]
        return ids

    def decode(self, ids: Sequence[int], *, skip_special: bool = False) -> str:
        tokens = self._check_ids(ids)
        if skip_special:
            tokens = [t for t in tokens if t not in SPECIAL_TOKENS]
        return "".join(tokens)

    # ---------- 落盘 ----------

    def save(self, path: str | Path) -> Path:
        return self._dump_json(
            path,
            {
                "kind": self.kind,
                "version": 1,
                "vocab_size": self.vocab_size,
                "vocab": self._vocab,
            },
        )

    @classmethod
    def load(cls, path: str | Path) -> "CharTokenizer":
        payload = cls._read_json(path)
        if payload.get("kind") != cls.kind:
            raise ValueError(
                f"词表类型不匹配：文件是 {payload.get('kind')!r}，期望 {cls.kind!r}"
            )
        return cls(payload["vocab"])
