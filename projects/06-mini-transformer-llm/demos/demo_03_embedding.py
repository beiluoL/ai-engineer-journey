#!/usr/bin/env python3
"""Demo 03 —— Embedding：把 token 的 id 变成向量，再叠上位置编码。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_03_embedding.py

输出同时打到 stdout 和 demos/out/demo_03_embedding.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import PositionalEncoding, TokenEmbedding, combine  # noqa: E402
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
    print("Demo 03: Embedding（TokenEmbedding + PositionalEncoding + combine）")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 词表与模型尺寸")
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    V, D = tok.vocab_size, 16
    print(f"  vocab_size = {V}")
    print(f"  d_model    = {D}")
    print(f"  词表里前 6 个 token：{tok.id_to_token[:6]}")

    rule("2. TokenEmbedding：id → (seq, d_model)")
    emb = TokenEmbedding(vocab_size=V, d_model=D)
    print(f"  权重形状 W_e         : {emb.weight.data.shape}  (V, d_model)")
    ids = np.array(tok.encode("Transformer")[:8])
    print(f"  输入 ids（前 8）      : {ids.tolist()}")
    x = emb(ids)
    print(f"  输出形状             : {x.data.shape}  (seq, d_model)")
    print(f"  查表正确性：out[0] 是否等于 W_e[ids[0]] : "
          f"{np.allclose(x.data[0], emb.weight.data[ids[0]])}")
    print("\n  第 0 个 token 的嵌入向量（前 8 维）：")
    print("    " + " ".join(f"{v:+.3f}" for v in x.data[0, :8]))

    rule("3. PositionalEncoding：正弦函数位置指纹")
    pe = PositionalEncoding(d_model=D, max_len=64)
    p0 = pe(8)
    print(f"  位置编码形状          : {p0.data.shape}  (seq, d_model)")
    print(f"  pe[0] 偶数列=sin(0)=0，奇数列=cos(0)=1 的校验：")
    print(f"    pe[0,0] = {p0.data[0,0]:+.4f}  (期望 ≈ 0)")
    print(f"    pe[0,1] = {p0.data[0,1]:+.4f}  (期望 ≈ 1)")
    print(f"    pe[1,0] = {p0.data[1,0]:+.4f}  (= sin(1/10000^(0/d)))")
    print("  pe[0] 前 8 维：")
    print("    " + " ".join(f"{v:+.3f}" for v in p0.data[0, :8]))

    rule("4. combine：token 嵌入 + 位置编码")
    xc = combine(emb, pe, ids)
    print(f"  combine 输出形状      : {xc.data.shape}  (seq, d_model)")
    # 验证 add 的广播：位置编码 (seq,D) 被加到 token 嵌入 (seq,D)
    want = emb(ids).data + pe(len(ids)).data
    print(f"  combine == token + pos : {np.allclose(xc.data, want)}")
    print("\n  combine 后第 0 个位置向量（前 8 维）：")
    print("    " + " ".join(f"{v:+.3f}" for v in xc.data[0, :8]))

    rule("5. 批处理形状（B, T, D）")
    ids_b = np.array([tok.encode("Transformer")[:6], tok.encode("模型")[:6]])
    xb = combine(emb, pe, ids_b)
    print(f"  两个不同长度句子补齐后 ids 形状 : {ids_b.shape}")
    print(f"  combine 批处理输出形状          : {xb.data.shape}  (B, T, d_model)")

    rule("Demo 03 结束")
    print("  下一步：Demo 04 —— 注意力机制（缩放点积 + 因果掩码）。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_03_embedding.txt", main))
