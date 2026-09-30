#!/usr/bin/env python
"""M02 · Tokenizer：词表怎么来的、压缩了多少、会不会丢字。

分词器是整条链路的入口，也是**最容易静默出错**的一环：词表一变，
之前训好的权重全部错位，而日志上一个字都不会说。所以本章除了展示
「训练出来了」，还要回答四个问题：

1. 词表由什么构成？  2. 压缩了多少？  3. 往返是否一致？  4. 不致的失败能不能归因？
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import TOKENIZER_JSON, build_cfg, corpus_split, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.tok import (  # noqa: E402
    load_tokenizer,
    oov_chars,
    roundtrip_report,
    tokenizer_stats,
)


def main() -> None:
    with Printer("demo_02_tokenizer") as out:
        out.section("M02 · Tokenizer：BPE 词表、压缩率与往返一致性")

        cfg = build_cfg()
        _raw, kept, train_lines, val_lines, _clean = corpus_split(cfg)
        cfg, tokenizer, dataset, model, _report, cache = ensure_bundle(cfg)

        out.subsection("1. 词表构成（4 个特殊 token + 基础字符 + 合并）")
        merges = list(tokenizer.merges)
        base = int(tokenizer.base_vocab_size)
        out.kv("分词器类型", tokenizer.kind)
        out.kv("词表大小", tokenizer.vocab_size)
        out.kv("基础部分（特殊 + 字符）", base)
        out.kv("学到的合并规则", len(merges))
        out.kv("落盘文件", TOKENIZER_JSON.name, f"缓存命中={not cache['tokenizer_trained']}")
        out.kv("读回后编码是否一致", load_tokenizer(TOKENIZER_JSON).encode("什么是 LoRA？") == tokenizer.encode("什么是 LoRA？"))

        out.subsection("2. 前 8 条合并规则（BPE 到底学了什么）")
        for index, (left, right) in enumerate(merges[:8], start=1):
            out.kv(f"#{index}", f"{left!r} + {right!r} → {left + right!r}")

        out.subsection("3. 压缩率：BPE vs 一字一 token")
        stats = tokenizer_stats(tokenizer, kept)
        char_tokens = stats["chars"]  # 含换行，与 chars 同一口径
        out.kv("语料字符数", stats["chars"])
        out.kv("BPE token 数", stats["tokens"])
        out.kv("字符级 token 数（上界）", char_tokens)
        out.kv("压缩率 chars/token", f"{stats['chars_per_token']:.3f}")
        out.kv("节省 token", f"{(1 - stats['tokens'] / char_tokens) * 100:.2f}%")
        out.kv("单行 token 数 均值/最大", f"{stats['tokens_per_line_mean']:.1f} / {stats['tokens_per_line_max']}")

        out.subsection("4. 切词示例（模型「眼里」的文本长什么样）")
        sample = "问：什么是 KV Cache？答：KV Cache 缓存已算过的 K 和 V。"
        pieces = tokenizer.pieces(sample)
        out.kv("原文", sample)
        out.kv("token 数", len(pieces))
        out.line("  pieces = " + " | ".join(pieces[:28]))

        out.subsection("5. 往返一致性：训练集必须 100%，验证集的失败必须能归因")
        train_rt = roundtrip_report(tokenizer, train_lines)
        val_rt = roundtrip_report(tokenizer, val_lines)
        out.kv("训练集行数 / 成功", f"{train_rt['total']} / {train_rt['ok']}")
        out.kv("训练集通过率", f"{train_rt['pass_rate'] * 100:.2f}%")
        out.kv("验证集行数 / 成功", f"{val_rt['total']} / {val_rt['ok']}")
        out.kv("验证集通过率", f"{val_rt['pass_rate'] * 100:.2f}%")
        out.kv("失败归因：OOV 导致", val_rt["unk_caused"])
        out.kv("失败归因：其它（应为 0）", val_rt["other_caused"])
        out.kv("全部失败都能用 OOV 解释", val_rt["all_failures_explained_by_oov"])
        if val_rt["mismatches"]:
            bad = val_rt["mismatches"][0]
            out.kv("反例原文", bad["source"][:40])
            out.kv("反例还原", bad["recovered"][:40])
            out.kv("丢失的字符", "".join(bad["missing_chars"]))

        out.subsection("6. OOV 率与词表覆盖")
        all_stats = tokenizer_stats(tokenizer, kept)
        out.kv("UNK token 数 / 占比", f"{all_stats['unk_tokens']} / {all_stats['unk_rate'] * 100:.3f}%")
        oov = oov_chars(tokenizer, "".join(kept))
        out.kv("语料里未进词表的字符", f"{len(oov)} 个", "".join(oov[:12]))
        out.kv("训练集已覆盖字符", f"{len(set(''.join(train_lines)))}")

        out.subsection("关键数字")
        out.kv("词表", f"{tokenizer.vocab_size} = 4 + {base - 4} 字符 + {len(merges)} 合并")
        out.kv("压缩率", f"{stats['chars_per_token']:.3f} chars/token（省 {(1 - stats['tokens'] / char_tokens) * 100:.2f}% token）")
        out.kv("往返", f"训练集 {train_rt['pass_rate'] * 100:.2f}% / 验证集 {val_rt['pass_rate'] * 100:.2f}%")
        out.kv("验证集失败归因", f"{val_rt['unk_caused']} 条全部由 OOV 引起，实现 bug {val_rt['other_caused']} 条")


if __name__ == "__main__":
    main()
