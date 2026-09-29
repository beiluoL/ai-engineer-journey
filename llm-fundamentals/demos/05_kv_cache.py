#!/usr/bin/env python3
"""05 · KV Cache：推理时最划算的一个优化，把 O(n^2) 的重复计算砍成 O(n)。

自回归生成时，第 t 步要算 Attention(Q_t, K_{1..t}, V_{1..t})。
K/V 是历史 token 算出来的，每步都重算一遍纯属浪费 —— 缓存起来只算新 token 即可。

运行：
    python3 demos/05_kv_cache.py
"""
import time

import numpy as np

np.random.seed(0)

D_MODEL, D_HEAD, N_HEADS, N_LAYERS = 512, 64, 8, 12
SEQ = 128


def make_weights():
    return {
        "q": np.random.randn(D_MODEL, N_HEADS * D_HEAD) * 0.02,
        "k": np.random.randn(D_MODEL, N_HEADS * D_HEAD) * 0.02,
        "v": np.random.randn(D_MODEL, N_HEADS * D_HEAD) * 0.02,
    }


def run(use_cache, seq=SEQ):
    """模拟一层 decoder 的自回归生成，统计矩阵乘的运算量。"""
    W = make_weights()
    x = np.random.randn(seq, D_MODEL)  # 所有 token 的 embedding（假设全部已知，纯计算量对比）
    flops = 0
    k_cache, v_cache = [], []
    t0 = time.perf_counter()

    for t in range(seq):
        if use_cache:
            x_t = x[t : t + 1]                    # 只喂新 token: (1, d_model)
            k_new, v_new = x_t @ W["k"], x_t @ W["v"]
            flops += 2 * x_t.shape[0] * D_MODEL * (N_HEADS * D_HEAD) * 2
            k_cache.append(k_new)
            v_cache.append(v_new)
            K = np.concatenate(k_cache, axis=0)   # (t+1, d)
            V = np.concatenate(v_cache, axis=0)
            q = x_t @ W["q"]
        else:
            x_all = x[: t + 1]                    # 每步把整个前缀重算一遍: (t+1, d_model)
            K, V, q = x_all @ W["k"], x_all @ W["v"], x_all @ W["q"]
            flops += 3 * 2 * x_all.shape[0] * D_MODEL * (N_HEADS * D_HEAD)
        _ = q @ K.T                               # 注意力打分（真正用上的部分）
        flops += 2 * q.shape[0] * K.shape[0] * (N_HEADS * D_HEAD)

    dt = time.perf_counter() - t0
    return flops, dt


def main():
    f_naive, t_naive = run(use_cache=False)
    f_cache, t_cache = run(use_cache=True)

    print(f"设定: seq_len={SEQ}, d_model={D_MODEL}, heads={N_HEADS}, d_head={D_HEAD}, layers={N_LAYERS}")
    print()
    print(f"{'策略':<16}{'矩阵乘 FLOPs':>18}{'实测耗时(s)':>14}{'相对加速':>10}")
    print(f"{'无 KV Cache':<16}{f_naive:>18,}{t_naive:>14.4f}{'1.0x':>10}")
    print(f"{'有 KV Cache':<16}{f_cache:>18,}{t_cache:>14.4f}{f'{t_naive / t_cache:.1f}x':>10}")
    print()
    print(f"  FLOPs 节省 {100 * (1 - f_cache / f_naive):.1f}% —— 因为 K/V 每步只算 1 次而不是 t 次")
    print("  注：实测耗时被 Python 循环的固定开销摊薄了；在 GPU 上（访存才是瓶颈）差距更接近 FLOPs 之比")
    print("  理论: 无 cache = sum_{t=1..n} 3*(t*d^2) = O(n^2 * d^2)；有 cache = 3*n*d^2 = O(n * d^2)")
    print()

    # 代价：显存
    print("代价：KV Cache 要占显存（这也是长上下文的瓶颈）")
    print(f"{'batch':<8}{'seq_len':<10}{'KV Cache 大小(fp16)':<24}{'备注'}")
    for batch, seq in [(1, 2048), (8, 2048), (8, 8192), (32, 32768)]:
        # 每个 token 每层存 K 和 V 各 N_HEADS*D_HEAD 个数，fp16 = 2 bytes
        bytes_per_token = 2 * N_LAYERS * (N_HEADS * D_HEAD) * 2
        total = bytes_per_token * seq * batch
        print(f"{batch:<8}{seq:<10}{total / 1024**3:>10.2f} GB{'':<8}{'单卡 A100 80G 也要掂量' if total / 1024**3 > 20 else ''}")
    print()
    print(f"  公式: kv_bytes = 2(K和V) x layers x (heads x d_head) x seq_len x batch x 2(bytes)")
    print(f"  本例每 token: {2 * N_LAYERS * (N_HEADS * D_HEAD) * 2 / 1024:.1f} KB")
    print("  -> 这就是 GQA / MQA / PagedAttention(vLLM) 要解决的核心问题")


if __name__ == "__main__":
    main()
