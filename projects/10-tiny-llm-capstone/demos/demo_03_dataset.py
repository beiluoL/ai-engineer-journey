#!/usr/bin/env python
"""M03 · Dataset：从 295 行语料到 243 个可训练样本。

这一层要证明三件事：**切分没有泄漏**、**目标真的右移了一位**、**padding 真的被 mask 掉**。
这三件事任何一件错了，训练都会「正常收敛」—— 只是收敛到一个错的地方。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, corpus_split, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.data import (  # noqa: E402
    batch_iter,
    leakage_check,
    make_examples,
    pad_batch,
)
from tiny.tok import encode_lines  # noqa: E402
from tokenizer.base import EOS_ID, PAD_ID  # noqa: E402


def main() -> None:
    with Printer("demo_03_dataset") as out:
        out.section("M03 · Dataset：清洗 → 无泄漏切分 → 滑窗打包 → padding mask")

        cfg = build_cfg()
        raw, kept, train_lines, val_lines, clean = corpus_split(cfg)
        cfg, tokenizer, dataset, model, _report, _cache = ensure_bundle(cfg)

        out.subsection("1. 清洗（空行 / 超短行 / 重复行）")
        out.kv("原始行数", clean["input_lines"], "含 P06 通用语料")
        out.kv("保留行数", clean["kept"])
        out.kv("丢弃：短于 min_chars", clean["dropped_short"], f"min_chars={cfg.data.min_chars}")
        out.kv("丢弃：重复行", clean["dropped_dup"])

        out.subsection("2. 切分与泄漏检查（val 里出现 train 的行 = 指标虚高）")
        leak = leakage_check(train_lines, val_lines)
        out.kv("train / val 行数", f"{len(train_lines)} / {len(val_lines)}")
        out.kv("val_ratio", cfg.data.val_ratio)
        out.kv("交集行数（应为 0）", leak["overlap"])
        out.kv("数据集是否干净", leak["clean"])

        out.subsection("3. 编码后的 token 账")
        train_ids = encode_lines(tokenizer, train_lines)
        val_ids = encode_lines(tokenizer, val_lines)
        train_tokens = sum(len(ids) for ids in train_ids)
        val_tokens = sum(len(ids) for ids in val_ids)
        lengths = np.array([len(ids) for ids in train_ids])
        out.kv("train / val token 数", f"{train_tokens} / {val_tokens}")
        out.kv("单行 token 数 均值/中位/最大",
               f"{lengths.mean():.1f} / {np.median(lengths):.0f} / {lengths.max()}")
        out.kv("超过 max_len 的行占比", f"{dataset.meta['max_len_truncated_rate'] * 100:.2f}%",
               f"max_len={cfg.model.max_len}")

        out.subsection("4. 滑窗打包：样本从哪来（pack=True）")
        out.kv("pack 模式", cfg.data.pack)
        out.kv("窗口长 / 步长", f"{cfg.model.max_len} / {cfg.data.stride}")
        out.kv("train 样本数", len(dataset.train_examples))
        out.kv("val 样本数", len(dataset.val_examples))
        packed = dataset.train_examples[0]
        out.kv("单个样本形状 x/y/mask", f"{packed[0].shape} / {packed[1].shape} / {packed[2].shape}")
        out.line("  x    =" + " ".join(str(int(i)) for i in packed[0][:10]) + " ...")
        out.line("  y    =" + " ".join(str(int(i)) for i in packed[1][:10]) + " ...")
        out.kv("y 是否等于 x 右移一位", bool(np.array_equal(packed[0][1:], packed[1][:-1])))
        flat = list(dataset.train_examples[0][0]) + list(dataset.train_examples[1][0])
        out.kv("样本之间插入 <eos>", int(EOS_ID) in flat,
               "不插的话模型会学到跨句子的假因果")

        out.subsection("5. padding 与 mask（不 mask 就等于让模型去预测 <pad>）")
        unpacked = make_examples(train_ids[:4], cfg.model.max_len, pack=False)
        x, y, mask = pad_batch(unpacked)
        out.kv("batch 形状", f"{x.shape}", f"batch=4, 长度按本批最长补齐")
        out.kv("padding 用的 id", PAD_ID)
        out.kv("mask 中 1 的比例", f"{mask.mean() * 100:.1f}%", "其余位置 loss 不计入")
        out.line("  mask[0] = " + " ".join("1" if value > 0.5 else "0" for value in mask[0][:24]))
        out.line("  x[0]    = " + " ".join(str(int(i)) for i in x[0][:24]))
        out.kv("padding 位置是否用了 PAD_ID", bool((x[mask == 0] == PAD_ID).all()))

        out.subsection("6. batch 迭代")
        batches = list(batch_iter(dataset.train_examples, cfg.train.batch_size))
        out.kv("batch_size", cfg.train.batch_size)
        out.kv("每轮 batch 数", len(batches))
        out.kv("样本覆盖率", f"{sum(b[0].shape[0] for b in batches)} / {len(dataset.train_examples)}")
        out.kv("1200 步 ≈ 多少个 epoch", f"{1200 / len(batches):.1f}")

        out.subsection("关键数字")
        out.kv("语料", f"{clean['input_lines']} → 清洗后 {clean['kept']} 行")
        out.kv("切分", f"train {len(train_lines)} / val {len(val_lines)}，泄漏 {leak['overlap']} 行")
        out.kv("样本", f"train {len(dataset.train_examples)} / val {len(dataset.val_examples)}")
        out.kv("不变量", "y = x 右移一位；padding 位置 mask=0；样本间插 <eos>")


if __name__ == "__main__":
    main()
