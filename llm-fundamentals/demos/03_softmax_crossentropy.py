#!/usr/bin/env python3
"""03 · Softmax 与交叉熵：模型最后一步在做什么，为什么数值稳定很重要。

关键点：
  - logits -> softmax -> 概率分布：候选 token 的"打分"变成"概率"
  - 温度 T 控制分布的平滑程度（采样时的 creativity 旋钮）
  - 交叉熵 loss = -log p(正确 token)，等价于"给正确答案的 logits 加负号再取 softmax"
  - 直接 exp(logits) 在大数下会溢出，必须减最大值

运行：
    python3 demos/03_softmax_crossentropy.py
"""
import warnings

import numpy as np

# 本脚本会故意用大 logits 触发 exp 溢出，所以关掉 numpy 的溢出告警，让输出保持干净
np.seterr(over="ignore", invalid="ignore")
warnings.filterwarnings("ignore")
np.set_printoptions(precision=4, suppress=True)


def softmax_stable(x):
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def softmax_naive(x):
    e = np.exp(x)
    return e / e.sum()


def main():
    logits = np.array([2.0, 1.0, 0.1, -1.0])
    vocab = ["猫", "狗", "鱼", "鸟"]

    print(f"logits（模型最后一层输出的原始打分）: {logits}")
    p = softmax_stable(logits)
    print(f"softmax 概率: {p}   和为 {p.sum():.6f}")
    print("对应关系: " + ", ".join(f"{w}={q:.3f}" for w, q in zip(vocab, p)))
    print()

    print("温度 T 的作用（logits / T 后再 softmax）：")
    print(f"{'T':<6}{'猫':<9}{'狗':<9}{'鱼':<9}{'鸟':<9}{'分布形态'}")
    for T in [0.1, 0.5, 1.0, 2.0, 5.0]:
        q = softmax_stable(logits / T)
        shape = "更尖锐(趋近贪心)" if T < 1.0 else ("原始分布" if T == 1.0 else "更平滑(随机性上升)")
        print(f"{T:<6}" + "".join(f"{v:<9.4f}" for v in q) + shape)
    print("  T->0 退化为 argmax（贪心解码）；T 越大越均匀（但幻觉也越多）")
    print()

    print("数值稳定性：为什么 softmax 要先减 max")
    big = np.array([1000.0, 1001.0, 999.0])
    naive = softmax_naive(big)
    stable = softmax_stable(big)
    print(f"  logits = {big}")
    print(f"  naive  exp(x) : {np.exp(big)}   -> 结果 {naive}  <- inf/inf = nan，梯度直接炸掉")
    print(f"  stable exp(x-max): 结果 {stable}   和为 {stable.sum():.6f}")
    print(f"  数学上等价：exp(x_i)/sum(exp(x_j)) = exp(x_i-c)/sum(exp(x_j-c))，c 任意常数")
    print()

    print("交叉熵损失：loss = -log p(正确 token)")
    print(f"{'正确 token':<12}{'logit':<9}{'p':<9}{'loss=-log p'}")
    for idx, w in enumerate(vocab):
        prob = p[idx]
        print(f"{w:<12}{logits[idx]:<9.1f}{prob:<9.4f}{-np.log(prob):<9.4f}")
    print()
    print("  观察：正确 token 的 logit 越高 -> 概率越大 -> loss 越小")
    print(f"  极端情况：p=1.0 -> loss={-np.log(1.0):.4f}（完美预测）; p=0.01 -> loss={-np.log(0.01):.4f}")
    print()

    # 一个 batch 的平均 loss 与困惑度
    batch_probs = np.array([0.8, 0.5, 0.1, 0.95])
    ce = -np.log(batch_probs).mean()
    print(" batch 平均交叉熵与困惑度 perplexity = exp(CE)：")
    print(f"  4 个样本的正确 token 概率: {batch_probs}")
    print(f"  平均 CE = {ce:.4f}    perplexity = exp({ce:.4f}) = {np.exp(ce):.3f}")
    print("  perplexity 直观含义 ≈ 模型每次预测时，等价于在几个候选里犹豫")


if __name__ == "__main__":
    main()
