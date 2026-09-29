#!/usr/bin/env python3
"""生成配图：所有图都由本脚本真实计算后绘制，不手改像素。

输出目录: assets/
    attention-heatmap.png       注意力权重矩阵（双向 vs 因果掩码）
    positional-encoding.png     正弦位置编码热力图 + 相对距离相似度衰减曲线
    softmax-temperature.png     温度 T 对采样分布的影响
    scaling-law.png             Loss 随参数量的幂律下降（双对数坐标）
    lora-params.png             LoRA 与全量微调的可训练参数量对比
    kv-cache-memory.png         KV Cache 显存随 batch / 序列长度的增长

运行：
    python3 demos/make_figures.py
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(OUT, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"
plt.rcParams["text.color"] = "#1f2933"
plt.rcParams["axes.labelcolor"] = "#1f2933"
plt.rcParams["xtick.color"] = "#3e4c59"
plt.rcParams["ytick.color"] = "#3e4c59"

BLUE, RED, GREY = "#2563eb", "#dc2626", "#94a3b8"


def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def fig_attention_heatmap():
    np.random.seed(42)
    n, d_model, d_k = 6, 8, 4
    words = ["我", "在", "北京", "吃", "烤", "鸭"]
    X = np.random.randn(n, d_model)
    Q = X @ (np.random.randn(d_model, d_k) * 0.35)
    K = X @ (np.random.randn(d_model, d_k) * 0.35)
    scores = Q @ K.T / np.sqrt(d_k)

    attn = softmax(scores, axis=-1)
    causal = softmax(scores + np.triu(np.ones((n, n)), 1) * -1e9, axis=-1)

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.2))
    for ax, mat, title in [
        (axes[0], attn, "双向注意力（Encoder / BERT）"),
        (axes[1], causal, "因果注意力（Decoder / GPT）"),
    ]:
        im = ax.imshow(mat, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(n), words, fontsize=11)
        ax.set_yticks(range(n), words, fontsize=11)
        ax.set_title(title, fontsize=12, pad=10)
        for i in range(n):
            for j in range(n):
                v = mat[i, j]
                if v > 0.005:
                    ax.text(
                        j, i, f"{v:.2f}", ha="center", va="center",
                        color="white" if v > 0.5 else "#1f2933", fontsize=9,
                    )
        ax.set_xlabel("Key 位置（被关注者）", fontsize=9)
    axes[0].set_ylabel("Query 位置（发起关注者）", fontsize=9)
    fig.subplots_adjust(left=0.09, right=0.9, top=0.82, bottom=0.14, wspace=0.22)
    cax = fig.add_axes([0.925, 0.16, 0.016, 0.64])
    fig.colorbar(im, cax=cax, label="注意力权重")
    fig.suptitle("Self-Attention 权重矩阵：每行和为 1，因果掩码把上三角（未来）清零",
                 fontsize=12.5, y=0.97)
    fig.savefig(f"{OUT}/attention-heatmap.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_positional_encoding():
    d_model, max_pos = 64, 100
    pos = np.arange(max_pos)[:, None]
    i = np.arange(d_model // 2)[None, :]
    angle = pos / np.power(10000.0, 2 * i / d_model)
    pe = np.zeros((max_pos, d_model))
    pe[:, 0::2] = np.sin(angle)
    pe[:, 1::2] = np.cos(angle)

    base = 20
    ks = np.arange(0, 60)
    dots = np.array([float(pe[base] @ pe[base + k]) for k in ks])

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0))
    im = axes[0].imshow(pe.T, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1)
    axes[0].set_xlabel("位置 pos", fontsize=9)
    axes[0].set_ylabel("维度 dim", fontsize=9)
    axes[0].set_title("正弦位置编码：低维高频振荡，高维缓慢变化", fontsize=11.5)
    fig.colorbar(im, ax=axes[0], shrink=0.85)

    axes[1].plot(ks, dots, color=BLUE, lw=2)
    win = 8
    smooth = np.convolve(dots, np.ones(win) / win, mode="valid")
    axes[1].plot(ks[win - 1 :], smooth, color=RED, lw=2, ls="--", label=f"{win} 点滑动平均")
    axes[1].set_xlabel("相对距离 k", fontsize=9)
    axes[1].set_ylabel("PE(pos)·PE(pos+k)", fontsize=9)
    axes[1].set_title("相似度随相对距离整体衰减（局部性）", fontsize=11.5)
    axes[1].legend(fontsize=9)
    axes[1].grid(alpha=0.25)

    fig.suptitle("位置编码：把顺序信息写进向量，且只依赖相对距离", fontsize=12.5, y=1.02)
    fig.tight_layout()
    fig.savefig(f"{OUT}/positional-encoding.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_softmax_temperature():
    logits = np.array([2.0, 1.0, 0.1, -1.0])
    labels = ["猫", "狗", "鱼", "鸟"]
    temps = [0.3, 0.7, 1.0, 2.0, 4.0]

    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    x = np.arange(len(labels))
    width = 0.16
    colors = ["#1e3a8a", "#2563eb", "#60a5fa", "#f59e0b", "#dc2626"]
    for idx, T in enumerate(temps):
        p = softmax(logits / T)
        ax.bar(x + (idx - 2) * width, p, width, label=f"T={T}", color=colors[idx])
    ax.set_xticks(x, labels, fontsize=11)
    ax.set_ylabel("采样概率", fontsize=10)
    ax.set_xlabel("候选 token（logits = 猫2.0 / 狗1.0 / 鱼0.1 / 鸟-1.0）", fontsize=9)
    ax.set_title("温度 T：T→0 退化为贪心 argmax，T 越大分布越平、随机性与幻觉风险越高",
                 fontsize=11.5)
    ax.legend(fontsize=9, ncol=5, loc="upper center")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(f"{OUT}/softmax-temperature.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_scaling_law():
    N_c, alpha = 8.8e13, 0.076
    ns = np.logspace(7, 12, 60)
    loss = (N_c / ns) ** alpha

    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    ax.plot(ns, loss, color=BLUE, lw=2.5, label=r"$L=(N_c/N)^{0.076}$")
    for name, n in [("GPT-2 1.5B", 1.5e9), ("LLaMA-7B", 7e9),
                    ("LLaMA-70B", 70e9), ("GPT-3 175B", 1.75e11)]:
        ax.scatter([n], [(N_c / n) ** alpha], color=RED, zorder=5)
        ax.annotate(name, (n, (N_c / n) ** alpha), textcoords="offset points",
                    xytext=(8, 8), fontsize=9, color="#dc2626")
    ax.set_xscale("log")
    ax.set_xlabel("参数量 N（对数轴）", fontsize=10)
    ax.set_ylabel("交叉熵损失 L", fontsize=10)
    ax.set_title("缩放定律：双对数坐标下，损失随规模近似线性下降（幂律）", fontsize=11.5)
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT}/scaling-law.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_lora_params():
    d_in, d_out = 4096, 4096
    rs = [1, 2, 4, 8, 16, 32, 64]
    full = d_in * d_out
    lora = [r * (d_in + d_out) for r in rs]

    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    bars = ax.bar([str(r) for r in rs], lora, color=BLUE, alpha=0.85, label="LoRA 可训练参数")
    ax.axhline(full, color=RED, ls="--", lw=2, label=f"全量微调 {full/1e6:.1f}M")
    ax.set_yscale("log")
    ax.set_xlabel("LoRA 秩 r", fontsize=10)
    ax.set_ylabel("可训练参数量（对数轴）", fontsize=10)
    ax.set_title("LoRA：4096×4096 线性层，r=8 时只需训练 0.39% 的参数", fontsize=11.5)
    for b, v in zip(bars, lora):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v/1e3:.0f}K\n({v/full*100:.2f}%)",
                ha="center", va="bottom", fontsize=8.5)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(f"{OUT}/lora-params.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_kv_cache_memory():
    layers, heads, d_head = 32, 32, 128  # LLaMA-7B 量级: 32 层, GQA 前 32 头
    per_token = 2 * layers * heads * d_head * 2  # K 和 V, fp16
    seqs = np.array([2048, 4096, 8192, 16384, 32768, 65536])
    batches = [1, 8, 32]

    fig, ax = plt.subplots(figsize=(8.8, 4.2))
    colors = ["#2563eb", "#f59e0b", "#dc2626"]
    for b, c in zip(batches, colors):
        gb = per_token * seqs * b / 1024**3
        ax.plot(seqs, gb, marker="o", color=c, lw=2, label=f"batch={b}")
    ax.axhline(80, color=GREY, ls=":", lw=1.5)
    ax.text(seqs[0], 82, "A100 80GB 显存上限", fontsize=9, color="#52606d")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("序列长度（对数轴）", fontsize=10)
    ax.set_ylabel("KV Cache 显存 (GB)", fontsize=10)
    ax.set_title("KV Cache 是长上下文的显存瓶颈（每 token 约 "
                 f"{per_token/1024:.0f} KB）", fontsize=11.5)
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT}/kv-cache-memory.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_attention_heatmap()
    fig_positional_encoding()
    fig_softmax_temperature()
    fig_scaling_law()
    fig_lora_params()
    fig_kv_cache_memory()
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            print(f"assets/{f}")
