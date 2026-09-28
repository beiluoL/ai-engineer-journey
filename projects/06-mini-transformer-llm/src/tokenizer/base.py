"""Tokenizer 抽象基类 —— 本项目所有分词器的统一契约。

为什么先定契约再写实现：
Token 化是整条链路的**入口**，它产出的 ``list[int]`` 会一路流到 Embedding、
Attention、训练循环和采样生成。上下游都只认这个契约，具体是字符级还是 BPE
就变成一个可以随时替换的实现细节 —— 这正是抽象存在的理由。

契约五件套：
    vocab_size   —— 词表有多大（决定 Embedding 矩阵的行数）
    encode(text) -> list[int]
    decode(ids)  -> str
    save(path)   —— 落盘（训练一次，推理无数次）
    load(path)   —— 读回（必须和训练时完全一致，否则模型全部错位）

额外约定两条，后面每个子类都必须满足：

1. **往返一致性**：对词表内的输入，`decode(encode(s)) == s`。
2. **特殊 token 固定占前 4 个 id**：`<pad>`=0 `<unk>`=1 `<bos>`=2 `<eos>`=3。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

#: 四个特殊 token，顺序即 id，任何子类都不许改这个顺序。
SPECIAL_TOKENS: tuple[str, ...] = ("<pad>", "<unk>", "<bos>", "<eos>")

PAD_ID, UNK_ID, BOS_ID, EOS_ID = 0, 1, 2, 3


class Tokenizer(ABC):
    """分词器抽象基类。

    子类只需要实现 ``id_to_token`` / ``encode`` / ``decode`` / ``save`` / ``load``，
    ``vocab_size`` 由基类从 ``id_to_token`` 推导，避免「词表和长度对不上」这类
    最容易出现、又最难查的错位。
    """

    #: 落盘 JSON 里用来区分实现的标记，子类覆盖。
    kind: str = "base"

    # ---------- 词表 ----------

    @property
    @abstractmethod
    def id_to_token(self) -> list[str]:
        """id → token 字符串，下标即 id。"""
        raise NotImplementedError

    @property
    def vocab_size(self) -> int:
        """词表大小 = Embedding 矩阵的行数。"""
        return len(self.id_to_token)

    @property
    def token_to_id(self) -> dict[str, int]:
        """token 字符串 → id（反查表，现场构造）。"""
        return {tok: i for i, tok in enumerate(self.id_to_token)}

    # ---------- 编解码 ----------

    @abstractmethod
    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        """文本 → id 序列。``add_special_tokens`` 时首尾加 ``<bos>`` / ``<eos>``。"""
        raise NotImplementedError

    @abstractmethod
    def decode(self, ids: Sequence[int], *, skip_special: bool = False) -> str:
        """id 序列 → 文本。``skip_special`` 时丢弃四个特殊 token 对应的 id。"""
        raise NotImplementedError

    # ---------- 落盘 ----------

    @abstractmethod
    def save(self, path: str | Path) -> Path:
        """写到 JSON 文件，返回落盘路径。"""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(cls, path: str | Path) -> "Tokenizer":
        """从 JSON 文件读回一个同类型分词器。"""
        raise NotImplementedError

    # ---------- 共用小工具 ----------

    def pieces(self, text: str) -> list[str]:
        """把 encode 的结果还原成 token 字符串列表 —— 调试/展示用。

        看 id 没有意义，看 `['▁trans', 'former']` 才知道模型「眼里」的词长什么样。
        """
        return [self.id_to_token[i] for i in self.encode(text)]

    def count_tokens(self, text: str) -> int:
        """这段文本会被切成几个 token（计费与上下文长度的基本单位）。"""
        return len(self.encode(text))

    def _check_ids(self, ids: Sequence[int]) -> list[str]:
        """把 id 序列变成 token 字符串，越界直接报错。

        越界静默兜底成 `<unk>` 是最糟的选择：模型会学到一个不存在的行，
        而日志上什么也看不出来。
        """
        tokens: list[str] = []
        for i in ids:
            if not isinstance(i, int) or isinstance(i, bool):
                raise TypeError(f"id 必须是 int，收到 {type(i).__name__}: {i!r}")
            if i < 0 or i >= self.vocab_size:
                raise ValueError(f"id {i} 越界（vocab_size={self.vocab_size}）")
            tokens.append(self.id_to_token[i])
        return tokens

    @staticmethod
    def _dump_json(path: str | Path, payload: dict) -> Path:
        """写 JSON：中文不转义（ensure_ascii=False），方便人眼看 diff。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return target

    @staticmethod
    def _read_json(path: str | Path) -> dict:
        """读 JSON，顺手校验落盘时写的 ``kind`` 标记。"""
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"词表文件不存在：{source}")
        return json.loads(source.read_text(encoding="utf-8"))


def _as_text(corpus: str | Sequence[str]) -> str:
    """语料既可以是整块字符串，也可以是多行列表 —— 统一成一块文本。"""
    if isinstance(corpus, str):
        return corpus
    return "\n".join(corpus)
