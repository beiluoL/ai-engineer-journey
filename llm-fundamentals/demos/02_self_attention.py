#!/usr/bin/env python3
"""02 · 手算 Self-Attention：把公式 Attention(Q,K,V)=softmax(QK^T/√d_k)V 拆成每一步。

只用 numpy，不依赖任何深度学习框架。目的是看清：
  1. Q/K/V 是怎么从同一个 X 变出来的（三个不同投影）
  2. √d_k 缩放到底在压什么
  3. 因果 mask 怎样让第 i 个位置看不到未来

运行：
    python3 demos/02_self_attention.py
"""
import numpy as np

np.random.seed(42)

N, D_MODEL, D_K = 6, 8, 4  # 6 个 token，模型维度 8，注意力头维度 4
WORDS = ["我", "在", "北京", "吃", "烤", "鸭"]


def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)  # 减最大值，防止 exp 溢出
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def main():
    X = np.random.randn(N, D_MODEL).round(3)
    # 权重乘 0.35 让打分不至于过于极端，这样注意力矩阵"有分布"而不是 one-hot，便于观察
    W_q = np.random.randn(D_MODEL, D_K) * 0.35
    W_k = np.random.randn(D_MODEL, D_K) * 0.35
    W_v = np.random.randn(D_MODEL, D_K) * 0.35

    Q, K, V = X @ W_q, X @ W_k, X @ W_v

    print(f"输入 X: {X.shape}  (N={N} 个 token, d_model={D_MODEL})")
    print(f"W_q/W_k/W_v: {W_q.shape} -> 同一个 X 乘三个不同矩阵，得到三种身份（查询/键/值）")
    print(f"Q: {Q.shape}   K: {K.shape}   V: {V.shape}")
    print()

    scores = Q @ K.T
    scaled = scores / np.sqrt(D_K)
    print(f"1) 打分 scores = QK^T: {scores.shape}   第 i 行 j 列 = 第 i 个 token 对第 j 个 token 的原始相似度")
    print(f"   未缩放 scores 的绝对值均值: {np.abs(scores).mean():.3f}")
    print(f"2) 除以 sqrt(d_k)={np.sqrt(D_K):.1f} 后均值: {np.abs(scaled).mean():.3f}  <- 防止点积随维度变大而爆炸")
    print()

    attn = softmax(scaled, axis=-1)
    print("3) 按行 softmax 得到注意力权重（每行 = 一个概率分布，和为 1）：")
    print("        " + "  ".join(f"{w:>5}" for w in WORDS))
    for i, row in enumerate(attn):
        bar = " ".join(f"{v:.3f}" for v in row)
        print(f"  {WORDS[i]:>3} | {bar}   row_sum={row.sum():.6f}")
    print()

    out = attn @ V
    print(f"4) 输出 = 权重 @ V: {out.shape}")
    # 手工验算第一行，确认"输出就是 V 的加权平均"
    manual = sum(attn[0, j] * V[j] for j in range(N))
    print("5) 验算：out[0] 是否等于 sum_j attn[0,j] * V[j] ?")
    print(f"   最大误差 = {np.abs(out[0] - manual).max():.2e}   (浮点精度内相等 -> 输出确实是 V 的加权平均)")
    print()

    # 因果 mask：把上三角（未来位置）盖掉
    mask = np.triu(np.ones((N, N)), k=1) * -1e9
    causal = softmax(scaled + mask, axis=-1)
    print("6) 加上因果 mask（GPT 解码器必须做），上三角被强制归零：")
    print("        " + "  ".join(f"{w:>5}" for w in WORDS))
    for i, row in enumerate(causal):
        print(f"  {WORDS[i]:>3} | " + " ".join(f"{v:.3f}" for v in row) + f"   可见范围=[0..{i}]")
    print()
    print(f"   因果注意力每行和仍是 1: {np.allclose(causal.sum(axis=1), 1.0)}")
    print("   含义：第 i 个位置在预测时，只能用 0..i 的信息，看不到 i+1 及之后 -> 才能自回归生成")

    # 多头：把 d_model 切成 h 份
    H, D_HEAD = 2, D_MODEL // 2
    print()
    print(f"7) 多头注意力 MHA: 把 d_model={D_MODEL} 切成 H={H} 个头，每头 d_head={D_HEAD}")
    print(f"   每头独立算注意力 -> {H} 个 {N}x{D_HEAD} 的输出 -> 拼回 {N}x{D_MODEL}")
    print(f"   参数量与单头相同（{D_MODEL}x{D_MODEL}），但每个头可以看不同的关系模式")


if __name__ == "__main__":
    main()
