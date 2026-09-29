"""LoRA 的核心算子：一个「基座权重冻结 + 低秩增量可训练」的线性层。

LoRA 的全部想法可以写成一行公式：

    W' = W + ΔW = W + (alpha / r) · B @ A

其中 ``W ∈ R^{in×out}`` 是**预训练并被冻结**的基座权重，
``A ∈ R^{in×r}``、``B ∈ R^{r×out}`` 是训练时才存在的低秩分解，``r << min(in, out)``。

为什么这样就省：
- 训练参数量从 ``in×out`` 降到 ``r×(in+out)``。
- 优化器状态（Adam 的 m / v）也只给 A / B 开，显存同理。
- 推理时可以把 ``W + ΔW`` **预先合并**成一个矩阵，不增加任何推理开销
  （见 :mod:`ft.merge`）。

为什么不是直接训练 W：
全量微调会破坏基座已经学到的通用能力（灾难性遗忘），而且每个下游任务都要
存一份完整权重。LoRA 让「一个基座 + N 个几 MB 的 adapter」成为可能。

------------------------------------------------------------------------------
本项目的一个实现约束（值得单独说清楚）
------------------------------------------------------------------------------
P06 的前向写死了 ``linear(x, self.Wq)`` 这种形态，而 P08 **不允许修改 P06**。
为了让注入进去的 LoRA 层在 P06 的原代码里「自动生效」，这里让
:class:`LoRALinear` 同时继承 ``Tensor`` 与 ``Module``，并把它的 ``.data``
做成一个**即时合成**的属性：

    LoRALinear.data  ==  W.data + (alpha/r) · (A.data @ B.data)

于是 ``x @ self.Wq`` 里的 ``.data`` 拿到的就是合并后的权重，前向天然正确；
反向则靠覆写 ``_backward``，把落在「合并权重」上的梯度按链式法则拆回 A 与 B：

    ∂L/∂A = (alpha/r) · G @ Bᵀ
    ∂L/∂B = (alpha/r) · Aᵀ @ G        （G = ∂L/∂(W+ΔW)）

这样 P06 一行都不用改，就拿到了完整的 LoRA 前向 + 反向。
"""

from __future__ import annotations

import numpy as np

from .paths import ensure_p06_importable, ordered_prev

ensure_p06_importable()

from model import Module, Parameter, Tensor, matmul  # noqa: E402  (必须先插入 sys.path)

__all__ = ["LoRALinear", "LoRAConfig"]


class LoRAConfig:
    """一组 LoRA 超参的容器（r / alpha / dropout），方便存进 checkpoint 元信息。"""

    def __init__(self, r: int = 8, alpha: float = 16.0, dropout: float = 0.0) -> None:
        if r <= 0:
            raise ValueError(f"r 必须是正整数，收到 {r}")
        self.r = r
        self.alpha = alpha
        self.dropout = dropout

    @property
    def scaling(self) -> float:
        """LoRA 论文里的缩放系数 ``alpha / r``。"""
        return self.alpha / self.r

    def to_dict(self) -> dict:
        return {"r": self.r, "alpha": self.alpha, "dropout": self.dropout}

    @classmethod
    def from_dict(cls, payload: dict) -> "LoRAConfig":
        return cls(r=int(payload["r"]), alpha=float(payload["alpha"]), dropout=float(payload.get("dropout", 0.0)))

    def __repr__(self) -> str:
        return f"LoRAConfig(r={self.r}, alpha={self.alpha}, dropout={self.dropout}, scaling={self.scaling:g})"


class LoRALinear(Tensor, Module):
    """``y = x @ W + (alpha/r) · x @ A @ B``，其中只有 A、B 参与训练。

    Parameters
    ----------
    in_features, out_features:
        基座权重的形状 ``[in, out]``（注意 P06 里线性层是右乘，W 是 ``[in, out]``）。
    r, alpha, dropout:
        LoRA 超参。``dropout`` 只保留接口 —— 在本项目的注入形态下（ΔW 合成进
        权重矩阵）拿不到输入 x，因此只支持 0，非 0 直接报错而不是悄悄失效。
    weight:
        可选的基座权重。传 ``Parameter`` 则**复用**它（P06 训练好的矩阵，冻结）；
        传 ndarray 则包成新的 ``Parameter``；不传则随机初始化一个。
    rng:
        初始化 A 用的随机源，传了才能保证可复现。
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        r: int = 8,
        alpha: float = 16.0,
        dropout: float = 0.0,
        weight: "Parameter | np.ndarray | None" = None,
        rng: "np.random.Generator | int | None" = None,
    ) -> None:
        if dropout and dropout > 0:
            raise ValueError(
                "LoRA 的 input dropout 需要改写 P06 的前向才能拿到输入 x；"
                "本项目不修改 P06，因此仅支持 dropout=0。"
            )
        if r <= 0:
            raise ValueError(f"r 必须是正整数，收到 {r}")

        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.r = int(r)
        self.alpha = float(alpha)
        self.dropout = float(dropout)
        self.scaling = alpha / r
        self.frozen = True

        # ---- 基座权重：永远是可学 Parameter，但不进优化器（=冻结）----
        if weight is None:
            gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
            base = gen.normal(0.0, 0.02, size=(self.in_features, self.out_features))
            self.W = Parameter(base)
        elif isinstance(weight, Parameter):
            self.W = weight
        else:
            self.W = Parameter(np.asarray(weight, dtype=np.float64))

        # ---- A / B：唯一被训练的东西 ----
        gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        # 教科书式初始化：A 取小随机值，B 全零
        bound = 1.0 / np.sqrt(self.in_features)
        self.A = Parameter(gen.uniform(-bound, bound, size=(self.in_features, self.r)))
        self.B = Parameter(np.zeros((self.r, self.out_features)))

        # 占位 data（会被下面的 property 覆盖成即时合成值）
        super().__init__(np.zeros((self.in_features, self.out_features)), requires_grad=True)
        # ⚠ Tensor.__init__ 会把 ``_backward`` 设成一个实例属性（noop lambda），
        #   它会**遮蔽**类里定义的方法。所以必须在这里显式挂回真正的反向实现。
        self._backward = self._lora_backward
        # 把 A / B 挂进计算图：这样 backward 会给它们清零梯度并按拓扑序回传
        self._prev = ordered_prev({self.A, self.B})
        self._op = "lora"

    # ---------------- 前向：data 是「即时合成」的 W + ΔW ----------------

    @property
    def data(self) -> np.ndarray:  # type: ignore[override]
        """合并后的权重 ``W + (alpha/r)·A@B``（每次访问重新合成，保证永远最新）。"""
        return self.W.data + self.scaling * (self.A.data @ self.B.data)

    @data.setter
    def data(self, value: "np.ndarray") -> None:  # pragma: no cover - 只用于兼容基类赋值
        # 合成值是派生的，写入无意义；基类 __init__ 的那次赋值直接忽略。
        return

    def _lora_backward(self) -> None:
        """把落在合并权重上的梯度拆回 A 与 B（链式法则）。

        注意方法名不能叫 ``_backward``：``Tensor.__init__`` 会把同名**实例属性**
        设成 noop，实例属性会遮蔽方法（踩过一次坑，见 __init__ 里的说明）。
        """
        g = self.grad
        if g is None:
            return
        s = self.scaling
        self.A._set_grad(s * (g @ self.B.data.T))
        self.B._set_grad(s * (self.A.data.T @ g))
        # 冻结的 W 不累积梯度：它不在计算图里，也不该被优化器看到。

    # ---------------- 便捷 API ----------------

    def forward(self, x: "Tensor | np.ndarray") -> Tensor:
        """``x @ (W + ΔW)``。单独拿 LoRALinear 当一层用时走这里。"""
        return matmul(x, self)

    __call__ = forward

    def delta_weight(self) -> np.ndarray:
        """低秩增量 ``ΔW = (alpha/r)·A@B``，shape ``[in, out]``。"""
        return self.scaling * (self.A.data @ self.B.data)

    def merged_weight(self) -> np.ndarray:
        """``W + ΔW``（合并后的完整权重）。"""
        return self.W.data + self.delta_weight()

    def trainable_parameters(self) -> list[Parameter]:
        """只有 A、B 可训练 —— LoRA 的全部意义。"""
        return [self.A, self.B]

    def num_parameters(self, trainable_only: bool = False) -> int:
        if trainable_only:
            return self.A.data.size + self.B.data.size
        return self.W.data.size + self.A.data.size + self.B.data.size

    def __repr__(self) -> str:
        return (
            f"LoRALinear({self.in_features}→{self.out_features}, r={self.r}, "
            f"alpha={self.alpha:g}, scaling={self.scaling:g}, "
            f"trainable={self.num_parameters(trainable_only=True)})"
        )
