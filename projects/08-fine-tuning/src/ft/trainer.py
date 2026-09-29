"""只训练 adapter 的训练器。

LoRA 的训练循环和全量微调**代码上几乎一样**，唯一的区别是：
优化器拿到的参数列表里只有 A / B。就这么一点差别，决定了
「一个基座 + 无数个小 adapter」还是「每个任务一份完整权重」。

    logits = model(x)
    loss   = cross_entropy(logits, y, mask=答案区 mask)
    loss.backward()
    optimizer.step()        # ← 只更新 A / B

另外两件这里必须做对的事：

1. **mask 要传给 loss**。SFT 只在答案区算损失（见 :mod:`ft.sft_data`），
   否则模型会花一半力气去学「怎么复述用户的问题」。
2. **训练要能从断点精确续上**。Adam 的动量状态必须一起存，否则 resume 之后
   loss 会先弹一下再回落 —— 那是「假续训」。本模块的 ``step`` 计数与每个 epoch
   的 perm 都由 ``seed + epoch`` 决定，所以断点前后的数据顺序也是连续的。
"""

from __future__ import annotations

import numpy as np

from .paths import ensure_p06_importable

ensure_p06_importable()

from model import Adam, SGD, cross_entropy  # noqa: E402

from .inject import trainable_parameters  # noqa: E402
from .sft_data import pad_batch  # noqa: E402

__all__ = ["LoRATrainer", "curve_summary"]


def curve_summary(losses: list[float], window: int = 10) -> dict:
    """loss 曲线的真实摘要（首 / 尾 / 最低 / 前后窗口均值）。"""
    arr = np.asarray(losses, dtype=np.float64)
    if arr.size == 0:
        return {"first": float("nan"), "last": float("nan"), "best": float("nan")}
    w = min(window, arr.size)
    return {
        "first": float(arr[0]),
        "last": float(arr[-1]),
        "best": float(arr.min()),
        "first_window": float(arr[:w].mean()),
        "last_window": float(arr[-w:].mean()),
        "drop": float(arr[:w].mean() - arr[-w:].mean()),
        "drop_ratio": float((arr[:w].mean() - arr[-w:].mean()) / arr[:w].mean()),
        "n_steps": int(arr.size),
    }


class LoRATrainer:
    """把「模型 + 只有 adapter 的参数列表 + 优化器」缝在一起。"""

    def __init__(
        self,
        model,
        trainable: "list | None" = None,
        lr: float = 2e-3,
        optimizer: str = "adam",
        seed: int = 0,
    ) -> None:
        self.model = model
        self.params = list(trainable) if trainable is not None else trainable_parameters(model)
        if not self.params:
            raise ValueError("可训练参数为空 —— 先注入 LoRA，或检查 targets 是否匹配")
        self.lr = float(lr)
        self.optimizer_name = optimizer.lower()
        # ⚠ Adam 在 __init__ 里按 id(p) 建 state：必须在参数列表定好之后再构造
        self.optimizer = Adam(self.params, lr=self.lr) if self.optimizer_name == "adam" else SGD(self.params, lr=self.lr)
        self.seed = int(seed)
        self.step = 0
        self.losses: list[float] = []
        self._perm_cache: dict[int, list[np.ndarray]] = {}

    # ---------------- 单步 ----------------

    def train_step(self, x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> float:
        """前向 → 带 mask 的交叉熵 → 反传 → 只更新 adapter。"""
        logits = self.model(x, mask=None)
        loss = cross_entropy(logits, y, mask=mask)
        # backward() 会把计算图内所有节点的梯度清零，不需要额外 zero_grad
        loss.backward()
        self.optimizer.step()
        self.step += 1
        return float(loss.data.item())

    # ---------------- 批处理（可精确续训）----------------

    def _epoch_batches(self, n_examples: int, batch_size: int, epoch: int) -> list[np.ndarray]:
        """第 ``epoch`` 轮的 batch 划分：由 ``seed + epoch`` 唯一决定。"""
        key = (n_examples, batch_size, epoch)
        if key not in self._perm_cache:
            rng = np.random.default_rng(self.seed + epoch)
            idx = rng.permutation(n_examples)
            self._perm_cache[key] = [idx[i : i + batch_size] for i in range(0, n_examples, batch_size)]
        return self._perm_cache[key]

    def run(
        self,
        examples: list,
        n_steps: int,
        batch_size: int = 4,
        log_every: int = 0,
        verbose: bool = False,
    ) -> list[float]:
        """跑 ``n_steps`` 步，返回这段的 loss 曲线（不是全历史）。"""
        n = len(examples)
        n_batches = max(1, int(np.ceil(n / batch_size)))
        losses: list[float] = []
        # ⚠ 先把起始步数抓在手里：train_step 每步都会自增 self.step，
        #   如果循环里写 self.step + s 就会**重复计数**（第 s 步实际跳到 2s），
        #   导致批次顺序错乱、断点续训对不上。
        start = self.step
        for s in range(n_steps):
            global_step = start + s
            epoch, bi = divmod(global_step, n_batches)
            idx = self._epoch_batches(n, batch_size, epoch)[bi]
            X, Y, M = pad_batch([examples[int(i)] for i in idx])
            loss = self.train_step(X, Y, M)
            losses.append(loss)
            if verbose and log_every and (s + 1) % log_every == 0:
                print(f"    step {global_step + 1:>4}  loss = {loss:.4f}")
        self.losses.extend(losses)
        return losses

    # ---------------- 断点 ----------------

    def optimizer_state(self) -> dict:
        """导出优化器状态（Adam 的 m / v 与步数 t），用于 resume。"""
        payload: dict = {"name": self.optimizer_name, "lr": self.lr, "step": self.step}
        if self.optimizer_name == "adam":
            payload["t"] = int(self.optimizer.t)
            payload["m"] = [np.asarray(self.optimizer.state[id(p)][0]).copy() for p in self.params]
            payload["v"] = [np.asarray(self.optimizer.state[id(p)][1]).copy() for p in self.params]
        return payload

    def load_optimizer_state(self, payload: dict) -> None:
        """恢复优化器状态；没有状态则只恢复步数计数。"""
        self.step = int(payload.get("step", self.step))
        if self.optimizer_name == "adam" and payload.get("m") and payload.get("v"):
            self.optimizer.t = int(payload.get("t", 0))
            for p, m, v in zip(self.params, payload["m"], payload["v"]):
                self.optimizer.state[id(p)] = (np.asarray(m).copy(), np.asarray(v).copy())

    def __repr__(self) -> str:
        return (
            f"LoRATrainer(params={len(self.params)}, lr={self.lr:g}, "
            f"optimizer={self.optimizer_name}, step={self.step})"
        )
