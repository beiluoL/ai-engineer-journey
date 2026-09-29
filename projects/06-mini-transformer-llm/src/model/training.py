"""训练循环：把梯度一路反传回 Embedding 和 Block 的参数，并用优化器更新。

这是整张计算图里**唯一一条从后往前的箭头**（架构文档里点名的那条）。
链路：``ids → 模型 → logits → 交叉熵 → loss → backward → 优化器 step``。

提供两个优化器（玩具规模都够用）：
- ``SGD``：最朴素的梯度下降，学习率要小。
- ``Adam``：带一阶/二阶动量估计，对学习率不那么敏感，收敛更快更稳。

``Trainer`` 负责：按 batch 喂数据、算带 mask 的交叉熵（pad 不计入）、反传、
step，并记录 loss 曲线。训练正常的话，loss 必须**肉眼可见地往下走**。
"""

from __future__ import annotations

import numpy as np

from .autograd import Module, Parameter, Tensor, cross_entropy
from .decoder import TransformerLM


class SGD:
    """随机梯度下降：``w -= lr * g``。"""

    def __init__(self, params: list[Parameter], lr: float = 0.01) -> None:
        self.params = params
        self.lr = lr

    def step(self) -> None:
        for p in self.params:
            if p.grad is None:
                continue
            p.data -= self.lr * p.grad


class Adam:
    """Adam 优化器（带偏置修正）。"""

    def __init__(self, params: list[Parameter], lr: float = 0.01, betas=(0.9, 0.999), eps=1e-8) -> None:
        self.params = params
        self.lr = lr
        self.betas = betas
        self.eps = eps
        self.t = 0
        self.state = {id(p): (np.zeros_like(p.data), np.zeros_like(p.data)) for p in params}

    def step(self) -> None:
        self.t += 1
        b1, b2 = self.betas
        for p in self.params:
            if p.grad is None:
                continue
            m, v = self.state[id(p)]
            m = b1 * m + (1 - b1) * p.grad
            v = b2 * v + (1 - b2) * (p.grad ** 2)
            mhat = m / (1 - b1 ** self.t)
            vhat = v / (1 - b2 ** self.t)
            p.data -= self.lr * mhat / (np.sqrt(vhat) + self.eps)


class Trainer:
    """把模型、数据、优化器缝在一起跑训练。"""

    def __init__(
        self,
        model: TransformerLM,
        optimizer: "SGD | Adam",
    ) -> None:
        self.model = model
        self.optimizer = optimizer

    def train_step(self, x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> float:
        """跑一个 batch：前向 → 交叉熵（mask 排除 pad）→ 反传 → step。

        返回本步的标量 loss。
        """
        logits: Tensor = self.model(x, mask=None)  # 模型内部按 x 序列长生成因果掩码
        loss = cross_entropy(logits, y, mask=mask)
        self.model.zero_grad()
        loss.backward()
        self.optimizer.step()
        return float(loss.data.item())

    def run(
        self,
        dataloader,
        n_steps: int,
        log_every: int = 10,
    ) -> list[float]:
        """训练 ``n_steps`` 步（不够一个 epoch 就重复喂），返回 loss 曲线。"""
        losses: list[float] = []
        it = iter(dataloader)
        for step in range(n_steps):
            try:
                x, y, mask = next(it)
            except StopIteration:
                it = iter(dataloader)
                x, y, mask = next(it)
            loss = self.train_step(x, y, mask)
            losses.append(loss)
            if log_every and (step + 1) % log_every == 0:
                print(f"  step {step + 1:>4}/{n_steps}  loss = {loss:.4f}")
        return losses
