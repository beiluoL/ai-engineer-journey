#!/usr/bin/env python3
"""07 · 缩放定律（Scaling Law）：模型多大、数据多少、算力怎么分，是有公式可依的。

两个常用结论：
  - Kaplan et al. (2020)：L 与 N(参数量)、D(数据量)、C(算力) 呈幂律关系
  - Chinchilla (Hoffmann et al. 2022)：给定算力，最优配比是 D ≈ 20 * N
     即"参数量翻一倍，数据也要翻一倍"，此前 GPT-3 一类模型是"参数过剩、数据不足"

训练算力的经验公式：C ≈ 6 * N * D（FLOPs）

运行：
    python3 demos/07_scaling_law.py
"""


def flops_str(f):
    """大数直接走科学计数法，避免单位换算错一位。"""
    return f"{f:.2e}"


def main():
    print("Chinchilla 最优配比：D_opt ≈ 20 * N（参数量 -> 训练 token 数）")
    print(f"{'模型':<14}{'参数量 N':>14}{'最优 token 数 D':>18}{'训练算力 C≈6ND(FLOPs)':>24}")
    models = [
        ("GPT-2", 1.5e9),
        ("LLaMA-7B", 7e9),
        ("LLaMA-13B", 13e9),
        ("LLaMA-70B", 70e9),
        ("GPT-3-175B", 175e9),
    ]
    for name, n in models:
        d = 20 * n
        c = 6 * n * d
        print(f"{name:<14}{n / 1e9:>13.0f}B{d / 1e12:>17.1f}T{flops_str(c):>24}")
    print()
    print("  现实对照：LLaMA-7B 实际训练了 1T tokens（≈20x 参数量，基本符合 Chinchilla）")
    print("  GPT-3 175B 只训了 300B tokens（≈1.7x 参数量）—— Chinchilla 认为它数据严重不足")
    print()

    print("幂律关系：损失随规模下降（Kaplan 形式 L = (N_c / N)^alpha）")
    N_c, alpha = 8.8e13, 0.076  # 论文拟合量级
    print(f"{'参数量':<14}{'预测 loss':>14}{'相对 0.1B 的下降':>18}")
    base = None
    for n in [1e8, 1e9, 1e10, 1e11, 1e12]:
        L = (N_c / n) ** alpha
        if base is None:
            base = L
        bar = "#" * int((L - 1.0) * 25)
        print(f"{n / 1e9:>10.1f}B{L:>14.4f}{(L - base) / base * 100:>17.1f}%  {bar}")
    print()
    print("  注意：这是「其它条件不变」下的趋势。真正在意的是「同样算力下怎么分配 N 和 D」")
    print()

    print("同样的算力预算，参数和数据怎么分？（Chinchilla 的答案是：平分给两边）")
    budget = 1e23  # 约 1e23 FLOPs
    print(f"  算力预算 C = {flops_str(budget)} FLOPs，C = 6ND 且 D = 20N -> N = sqrt(C/120)")
    n_opt = (budget / 120) ** 0.5
    d_opt = 20 * n_opt
    print(f"  -> 最优参数量 N ≈ {n_opt / 1e9:.1f}B，最优数据量 D ≈ {d_opt / 1e12:.2f}T tokens")
    print(f"  若把参数堆到 2x（{2 * n_opt / 1e9:.1f}B）却只喂同样的数据，loss 会变差 —— 这就是参数过剩")
    print()
    print("  现代实践：推理成本也要算进账 -> 大家普遍训得比 Chinchilla 最优更久（overtrained）")
    print("  （LLaMA-3 8B 训了 15T tokens，远超 20x8B=160B，因为小模型推理便宜、总拥有成本更低）")


if __name__ == "__main__":
    main()
