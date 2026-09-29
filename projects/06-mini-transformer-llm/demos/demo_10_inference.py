#!/usr/bin/env python3
"""Demo 10 —— 推理生成：greedy / temperature / top-k 三种采样策略。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_10_inference.py

输出同时打到 stdout 和 demos/out/demo_10_inference.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import (  # noqa: E402
    Adam,
    DataLoader,
    TransformerLM,
    Trainer,
    examples_from_lines,
    generate,
    generate_ids,
)
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
    print("Demo 10: Inference（贪心 / 温度 / top-k 采样）")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 训练一个玩具模型（与 Demo 09 同配置）")
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    id_lines = [tok.encode(ln) for ln in SAMPLE_CORPUS.splitlines() if ln.strip()]
    loader = DataLoader(examples_from_lines(id_lines, context_len=16), batch_size=16, shuffle=True)
    m = TransformerLM(vocab_size=tok.vocab_size, d_model=24, n_heads=4, d_ff=64, n_layers=2, max_len=64)
    losses = Trainer(m, Adam(m.parameters(), lr=0.02)).run(loader, n_steps=120, log_every=0)
    print(f"  训练后 loss ≈ {losses[-1]:.4f}（初始 ≈ {losses[0]:.4f}）")

    rule("2. 贪心生成（temperature ≤ 0 → 取 argmax，最确定）")
    prompt = "Transformer"
    greedy = generate(m, tok, prompt, max_new_tokens=15, temperature=0.0)
    gids = generate_ids(m, tok, prompt, max_new_tokens=15, temperature=0.0)
    print(f"  prompt        : {prompt!r}")
    print(f"  贪心生成文本  : {greedy!r}")
    print(f"  生成 token 数 : {len(gids) - len(tok.encode(prompt))}  (≤ 15)")
    print(f"  全部在词表内  : {all(0 <= i < tok.vocab_size for i in gids)}")

    rule("3. 温度采样（temperature > 0，越高温越随机）")
    rng = np.random.default_rng(0)
    t_high = generate(m, tok, prompt, max_new_tokens=15, temperature=1.2, rng=rng)
    rng = np.random.default_rng(0)
    t_low = generate(m, tok, prompt, max_new_tokens=15, temperature=0.5, rng=rng)
    print(f"  temperature=1.2 : {t_high!r}")
    print(f"  temperature=0.5 : {t_low!r}")
    print("  → 温度低更聚焦、温度高更发散，符合直觉。")

    rule("4. top-k 采样（只在概率最高的 k 个里选）")
    rng = np.random.default_rng(7)
    topk = generate(m, tok, prompt, max_new_tokens=15, temperature=0.9, top_k=20, rng=rng)
    print(f"  top_k=20 : {topk!r}")
    print("  → top-k 把长尾噪声 token 截掉，生成更干净。")

    rule("5. 多 prompt 对照（都是玩具规模，内容可能重复属正常）")
    for p in ("模型", "Attention", "token"):
        t = generate(m, tok, p, max_new_tokens=10, temperature=0.0)
        print(f"    prompt={p!r:>12} → {t!r}")

    rule("Demo 10 结束")
    print("  Project 06 完结：Tokenizer → Embedding → Block → Training → Inference 全链路跑通。")
    return 0


if __name__ == "__main__":
    sys.exit(run("demo_10_inference.txt", main))
