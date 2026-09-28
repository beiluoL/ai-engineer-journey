"""Project 06 —— tokenizer 包：文本 ↔ id 的第一道门。

    from tokenizer import CharTokenizer, BPETokenizer

    tok = CharTokenizer.build(corpus)          # 字符级：词表 = 字符集
    tok = BPETokenizer.train(corpus, 300)      # 子词级：从零跑 BPE 合并

两者共用 `src/tokenizer/base.py` 里的 `Tokenizer` 契约
（vocab_size / encode / decode / save / load），所以后面 Embedding、
训练循环、推理全都只依赖契约，换分词器不用改下游一行代码。
"""

from .base import (
    BOS_ID,
    EOS_ID,
    PAD_ID,
    SPECIAL_TOKENS,
    UNK_ID,
    Tokenizer,
)
from .bpe import BPETokenizer
from .char_tokenizer import CharTokenizer

__all__ = [
    "BOS_ID",
    "BPETokenizer",
    "CharTokenizer",
    "EOS_ID",
    "PAD_ID",
    "SPECIAL_TOKENS",
    "Tokenizer",
    "UNK_ID",
]
