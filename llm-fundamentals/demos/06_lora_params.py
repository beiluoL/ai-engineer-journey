#!/usr/bin/env python3
"""06 · LoRA 到底省了多少：用真实矩阵算一遍参数量和秩。

LoRA 的核心假设：微调时的权重更新 ΔW 是"低秩"的 —— 不需要动完整的 d×d 矩阵，
用两个瘦矩阵 B(d×r) 和 A(r×d) 相乘就能近似：
    W' = W + ΔW = W + B @ A      其中 r << d
训练时冻结 W，只训 A、B。

运行：
    python3 demos/06_lora_params.py
"""
import numpy as np

np.random.seed(7)


def lora_report(d_in, d_out, r, alpha=16, name=""):
    full = d_in * d_out
    lora = r * (d_in + d_out)
    scale = alpha / r
    return {
        "name": name,
        "shape": f"{d_in}x{d_out}",
        "r": r,
        "full": full,
        "lora": lora,
        "ratio": lora / full,
        "scale": scale,
    }


def main():
    print("单个线性层对比（以 LLaMA-7B 的 attention 投影 d=4096 为例）：")
    print(f"{'层':<22}{'形状':<12}{'r':<6}{'全量微调参数':>16}{'LoRA 参数':>14}{'占比':>9}{'缩放 alpha/r':>12}")
    rows = [
        lora_report(4096, 4096, 8, 16, "q_proj"),
        lora_report(4096, 4096, 16, 32, "v_proj"),
        lora_report(4096, 4096, 64, 128, "q_proj(r=64)"),
        lora_report(4096, 11008, 8, 16, "up_proj(FFN)"),
    ]
    for x in rows:
        print(
            f"{x['name']:<22}{x['shape']:<12}{x['r']:<6}{x['full']:>16,}{x['lora']:>14,}"
            f"{100 * x['ratio']:>8.2f}%{x['scale']:>12.1f}"
        )
    print()
    print("  结论：r=8 时 LoRA 参数不到全量的 0.4%，而且 FFN 层（4096x11008）省得更狠")
    print()

    # 数值验证：B@A 的秩确实 <= r
    d, r = 64, 4
    A = np.random.randn(r, d) * 0.01     # 通常 A 用小随机初始化
    B = np.zeros((d, r))                 # B 初始化为 0 -> 训练开始时 ΔW=0，不破坏原模型
    delta_W = B @ A
    print("数值验证 1：B 初始化为 0 时，ΔW 全零 -> 微调起点 = 原模型，不会一上来就劣化")
    print(f"   ΔW 绝对值最大值 = {np.abs(delta_W).max():.2e}")
    print()
    B = np.random.randn(d, r)
    delta_W = B @ A
    rank = np.linalg.matrix_rank(delta_W)
    print(f"数值验证 2：B({d}x{r}) @ A({r}x{d}) 的秩 = {rank}，受限于 r={r}（低秩假设的代价）")
    print(f"   完整矩阵可以是满秩 {d}，LoRA 只能表达秩 <= {r} 的更新")
    print()

    # 显存账：7B 模型微调
    print("显存账（LLaMA-7B, fp16, AdamW）—— 为什么 LoRA 能单卡跑：")
    params = 7e9
    fp16 = 2
    print(f"{'项目':<26}{'全量微调':>16}{'LoRA(r=8)':>16}")
    print(f"{'权重 (fp16)':<26}{params * fp16 / 1024**3:>15.1f}GB{params * fp16 / 1024**3:>15.1f}GB")
    grad_full = params * fp16 / 1024**3
    print(f"{'梯度':<26}{grad_full:>15.1f}GB{0.5 * 0.004 * params * fp16 / 1024**3:>15.2f}GB")
    opt_full = params * 4 * 2 / 1024**3  # Adam 的一阶/二阶动量，fp32
    print(f"{'优化器状态(Adam fp32)':<26}{opt_full:>15.1f}GB{opt_full * 0.004:>15.2f}GB")
    total_full = (params * fp16 + params * fp16 + params * 8) / 1024**3
    total_lora = (params * fp16 + params * fp16 * 0.004 + params * 8 * 0.004) / 1024**3
    print(f"{'合计（不含激活值）':<26}{total_full:>15.1f}GB{total_lora:>15.2f}GB")
    print()
    print(f"   全量微调 ≈ {total_full:.0f}GB（需多卡 + 各种并行），LoRA ≈ {total_lora:.1f}GB（单张 24G 卡可跑）")
    print("   QLoRA 再把冻结的基座量化成 4bit -> 基座从 14GB 降到 ~3.5GB，门槛进一步降低")


if __name__ == "__main__":
    main()
