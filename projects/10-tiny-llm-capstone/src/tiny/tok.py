"""Milestone 02 —— 分词器：Capstone 的第一道门，也是**唯一一处文本入口**。

分工：本模块**不重写** BPE，直接复用 P06 的 :class:`BPETokenizer`（字符级则用
:class:`CharTokenizer`）。P10 补的是「工程化」那一半 —— 因为真实项目里分词器
出的问题几乎都不在算法本身，而在下面这几件没人管的杂事：

1. **落盘与读回**：训练一次、推理无数次，模型权重和分词器必须**配套**。
   本模块把「模型 + 分词器 + 配置」三件套的落盘路径统一在 ``models/`` 下管理。
2. **词表上限 vs 字符集大小**：语料的字符集大于 ``vocab_size`` 时 P06 会抛错，
   这里提前算清楚并给出**可执行的建议**（要么调大 vocab_size，要么接受 <unk>）。
3. **可观测**：训练完只看到 loss 下降是不够的，还要能回答
   「压缩率多少」「有没有 OOV」「往返是否一致」—— 这三个数本模块全部给出。

一句话总结本层要证明的事：**分词器是可复现、可落盘、可度量的，不是玄学。**
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .config import TinyConfig
from .paths import P10_MODELS, ensure_dir, ensure_models_dir

ensure_dir(P10_MODELS)

from tokenizer import BPETokenizer, CharTokenizer, Tokenizer  # noqa: E402
from tokenizer.base import UNK_ID  # noqa: E402

__all__ = [
    "TOKENIZER_JSON",
    "build_tokenizer",
    "decode_ids",
    "encode_lines",
    "load_tokenizer",
    "oov_chars",
    "roundtrip_report",
    "save_tokenizer",
    "tokenizer_stats",
]

TOKENIZER_JSON = P10_MODELS / "tokenizer.json"


def build_tokenizer(cfg: TinyConfig, texts: "list[str] | str") -> Tokenizer:
    """按配置训练分词器。

    ``texts`` 只用于**训练词表**，所以传训练集而不是全量语料——
    用验证集一起训词表等于把验证集的信息泄漏进模型，这是最常见的隐形泄漏。
    """
    corpus = texts if isinstance(texts, str) else "\n".join(texts)
    if cfg.tokenizer.kind == "char":
        return CharTokenizer.build(corpus)
    return BPETokenizer.train(corpus, cfg.tokenizer.vocab_size, min_freq=cfg.tokenizer.min_pair_freq)


def save_tokenizer(tokenizer: Tokenizer, path: "str | Path | None" = None) -> Path:
    """落盘。

    ⚠ 这里刻意写 ``path=None`` 而不是 ``path=TOKENIZER_JSON``：**默认参数在
    ``def`` 时就绑定好了**，之后测试里 ``monkeypatch.setattr(tok, "TOKENIZER_JSON", ...)``
    对它完全无效 —— 于是测试会悄悄把 char 分词器写进真实的 ``models/``，
    把 demo 的缓存毒掉。改成在**调用时**读模块全局，重定向才真的生效。
    """
    return tokenizer.save(path if path is not None else TOKENIZER_JSON)


def load_tokenizer(path: "str | Path | None" = None) -> Tokenizer:
    """从 JSON 读回分词器；按文件里的 ``kind`` 分派到对应实现。

    同样在**调用时**解析默认路径，理由见 :func:`save_tokenizer`。
    """
    import json

    payload = json.loads(Path(path if path is not None else TOKENIZER_JSON).read_text(encoding="utf-8"))
    kind = payload.get("kind", "bpe")
    if kind == "char":
        return CharTokenizer.load(path if path is not None else TOKENIZER_JSON)
    if kind == "bpe":
        return BPETokenizer.load(path if path is not None else TOKENIZER_JSON)
    raise ValueError(f"未知的分词器类型：{kind!r}")


def encode_lines(tokenizer: Tokenizer, lines: "list[str]") -> "list[list[int]]":
    return [list(map(int, tokenizer.encode(line))) for line in lines]


def decode_ids(tokenizer: Tokenizer, ids: "list[int]") -> str:
    return tokenizer.decode(ids, skip_special=True)


def oov_chars(tokenizer: Tokenizer, text: str) -> list[str]:
    """语料里**不在词表中**的字符（会被编码成 ``<unk>``）。

    为什么单独列出来：OOV 会静默地把两个不同的字塌缩成同一个 id，
    模型看到的世界就少了一维。宁可先看清楚再决定要不要调大词表。
    """
    known = set(tokenizer.id_to_token)
    return sorted({ch for ch in text if ch not in known and ch.strip()})


def roundtrip_report(tokenizer: Tokenizer, lines: "list[str]") -> dict:
    """往返一致性：``decode(encode(s)) == s`` 的比例，并**归因**失败原因。

    这是分词器的**最基本正确性**。它一旦不成立，后面所有训练都是在学噪声。

    本项目实测到的一类失败很典型：词表只用**训练集**构建，于是验证集里那些
    没见过的字符会变成 ``<unk>``，解码时被丢掉 → 往返失败。所以这里把失败
    分成两类：``unk_caused``（词表覆盖问题，可度量、可接受）和
    ``other``（真正的实现 bug，必须为零）。
    """
    mismatches: list[dict] = []
    unk_caused = 0
    for line in lines:
        ids = list(map(int, tokenizer.encode(line)))
        recovered = decode_ids(tokenizer, ids)
        if recovered == line:
            continue
        missing = sorted({ch for ch in line if ch not in set(tokenizer.id_to_token)})
        caused_by_unk = bool(missing) and all(ch not in recovered for ch in missing)
        unk_caused += int(caused_by_unk)
        mismatches.append(
            {"source": line, "recovered": recovered, "missing_chars": missing,
             "unk_caused": caused_by_unk}
        )
    total = max(len(lines), 1)
    return {
        "total": len(lines),
        "ok": len(lines) - len(mismatches),
        "mismatches": mismatches[:5],
        "pass_rate": (len(lines) - len(mismatches)) / total,
        "unk_caused": unk_caused,
        "other_caused": len(mismatches) - unk_caused,
        "all_failures_explained_by_oov": unk_caused == len(mismatches),
    }


def tokenizer_stats(tokenizer: Tokenizer, lines: "list[str]") -> dict:
    """分词器的三个关键度量：词表大小、压缩率、UNK 率。"""
    text = "\n".join(lines)
    chars = len(text)
    token_counts = [len(tokenizer.encode(line)) for line in lines]
    tokens = int(sum(token_counts))
    ids: list[int] = []
    for line in lines:
        ids.extend(tokenizer.encode(line))
    unk = int(sum(1 for i in ids if i == UNK_ID))
    lengths = np.asarray(token_counts, dtype=np.float64) if token_counts else np.zeros(1)
    return {
        "vocab_size": int(tokenizer.vocab_size),
        "lines": len(lines),
        "chars": chars,
        "tokens": tokens,
        "chars_per_token": chars / tokens if tokens else 0.0,
        "tokens_per_line_mean": float(lengths.mean()),
        "tokens_per_line_max": int(lengths.max()) if token_counts else 0,
        "unk_tokens": unk,
        "unk_rate": unk / tokens if tokens else 0.0,
        "oov_chars": oov_chars(tokenizer, text),
    }


def ensure_tokenizer(cfg: TinyConfig, texts: "list[str]", path: "str | Path | None" = None):
    """训练并落盘；**已存在就直接读回**。

    为什么缓存：词表一旦变化，之前训好的权重全部错位。所有 demo 共用同一个
    分词器，对比才有意义（和 P08 缓存基座的道理一样）。

    ``path=None`` 表示用模块级 :data:`TOKENIZER_JSON`（调用时解析，便于测试重定向）。
    """
    target = Path(path if path is not None else TOKENIZER_JSON)
    if target.is_file():
        return load_tokenizer(target), False
    tokenizer = build_tokenizer(cfg, texts)
    save_tokenizer(tokenizer, target)
    return tokenizer, True
