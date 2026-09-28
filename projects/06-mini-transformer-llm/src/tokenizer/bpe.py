"""BPE（Byte Pair Encoding）子词分词器 —— 从零实现的训练循环。

核心只有一句话：**反复合并语料里出现次数最多的那对相邻符号**。

```
初始：每个字符是一个符号
  ↓  统计所有相邻 pair 的出现次数
  ↓  把次数最多的 pair (a, b) 合并成新符号 "ab"，写进词表、记进 merges
  ↓  用这条规则改写整份语料
  ↓  重复，直到词表达到 vocab_size 或没有可合并的 pair
```

训练出来的 ``merges`` 是**有序**的：先学的合并优先级更高。encode 时按这个
优先级把字符串一路合并回去 —— 顺序错了结果就不一样，所以 merges 必须按序保存。

为什么 LLM 都用子词而不是字符或词：
- 字符级：词表小，但序列太长（Attention 是 O(n²)）
- 词级：序列短，但词表爆炸且全是 `<unk>`（"transformer" 的复数没见过就废了）
- 子词：词表可控 + 序列可控 + 几乎不产生 `<unk>`
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Sequence

from .base import SPECIAL_TOKENS, Tokenizer, _as_text

#: 预切分规则：先把文本切成「word」，BPE 只在 word 内部合并，绝不跨空格。
#: 顺序有意义 —— 空白单独成词（所以它永远不会被并进别的 token），
#: 汉字**成串**成词（和 GPT-2 一样：中文没有空格，一整串汉字就是一个 word，
#: BPE 在串内学出「模型」「注意力」这类二字词；若逐字切开就永远合并不了），
#: 最后的 ``.`` 是兜底，保证任何字符都不会被丢掉（否则解码就回不去了）。
_WORD_RE = re.compile(
    r"\s"                       # 空白字符单独成 token
    r"|[A-Za-z]+"               # 连续英文
    r"|[0-9]+"                  # 连续数字
    r"|[\u4e00-\u9fff]+"        # 连续汉字：整串当一个 word
    r"|[\u3000-\u303f\uff00-\uffef]"  # 中文标点 / 全角符号
    r"|.",                      # 兜底：其它任意单字符
)


class BPETokenizer(Tokenizer):
    """子词分词器：词表 = 基础字符 + 训练学到的合并 token + 4 个特殊 token。"""

    kind = "bpe"

    def __init__(self, vocab: dict[str, int], merges: Sequence[tuple[str, str]]) -> None:
        self._vocab = dict(vocab)
        for i, tok in enumerate(SPECIAL_TOKENS):
            if self._vocab.get(tok) != i:
                raise ValueError(f"词表前 4 个必须是 {SPECIAL_TOKENS}，{tok} 的 id 不对")
        self._merges: list[tuple[str, str]] = [tuple(m) for m in merges]  # type: ignore[arg-type]
        self._ranks: dict[tuple[str, str], int] = {
            pair: rank for rank, pair in enumerate(self._merges)
        }
        self._id_to_token: list[str] = [""] * len(self._vocab)
        for tok, i in self._vocab.items():
            if i >= len(self._id_to_token):
                raise ValueError(f"id {i} 超出词表长度 {len(self._id_to_token)}")
            self._id_to_token[i] = tok
        self._cache: dict[str, list[str]] = {}

    # ---------- 训练 ----------

    @classmethod
    def train(
        cls,
        corpus: str | Sequence[str],
        vocab_size: int,
        *,
        min_freq: int = 1,
    ) -> "BPETokenizer":
        """从语料训练一个 BPE 词表。

        - ``vocab_size`` 是**硬上限**：基础字符已经超过它就报错，而不是假装成功。
        - 可合并的 pair 用光了就**优雅停**：词表会比请求的小，不抛异常。
          （小语料上这是常态，比如 1KB 语料请求 5000 词表。）
        - ``min_freq`` 先压掉低频 word，避免为只出现一次的怪串单独造 token。
        """
        if vocab_size < len(SPECIAL_TOKENS):
            raise ValueError(f"vocab_size 至少要放下 {len(SPECIAL_TOKENS)} 个特殊 token")

        text = _as_text(corpus)
        word_counts = Counter(cls._pre_tokenize(text))
        if min_freq > 1:
            word_counts = Counter(
                {w: c for w, c in word_counts.items() if c >= min_freq}
            )
        vocab: dict[str, int] = {tok: i for i, tok in enumerate(SPECIAL_TOKENS)}
        for ch in sorted({ch for word in word_counts for ch in word}):
            vocab.setdefault(ch, len(vocab))
        if len(vocab) > vocab_size:
            raise ValueError(
                f"vocab_size={vocab_size} 太小：光基础字符就有 {len(vocab)} 个"
            )

        # 每个 word 表示成符号元组，带上出现次数 —— 之后每次合并只改这里
        symbols: dict[tuple[str, ...], int] = {
            tuple(word): count for word, count in word_counts.items()
        }
        merges: list[tuple[str, str]] = []

        while len(vocab) < vocab_size:
            pairs = cls._count_pairs(symbols)
            if not pairs:
                break  # 没有可合并的 pair 了：优雅停止
            # 频次优先；同频次按字典序取小的那个，保证同一份语料训练两次结果完全一致
            best = min(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            new_token = best[0] + best[1]
            vocab[new_token] = len(vocab)
            merges.append(best)
            symbols = cls._merge_everywhere(symbols, best, new_token)

        return cls(vocab, merges)

    @staticmethod
    def _pre_tokenize(text: str) -> list[str]:
        """把整段文本切成 word 列表（含单独成词的空白字符）。"""
        return _WORD_RE.findall(text)

    @staticmethod
    def _count_pairs(symbols: dict[tuple[str, ...], int]) -> Counter:
        """统计相邻 pair 的加权出现次数（按 word 频次加权）。"""
        pairs: Counter = Counter()
        for word, freq in symbols.items():
            for i in range(len(word) - 1):
                pairs[(word[i], word[i + 1])] += freq
        return pairs

    @staticmethod
    def _merge_everywhere(
        symbols: dict[tuple[str, ...], int],
        pair: tuple[str, str],
        new_token: str,
    ) -> dict[tuple[str, ...], int]:
        """把一条合并规则应用到全部 word，返回新的符号表。"""
        left, right = pair
        merged: dict[tuple[str, ...], int] = {}
        for word, freq in symbols.items():
            out: list[str] = []
            i = 0
            while i < len(word):
                if i < len(word) - 1 and word[i] == left and word[i + 1] == right:
                    out.append(new_token)
                    i += 2
                else:
                    out.append(word[i])
                    i += 1
            merged[tuple(out)] = freq
        return merged

    # ---------- 词表 ----------

    @property
    def id_to_token(self) -> list[str]:
        return list(self._id_to_token)

    @property
    def vocab(self) -> dict[str, int]:
        return dict(self._vocab)

    @property
    def merges(self) -> list[tuple[str, str]]:
        """有序合并规则，下标即优先级（越小越先学）。"""
        return list(self._merges)

    @property
    def base_vocab_size(self) -> int:
        """特殊 token + 基础字符的数量（不含学到的合并）。"""
        return self.vocab_size - len(self._merges)

    # ---------- 编码 ----------

    def _encode_word(self, word: str) -> list[str]:
        """把一个 word 按 merges 的优先级一路合并到不能再合并。"""
        cached = self._cache.get(word)
        if cached is not None:
            return list(cached)
        out = list(word)
        while len(out) > 1:
            best_rank, best_i = None, -1
            for i in range(len(out) - 1):
                rank = self._ranks.get((out[i], out[i + 1]))
                if rank is not None and (best_rank is None or rank < best_rank):
                    best_rank, best_i = rank, i
            if best_rank is None:
                break
            out[best_i : best_i + 2] = [out[best_i] + out[best_i + 1]]
        self._cache[word] = out
        return list(out)

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        unk = self._vocab["<unk>"]
        ids: list[int] = []
        for word in self._pre_tokenize(text):
            for token in self._encode_word(word):
                ids.append(self._vocab.get(token, unk))
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
                "base_vocab_size": self.base_vocab_size,
                "num_merges": len(self._merges),
                "vocab": self._vocab,
                # JSON 没有 tuple，存成二元组列表；顺序即优先级，不能排序
                "merges": [list(m) for m in self._merges],
            },
        )

    @classmethod
    def load(cls, path: str | Path) -> "BPETokenizer":
        payload = cls._read_json(path)
        if payload.get("kind") != cls.kind:
            raise ValueError(
                f"词表类型不匹配：文件是 {payload.get('kind')!r}，期望 {cls.kind!r}"
            )
        return cls(payload["vocab"], [tuple(m) for m in payload["merges"]])
