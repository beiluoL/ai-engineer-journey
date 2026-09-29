#!/usr/bin/env python3
"""04 · 正弦位置编码：不用训练，就能让模型知道"谁在前谁在后"。

Attention 本身是对序列做加权求和，与顺序无关（置换不变）。
位置编码把"位置"变成向量加到 token embedding 上，这样 QK^T 的打分里就带上了相对距离信息。

公式（原论文 Sinusoidal PE）：
    PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

运行：
    python3 demos/04_positional_encoding.py
"""
import numpy as np

np.set_printoptions(precision=4, suppress=True)

D_MODEL = 64
MAX_POS = 400


def sinusoidal_pe(max_pos, d_model):
    pos = np.arange(max_pos)[:, None]           # (max_pos, 1)
    i = np.arange(d_model // 2)[None, :]        # (1, d_model/2)
    angle = pos / np.power(10000.0, 2 * i / d_model)
    pe = np.zeros((max_pos, d_model))
    pe[:, 0::2] = np.sin(angle)                 # 偶数维度 sin
    pe[:, 1::2] = np.cos(angle)                 # 奇数维度 cos
    return pe


def main():
    pe = sinusoidal_pe(MAX_POS, D_MODEL)
    print(f"PE 矩阵形状: {pe.shape}  (max_pos={MAX_POS}, d_model={D_MODEL})")
    print()
    print("前 4 个位置的前 8 个维度（保留 4 位小数）：")
    print("      " + "".join(f"dim{i:<6}" for i in range(8)))
    for p in range(4):
        print(f"pos{p:<4}" + "".join(f"{v:<+8.4f}" for v in pe[p, :8]))
    print()
    print("观察：低维（dim0/1）随位置快速振荡，高维变化缓慢 —— 不同频率叠加 = 不同刻度的尺子")
    print()

    # 关键性质 1：任意位置的 PE 都能由另一个位置的 PE 线性变换得到（相对位置可学习）
    print("性质 1：PE(pos+k) 可由 PE(pos) 线性表示 —— 验证 dot(PE(pos), PE(pos+k)) 只依赖 k")
    print(f"{'k(相对距离)':<14}" + "".join(f"pos={p:<10}" for p in [0, 10, 30, 60]))
    for k in [0, 1, 3, 5, 10]:
        row = ""
        for p in [0, 10, 30, 60]:
            d = float(pe[p] @ pe[p + k])
            row += f"{d:<+13.4f}"
        print(f"{k:<14}" + row)
    print("  同一 k 下不同 pos 的点积非常接近 -> 模型学到的是相对距离，而不是死记绝对位置")
    print()

    # 关键性质 2：距离越远，相似度整体越低（局部性先验）
    print("性质 2：相似度随相对距离增大而衰减（近处更相关 —— 局部性先验）")
    base = 20
    dots = [float(pe[base] @ pe[base + k]) for k in range(0, 40)]
    print("  逐点（不同频率叠加，会有局部起伏）：")
    for k in range(0, 40, 4):
        bar = "#" * max(0, int(dots[k] * 1.2))
        print(f"    k={k:<3} dot={dots[k]:<+8.3f} {bar}")
    print("  按区间取平均后，衰减趋势很清楚：")
    for lo in range(0, 40, 8):
        chunk = dots[lo : lo + 8]
        avg = sum(chunk) / len(chunk)
        bar = "#" * max(0, int(avg * 1.2))
        print(f"    k={lo:>2}-{lo + 7:<3} 均值={avg:<+8.3f} {bar}")
    print(f"  k=0 时最大({dots[0]:.3f})；k=32-39 均值已降到 {sum(dots[32:40]) / 8:.3f}")
    print()

    # 与可学习位置编码的对比
    print("两种主流位置编码对比：")
    print(f"{'类型':<14}{'是否可训练':<12}{'能否外推到更长序列':<22}{'代表模型'}")
    print(f"{'Sinusoidal':<14}{'否':<12}{'能（公式任意长）':<22}Transformer / 早期 GPT")
    print(f"{'Learned':<14}{'是':<12}{'不能（超出训练长度失效）':<22}BERT / GPT-2")
    print(f"{'RoPE':<14}{'否':<12}{'能（且可插值扩展）':<22}LLaMA / Qwen / Mistral")
    print()
    print("RoPE 思路：不改 embedding，而是把 Q/K 向量旋转 pos*theta 角度，")
    print("          使 q_m^T k_n 天然只含 (m-n) —— 相对位置直接写进注意力打分里。")


if __name__ == "__main__":
    main()
