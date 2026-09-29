#!/usr/bin/env python3
"""Demo 07 —— DecoderStack：堆叠 N 层 + 最终 LayerNorm + 输出投影 → logits。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_07_decoder.py

输出同时打到 stdout 和 demos/out/demo_07_decoder.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import DecoderStack, TokenEmbedding, PositionalEncoding, combine  # noqa: E402
from tokenizer import BPETokenizer  # noqa: E402
from tokenizer.sample_corpus import SAMPLE_CORPUS  # noqa: E402

from _demo_common import run  # noqa: E402


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> int:
    np.random.seed(0)
    print("Project 06 — Mini Transformer LLM")
    print("Demo 07: DecoderStack（→ logits）")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 随机初始化的小模型（未训练，仅看形状/数值合理性）")
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    V, D, H, FF, L = tok.vocab_size, 24, 4, 64, 2
    stack = DecoderStack(d_model=D, n_heads=H, d_ff=FF, n_layers=L, vocab_size=V)
    emb = TokenEmbedding(V, D)
    pe = PositionalEncoding(D, max_len=64)
    print(f"  vocab={V}, d_model={D}, n_heads={H}, d_ff={FF}, n_layers={L}")
    print(f"  DecoderStack 参数个数 : {len(stack.parameters())}")

    rule("2. 一个句子 → logits(seq, vocab)")
    line = SAMPLE_CORPUS.splitlines()[1]  # 取一行真实语料
    ids = np.array([tok.encode(line)[:12]])
    print(f"  句子（前 12 token）：{tok.pieces(line)[:12]}")
    print(f"  ids 形状 : {ids.shape}")
    x = combine(emb, pe, ids)
    logits = stack(x, mask=None)
    print(f"  logits 形状 : {logits.data.shape}  (seq, vocab)")
    print(f"  logits 有限 : {np.isfinite(logits.data).all()}")

    rule("3. 每个位置预测的下一个 token（未训练 = 基本乱猜）")
    last = logits.data[0]
    top5 = np.argsort(last, axis=-1)[:, -5:][-1]  # 最后一个位置 top5
    print(f"  最后位置 logits 的 top5 预测 token：")
    for rank, tid in enumerate(reversed(top5)):
        print(f"    #{rank + 1}  {tok.id_to_token[tid]!r:>12}  (id={tid}, logit={last[-1, tid]:+.3f})")
    print(f"  随机初始下 logits 的量级 |max| ≈ {np.abs(logits.data).max():.3f}")

    rule("4. 堆叠层数不影响接口形状")
    for n in (1, 3):
        s2 = DecoderStack(d_model=D, n_heads=H, d_ff=FF, n_layers=n, vocab_size=V)
        lg = s2(combine(emb, pe, ids), mask=None)
        print(f"    n_layers={n} → logits 形状 {lg.data.shape}")

    rule("Demo 07 结束")
    print("  下一步：Demo 08 —— DataLoader（滑动窗口 + 批处理 + 补齐）。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_07_decoder.txt", main))
