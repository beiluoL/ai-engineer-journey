"""NF4 分位量化 —— QLoRA 能塞进一张消费级显卡的真正原因。

一句话讲清 NF4（4-bit NormalFloat）：

> 神经网络权重近似服从 **零均值正态分布**。既然分布已知，就不需要像 int8 那样
> 把 [-1, 1] 均匀切成 256 份，而是**按分位数**切 16 份 —— 让每一份里落进来的
> 权重**数量相同**。信息论上，这让 4 bit 承载的信息量最大。

QLoRA 的做法（也是本模块的实现）：

1. **分块 absmax 归一化**：每 ``block_size``（默认 64）个数一组，除以组内
   绝对值最大值，把权重压到 [-1, 1]。分块是为了挡住离群值 —— 一个特别大的
   权重如果参与全局归一化，会把其他所有权重都压成 0。
2. **映射到 NF4 的 16 个码字**：不是 ``round``，而是**最近邻查找**
   （``argmin |x - c|``）。因为码字不是等距的。
3. **双量化（可选）**：每个块要存一个 fp32 的 absmax，64 个权重摊到 4/64 = 0.0625
   字节/权重，占 NF4（0.5 字节/权重）的 12.5%，很浪费。于是对 absmax **再量化
   一次**成 8 bit（每 256 个 absmax 共享一个 fp32 scale），把它压到 1/4。

存储账（每个权重占多少字节）：

    方案                       每权重字节数       相对 fp32
    fp32                       4.0000             1.00×
    fp16                       2.0000             2.00×
    NF4（不双量化）            0.5 + 4/64         7.11×
    NF4 + 双量化               0.5 + (1+4/256)/64 7.75×
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "NF4_LEVELS",
    "NF4Tensor",
    "dequantize_nf4",
    "nf4_codebook",
    "nf4_storage_bytes",
    "quantization_error",
    "quantize_absmax",
    "quantize_nf4",
]

#: NF4 的 16 个码字（QLoRA 论文 Table 1，由标准正态分布的分位数反解并归一化到 [-1,1]）
NF4_LEVELS: np.ndarray = np.array(
    [
        -1.0,
        -0.6961928009986877,
        -0.5250730514526367,
        -0.39491748809814453,
        -0.28444138169288635,
        -0.18477343022823334,
        -0.09105003625154495,
        0.0,
        0.07958029955625534,
        0.16093020141124725,
        0.24611230194568634,
        0.33791524171829224,
        0.44070982933044434,
        0.5626170039176941,
        0.7229568362236023,
        1.0,
    ],
    dtype=np.float64,
)


def nf4_codebook() -> np.ndarray:
    """返回 NF4 的 16 个码字（只读副本）。"""
    return NF4_LEVELS.copy()


# ==========================================================================
#  absmax 的双量化（8 bit）
# ==========================================================================


def quantize_absmax(absmax: np.ndarray, block_size: int = 256):
    """把一组 absmax 量化成 uint8 + 每块一个 fp32 scale。

    QLoRA 论文里 absmax 用 8 bit、且每 256 个 absmax 共享一个 scale。
    """
    a = np.asarray(absmax, dtype=np.float64).reshape(-1)
    n_groups = int(np.ceil(a.size / block_size))
    pad = n_groups * block_size - a.size
    if pad:
        a = np.concatenate([a, np.zeros(pad)])
    groups = a.reshape(n_groups, block_size)
    scale = groups.max(axis=1) / 127.0
    scale = np.where(scale <= 0, 1.0, scale)  # 全 0 的块避免除零
    codes = np.clip(np.round(groups / scale[:, None]), 0, 127).astype(np.uint8)
    return codes, scale, a.size


def dequantize_absmax(codes: np.ndarray, scale: np.ndarray, size: int) -> np.ndarray:
    """``uint8 → fp``，还原 absmax（保留原始长度）。"""
    out = (codes.astype(np.float64) * scale[:, None]).reshape(-1)
    return out[:size]


# ==========================================================================
#  NF4 主流程
# ==========================================================================


@dataclass
class NF4Tensor:
    """一个被 NF4 量化后的权重块集合。

    Attributes
    ----------
    codes:        每个权重的 4-bit 码字下标，用 uint8 存（0..15）
    absmax:       每块的 fp32 归一化系数（双量化时这里存的是**已还原**的值，
                  真正落盘的是 ``absmax_codes`` + ``absmax_scale``）
    shape:        原始权重形状
    block_size:   分块大小
    double_quant: 是否双量化
    """

    codes: np.ndarray
    absmax: np.ndarray
    shape: tuple
    block_size: int = 64
    double_quant: bool = False
    absmax_codes: "np.ndarray | None" = None
    absmax_scale: "np.ndarray | None" = None
    n_elements: int = field(default=0)

    @property
    def n_blocks(self) -> int:
        return int(self.absmax.size)


def quantize_nf4(
    w: np.ndarray,
    block_size: int = 64,
    double_quant: bool = False,
) -> NF4Tensor:
    """把一块权重矩阵量化成 NF4。

    流程：拉平 → 按 ``block_size`` 分块 → 每块除以 absmax → 最近邻查码本。

    注意「最近邻查找」而不是 ``round``：NF4 的码字是**不等距**的
    （中间密、两头疏），``round`` 会把它当成均匀量化，误差明显变大。
    """
    w = np.asarray(w, dtype=np.float64)
    flat = w.reshape(-1)
    n = flat.size
    n_blocks = int(np.ceil(n / block_size))
    pad = n_blocks * block_size - n
    if pad:
        flat = np.concatenate([flat, np.zeros(pad)])

    blocks = flat.reshape(n_blocks, block_size)
    absmax = np.abs(blocks).max(axis=1)
    absmax = np.where(absmax <= 0, 1.0, absmax)  # 全零块：避免 0/0
    normed = blocks / absmax[:, None]

    # 最近邻查表：(n_blocks, block_size, 16) 的绝对差 → argmin
    dist = np.abs(normed[:, :, None] - NF4_LEVELS[None, None, :])
    codes = np.argmin(dist, axis=2).astype(np.uint8).reshape(-1)[:n]

    qt = NF4Tensor(
        codes=codes,
        absmax=absmax.astype(np.float32),
        shape=tuple(w.shape),
        block_size=block_size,
        double_quant=double_quant,
        n_elements=n,
    )
    if double_quant:
        ac, asc, size = quantize_absmax(absmax)
        qt.absmax_codes = ac
        qt.absmax_scale = asc.astype(np.float32)
        # 双量化后「实际存」的 absmax 是有损版本 —— 反量化要用它，
        # 否则测出来的误差会假装双量化是免费的。
        qt.absmax = dequantize_absmax(ac, asc, size)
    return qt


def dequantize_nf4(q: NF4Tensor) -> np.ndarray:
    """NF4 → float 矩阵，恢复原始 ``shape``。"""
    n = q.n_elements if q.n_elements else int(np.prod(q.shape))
    absmax = np.asarray(q.absmax, dtype=np.float64)
    if q.double_quant and q.absmax_codes is not None and q.absmax_scale is not None:
        absmax = dequantize_absmax(q.absmax_codes, q.absmax_scale, absmax.size)

    n_blocks = absmax.size
    total = n_blocks * q.block_size
    idx = np.concatenate([q.codes, np.zeros(total - q.codes.size, dtype=np.uint8)]).astype(np.int64)
    flat = (NF4_LEVELS[idx] * np.repeat(absmax, q.block_size))[:n]
    return flat.reshape(q.shape)


def quantization_error(w: np.ndarray, w_hat: np.ndarray) -> dict:
    """量化前后的误差统计（全部是真实算出来的）。"""
    w = np.asarray(w, dtype=np.float64)
    w_hat = np.asarray(w_hat, dtype=np.float64)
    diff = w - w_hat
    norm_w = float(np.linalg.norm(w))
    return {
        "mse": float(np.mean(diff ** 2)),
        "rmse": float(np.sqrt(np.mean(diff ** 2))),
        "max_abs": float(np.max(np.abs(diff))),
        "rel_l2": float(np.linalg.norm(diff) / norm_w) if norm_w > 0 else 0.0,
        "mean_abs": float(np.mean(np.abs(diff))),
        "std_w": float(np.std(w)),
    }


def nf4_storage_bytes(
    n_elements: int,
    block_size: int = 64,
    double_quant: bool = False,
    absmax_block: int = 256,
) -> float:
    """给定权重个数，算出 NF4 方案实际占用多少字节（含 absmax 开销）。"""
    n_blocks = int(np.ceil(n_elements / block_size))
    weight_bytes = 0.5 * n_elements  # 4 bit
    if not double_quant:
        absmax_bytes = 4.0 * n_blocks  # fp32
    else:
        n_absmax_groups = int(np.ceil(n_blocks / absmax_block))
        absmax_bytes = 1.0 * n_blocks + 4.0 * n_absmax_groups  # uint8 + fp32 scale
    return weight_bytes + absmax_bytes
