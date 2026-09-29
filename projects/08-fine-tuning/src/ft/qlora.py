"""QLoRA = 4-bit 量化基座 + LoRA adapter。

LoRA 解决的是「训练不动那么多参数」，但它**没有**让基座变小 —— 基座权重依然
是 fp32/fp16 老老实实地躺在显存里。7B 模型光是权重就要 28GB（fp32），
这才是大多数人根本跑不起微调的真正瓶颈。

QLoRA 的解法很直接：**把基座权重压成 4 bit**，前向时再反量化回 float 参与计算。

    y = x · dequant(W_nf4)  +  (alpha/r) · x · A · B
        └── 冻结、4 bit ──┘   └── 可训练、fp32 ──┘

三个关键点：

1. **量化只作用于被冻结的基座**。梯度不会流过量化器（那东西不可导），
   所以「量化误差」不会被训练修复 —— 这也是为什么必须用 NF4 这种
   为「正态分布权重」量身定做的信息论最优码本，而不是粗暴的 int4。
2. **adapter 保持 fp32**。它只有几百万参数，占不了多少显存，但它是唯一
   在被训练的东西，精度必须保住。
3. **训练时的显存是「NF4 基座 + fp32 计算副本」**，不是「fp32 基座」。
   真正的峰值出现在逐层反量化的瞬间，但同一时刻只有一层是 fp32。

本模块提供：
- :class:`QLoRALinear`：NF4 基座 + LoRA 分支的线性层（和 :class:`LoRALinear`
  同一套「.data 即时合成 + _backward 拆梯度」机制，因此能直接塞进 P06）。
- :func:`memory_ledger`：显存账本 —— 把 fp32 / fp16 / NF4 / adapter 各占多少
  字节算清楚，这才是 QLoRA 的意义所在。
"""

from __future__ import annotations

import numpy as np

from .paths import ensure_p06_importable, ordered_prev

ensure_p06_importable()

from model import Module, Parameter, Tensor  # noqa: E402

from .quantize import (  # noqa: E402
    NF4Tensor,
    dequantize_nf4,
    nf4_storage_bytes,
    quantize_nf4,
)

__all__ = ["QLoRALinear", "memory_ledger", "training_memory", "human_bytes"]


def human_bytes(n: float) -> str:
    """字节数 → 人眼友好的字符串。"""
    step = 1024.0
    units = ["B", "KB", "MB", "GB"]
    value = float(n)
    i = 0
    while value >= step and i < len(units) - 1:
        value /= step
        i += 1
    return f"{value:,.2f} {units[i]}"


class QLoRALinear(Tensor, Module):
    """基座以 NF4 存储（不可训练）+ fp32 的 LoRA 分支（可训练）。"""

    def __init__(
        self,
        in_features: int,
        out_features: int,
        r: int = 8,
        alpha: float = 16.0,
        weight: "Parameter | np.ndarray | None" = None,
        block_size: int = 64,
        double_quant: bool = True,
        rng: "np.random.Generator | int | None" = None,
    ) -> None:
        if r <= 0:
            raise ValueError(f"r 必须是正整数，收到 {r}")
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.r = int(r)
        self.alpha = float(alpha)
        self.scaling = alpha / r
        self.block_size = int(block_size)
        self.double_quant = bool(double_quant)

        # ---- 基座：量化成 NF4，永不更新 ----
        if weight is None:
            gen0 = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
            base = gen0.normal(0.0, 0.02, size=(self.in_features, self.out_features))
        elif isinstance(weight, Parameter):
            base = weight.data
        else:
            base = np.asarray(weight, dtype=np.float64)
        self.base_shape = base.shape
        self.qw: NF4Tensor = quantize_nf4(base, self.block_size, self.double_quant)

        # ---- adapter：fp32，唯一被训练的部分 ----
        gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        bound = 1.0 / np.sqrt(self.in_features)
        self.A = Parameter(gen.uniform(-bound, bound, size=(self.in_features, self.r)))
        self.B = Parameter(np.zeros((self.r, self.out_features)))

        super().__init__(np.zeros((self.in_features, self.out_features)), requires_grad=True)
        self._backward = self._qlora_backward  # 同 LoRALinear：挂回真正的反向实现
        self._prev = ordered_prev({self.A, self.B})
        self._op = "qlora"

    # ---------------- 前向 ----------------

    @property
    def data(self) -> np.ndarray:  # type: ignore[override]
        """反量化基座 + LoRA 增量（每次访问重新合成）。"""
        return self.dequantized_base() + self.scaling * (self.A.data @ self.B.data)

    @data.setter
    def data(self, value: "np.ndarray") -> None:  # pragma: no cover
        return

    def dequantized_base(self) -> np.ndarray:
        """NF4 → fp32 的基座权重（有损，但不参与训练）。"""
        return dequantize_nf4(self.qw)

    def _qlora_backward(self) -> None:
        g = self.grad
        if g is None:
            return
        s = self.scaling
        self.A._set_grad(s * (g @ self.B.data.T))
        self.B._set_grad(s * (self.A.data.T @ g))

    # ---------------- 便捷 API ----------------

    def forward(self, x: "Tensor | np.ndarray") -> Tensor:
        from model import matmul

        return matmul(x, self)

    __call__ = forward

    def delta_weight(self) -> np.ndarray:
        return self.scaling * (self.A.data @ self.B.data)

    def merged_weight(self) -> np.ndarray:
        return self.dequantized_base() + self.delta_weight()

    def trainable_parameters(self) -> list[Parameter]:
        return [self.A, self.B]

    def num_parameters(self, trainable_only: bool = False) -> int:
        trainable = self.A.data.size + self.B.data.size
        return trainable if trainable_only else self.qw.n_elements + trainable

    def __repr__(self) -> str:
        return (
            f"QLoRALinear({self.in_features}→{self.out_features}, r={self.r}, nf4("
            f"{'dq' if self.double_quant else 'sq'})=4bit, "
            f"trainable={self.num_parameters(trainable_only=True)})"
        )


# ==========================================================================
#  显存账本
# ==========================================================================


def memory_ledger(
    weight_shapes: "list[tuple[int, int]]",
    r: int,
    block_size: int = 64,
    double_quant: bool = True,
    dtype_bytes: int = 4,
) -> dict:
    """把「基座 fp32 / fp16 / NF4」与「adapter」各自的字节数算清楚。

    Parameters
    ----------
    weight_shapes: 每个被量化的权重矩阵形状（本项目是 13 个线性层）
    r:             LoRA 秩
    dtype_bytes:   基座在未量化时的每参数字节数（fp32=4，fp16=2）
    """
    n_total = int(sum(a * b for a, b in weight_shapes))
    n_adapter = int(sum(r * (a + b) for a, b in weight_shapes))

    fp32_bytes = 4.0 * n_total
    fp16_bytes = 2.0 * n_total
    nf4_bytes = nf4_storage_bytes(n_total, block_size, double_quant=False)
    nf4_dq_bytes = nf4_storage_bytes(n_total, block_size, double_quant=True)
    adapter_bytes = 4.0 * n_adapter

    return {
        "n_base_params": n_total,
        "n_adapter_params": n_adapter,
        "fp32_bytes": fp32_bytes,
        "fp16_bytes": fp16_bytes,
        "nf4_bytes": nf4_bytes,
        "nf4_double_bytes": nf4_dq_bytes,
        "adapter_bytes": adapter_bytes,
        "base_dtype_bytes": dtype_bytes * n_total,
        "compress_fp32_vs_nf4": fp32_bytes / nf4_bytes,
        "compress_fp32_vs_nf4dq": fp32_bytes / nf4_dq_bytes,
        "nf4_vs_fp16_ratio": nf4_bytes / fp16_bytes,
        "adapter_vs_fp32_ratio": adapter_bytes / fp32_bytes,
        "adapter_vs_nf4_ratio": adapter_bytes / nf4_dq_bytes,
        "total_qlora_bytes": nf4_dq_bytes + adapter_bytes,
    }


def training_memory(
    n_total_params: int,
    n_trainable_params: int,
    dtype_bytes: int = 4,
    optimizer: str = "adam",
) -> dict:
    """训练时的显存账（参数 + 梯度 + 优化器状态）。

    全量微调 vs LoRA 的差距在这里最刺眼：Adam 要给**每个可训练参数**存
    m 和 v 两份状态，再加上一份梯度 —— 也就是说每个可训练参数训练时要
    占 **4(参数) + 4(梯度) + 8(Adam) = 16 字节**。参数量降 10 倍，
    训练开销就降 10 倍。
    """
    param_bytes = dtype_bytes * n_total_params
    grad_bytes = dtype_bytes * n_trainable_params  # 只有可训练参数需要梯度
    if optimizer.lower() == "adam":
        opt_bytes = 8.0 * n_trainable_params  # 一阶 + 二阶动量
    elif optimizer.lower() == "sgd":
        opt_bytes = 0.0
    else:
        raise ValueError(f"未知优化器：{optimizer}")
    return {
        "optimizer": optimizer,
        "n_total_params": n_total_params,
        "n_trainable_params": n_trainable_params,
        "param_bytes": param_bytes,
        "grad_bytes": grad_bytes,
        "optimizer_bytes": opt_bytes,
        "trainable_ratio": n_trainable_params / n_total_params if n_total_params else 0.0,
        "total_bytes": param_bytes + grad_bytes + opt_bytes,
    }
