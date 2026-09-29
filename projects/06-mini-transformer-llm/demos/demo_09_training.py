#!/usr/bin/env python3
"""Demo 09 —— 训练循环：自回归 + 交叉熵，loss 肉眼可见地下降。

跑法：
    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_09_training.py

输出同时打到 stdout 和 demos/out/demo_09_training.txt。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from model import Adam, DataLoader, TransformerLM, Trainer, examples_from_lines  # noqa: E402
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
    print("Demo 09: Training（训练 loss 下降）")
    print(f"Python {sys.version.split()[0]}  |  numpy {np.__version__}")

    rule("1. 准备数据：BPE 分词 + 滑动窗口")
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    id_lines = [tok.encode(ln) for ln in SAMPLE_CORPUS.splitlines() if ln.strip()]
    loader = DataLoader(examples_from_lines(id_lines, context_len=16), batch_size=16, shuffle=True)
    print(f"  vocab_size = {tok.vocab_size}")
    print(f"  训练样本数 = {len(loader.examples)}  (由语料行滑窗得到)")
    print(f"  batch 数   ≈ {len(loader)}")

    rule("2. 构造玩具模型（d_model 小、层数少，几秒跑完）")
    V, D, H, FF, L = tok.vocab_size, 24, 4, 64, 2
    m = TransformerLM(vocab_size=V, d_model=D, n_heads=H, d_ff=FF, n_layers=L, max_len=64)
    n_params = len(m.parameters())
    n_weights = sum(p.data.size for p in m.parameters())
    print(f"  d_model={D}, n_heads={H}, d_ff={FF}, n_layers={L}")
    print(f"  参数量     : {n_weights:,}（{n_params} 个 Parameter 张量）")

    rule("3. 训练 150 步（Adam）")
    opt = Adam(m.parameters(), lr=0.02)
    tr = Trainer(m, opt)
    losses = tr.run(loader, n_steps=150, log_every=25)

    rule("4. 训练曲线数字（真实打印）")
    initial = losses[0]
    final = losses[-1]
    print(f"  初始 loss (step 1)   : {initial:.4f}  ≈ log(vocab)={np.log(V):.4f}")
    print(f"  最终 loss (step 150) : {final:.4f}")
    print(f"  下降幅度             : {initial - final:.4f}")
    print(f"  loss 是否下降        : {final < initial}")
    # 每 15 步取一个点画粗曲线
    print("\n  粗粒度 loss 曲线（每 15 步取一点）：")
    for i in range(0, len(losses), 15):
        v = losses[i]
        bar = "#" * int((v / initial) * 40)
        print(f"    step {i + 1:>3}  loss={v:6.3f}  {bar}")

    rule("5. 梯度检查（autograd vs 有限差分，tiny 配置）")
    tiny = TransformerLM(vocab_size=12, d_model=8, n_heads=2, d_ff=16, n_layers=1, max_len=16)
    from model import cross_entropy

    ids_t = np.array([[1, 2, 3, 4, 5, 6, 7, 8]])
    tgt_t = np.array([2, 3, 4, 5, 6, 7, 8, 9])

    def f(*_):
        return cross_entropy(tiny(ids_t), tgt_t)

    err = tiny_gradcheck(f, tiny.parameters())
    print(f"  梯度校验最大相对误差 : {err:.2e}  (< 1e-3 即正确)")

    rule("Demo 09 结束")
    print("  下一步：Demo 10 —— 推理生成（greedy / temperature / top-k）。")
    return 0


def tiny_gradcheck(func, params):
    # 复刻 model.grad_check 调用，避免 demo 顶层额外 import 噪音
    from model import grad_check

    return grad_check(func, params, tol=1e-3)


if __name__ == "__main__":
    sys.exit(run("demo_09_training.txt", main))
