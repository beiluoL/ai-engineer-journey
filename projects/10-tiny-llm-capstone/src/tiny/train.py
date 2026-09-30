"""Milestone 06 —— 训练 Pipeline：把「能跑」升级成「能复现、能断点续训、能早停」。

P06 的 :class:`Trainer` 证明了「前向 → 交叉熵 → 反传 → step」这条链路是通的。
但真实训练还差四件事，本模块补齐：

1. **学习率调度**（预热 + 余弦衰减）。固定 lr 在小模型上也行，
   但一旦换规模，开局震荡和末期抖动就会吃掉大量调参时间。
2. **梯度裁剪**（按全局范数）。手写 autograd 没有框架兜底，
   一个异常 batch 能把权重直接推到 nan —— 而 nan 会安静地扩散到所有指标。
3. **验证集监控 + 早停 + 最优回滚**。训练损失单调下降不代表模型变好；
   早停并**回滚到最优权重**，才不会把「最后一步」当成「最好的一步」交出去。
4. **检查点**：保存权重 + 优化器状态 + 步数 + 配置，使得
   ``train(resume=ckpt)`` 与「一口气训完」的结果**逐步一致**（M06 会实测这个差）。

另外刻意保留的一个设计：整个训练过程**只用 numpy 全局种子 + 显式 Random**，
不依赖任何不可控的字典序/对象地址，所以同一份配置在任何机器上跑出的
loss 曲线是逐位相同的（P08 已经踩过 ``Tensor._prev`` 是 set 的坑）。
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import TinyConfig
from .model import walk_parameters

from model import cross_entropy  # noqa: E402

__all__ = [
    "Checkpoint",
    "LMTrainer",
    "evaluate_loss",
    "load_checkpoint",
    "save_checkpoint",
]


# ------------------------------------------------------------------ 评估损失
def evaluate_loss(
    model,
    examples,
    batch_size: int = 8,
) -> dict:
    """只做前向，算验证集的平均交叉熵 / 困惑度 / token 准确率。

    为什么单独写：P09 的 ``perplexity()`` 走的是它自己的 batch 拼装逻辑，
    而训练中途要**按训练时的 padding 约定**评估，两边必须完全一致，
    否则「训练 loss」和「验证 loss」根本不可比。
    """
    from .data import pad_batch

    if not examples:
        raise ValueError("examples 不能为空")
    total_loss = 0.0
    total_tokens = 0.0
    correct = 0.0
    for start in range(0, len(examples), batch_size):
        x, y, mask = pad_batch(examples[start : start + batch_size])
        logits = model(x, mask=None)
        loss = cross_entropy(logits, y, mask=mask)
        n = float(mask.sum())
        total_loss += float(loss.data) * n
        total_tokens += n
        probs = logits.data
        pred = np.argmax(probs, axis=-1)
        correct += float(((pred == y) * (mask > 0.5)).sum())
    mean_loss = total_loss / max(total_tokens, 1e-12)
    return {
        "loss": float(mean_loss),
        "perplexity": float(math.exp(min(mean_loss, 20.0))),
        "token_accuracy": float(correct / max(total_tokens, 1e-12)),
        "tokens": float(total_tokens),
    }


# ------------------------------------------------------------------ 检查点
@dataclass
class Checkpoint:
    """落盘到 ``models/`` 的一份训练快照。"""

    path: Path
    meta_path: Path
    meta: dict

    @property
    def step(self) -> int:
        return int(self.meta.get("step", 0))

    @property
    def best_val_loss(self) -> float:
        return float(self.meta.get("best_val_loss", float("inf")))


def save_checkpoint(
    model,
    path: "str | Path",
    *,
    step: int,
    meta: "dict | None" = None,
    optimizer=None,
    dtype=np.float64,
) -> Checkpoint:
    """保存权重（npz）+ 元信息（json）。

    优化器状态也存：Adam 的一阶/二阶矩是「训练进度」的一部分，
    只恢复权重不恢复动量，续训的前几十步会明显跑偏（M06 会实测）。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    named = walk_parameters(model)
    arrays = {name.replace(".", "/"): np.asarray(p.data, dtype=dtype) for name, p in named}
    payload = dict(arrays)
    if optimizer is not None:
        for index, param in enumerate(optimizer.params):
            state = optimizer.state.get(id(param))
            if state is None:
                continue
            m, v = state
            payload[f"__opt__/{index}/m"] = np.asarray(m, dtype=dtype)
            payload[f"__opt__/{index}/v"] = np.asarray(v, dtype=dtype)
    np.savez(target, **payload)

    info = {
        "step": int(step),
        "n_tensors": len(named),
        "dtype": np.dtype(dtype).name,
        "names": [name for name, _p in named],
        "has_optimizer": optimizer is not None,
        "optimizer_t": int(getattr(optimizer, "t", 0)) if optimizer is not None else 0,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    info.update(meta or {})
    meta_path = target.with_suffix(".json")
    meta_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return Checkpoint(target, meta_path, info)


def load_checkpoint(model, path: "str | Path", optimizer=None) -> dict:
    """把检查点读回模型（可选连优化器状态一起恢复）。

    严格按**名字**对齐，而不是按遍历顺序 —— 顺序依赖对象地址，
    P08 已经证明它跨进程不可靠。
    """
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"找不到检查点：{target}")
    data = np.load(target)
    named = walk_parameters(model)
    restored = 0
    for name, param in named:
        key = name.replace(".", "/")
        if key in data:
            param.data[...] = np.asarray(data[key], dtype=param.data.dtype).reshape(param.data.shape)
            restored += 1
        else:
            raise KeyError(f"检查点缺少张量 {key}")
    if optimizer is not None:
        for index, param in enumerate(optimizer.params):
            mk = f"__opt__/{index}/m"
            vk = f"__opt__/{index}/v"
            if mk in data and vk in data:
                optimizer.state[id(param)] = (
                    np.asarray(data[mk]).reshape(param.data.shape),
                    np.asarray(data[vk]).reshape(param.data.shape),
                )
    meta_path = target.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    if optimizer is not None:
        # ⚠ Adam 的 ``t`` 参与偏置修正（1/(1-βᵗ)），只恢复 m/v 不恢复 t，
        #   续训的第一步步长就会和「没中断过」不一样 —— 实测会让 30 步后的
        #   权重差到 3.5e-3。所以步数计数必须一起恢复。
        optimizer.t = int(meta.get("optimizer_t", optimizer.t))
    return {"restored": restored, "meta": meta}


# ------------------------------------------------------------------ 训练器
@dataclass
class TrainHistory:
    steps: list[int] = field(default_factory=list)
    train_loss: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    val_ppl: list[float] = field(default_factory=list)
    lr: list[float] = field(default_factory=list)
    grad_norm: list[float] = field(default_factory=list)


class LMTrainer:
    """完整训练循环：调度 / 裁剪 / 验证 / 早停 / 检查点 / 续训。"""

    def __init__(
        self,
        cfg: TinyConfig,
        model,
        optimizer,
        train_examples,
        val_examples,
        *,
        verbose: bool = True,
    ) -> None:
        self.cfg = cfg
        self.model = model
        self.optimizer = optimizer
        self.train_examples = train_examples
        self.val_examples = val_examples
        self.verbose = verbose
        self.rng = random.Random(cfg.train.seed)
        self.history = TrainHistory()
        self.best_val_loss = float("inf")
        self.best_step = 0
        self.best_weights: "dict[str, np.ndarray] | None" = None
        self.step = 0
        self.stopped_early = False
        self.wall_seconds = 0.0

    # ------------------------------------------------------------ 调度
    def lr_at(self, step: int) -> float:
        """预热 ``warmup_steps`` 步后再按余弦衰减到 ``lr * min_lr_ratio``。"""
        base = self.cfg.optim.lr
        warmup = max(0, int(self.cfg.optim.warmup_steps))
        total = max(1, int(self.cfg.train.n_steps))
        if warmup and step < warmup:
            return base * (step + 1) / warmup
        progress = (step - warmup) / max(1, total - warmup)
        progress = min(1.0, max(0.0, progress))
        cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
        floor = base * self.cfg.optim.min_lr_ratio
        return floor + (base - floor) * cosine

    # ------------------------------------------------------------ 单步
    def _grad_global_norm(self) -> float:
        total = 0.0
        for param in self.optimizer.params:
            grad = getattr(param, "grad", None)
            if grad is None:
                continue
            total += float(np.sum(np.asarray(grad) ** 2))
        return math.sqrt(total)

    def _clip_grads(self, max_norm: float) -> float:
        norm = self._grad_global_norm()
        if max_norm > 0 and norm > max_norm:
            scale = max_norm / (norm + 1e-12)
            for param in self.optimizer.params:
                if getattr(param, "grad", None) is not None:
                    param.grad = np.asarray(param.grad) * scale
        return norm

    def train_step(self, x, y, mask) -> float:
        self.optimizer.lr = self.lr_at(self.step)
        logits = self.model(x, mask=None)
        loss = cross_entropy(logits, y, mask=mask)
        self.model.zero_grad()
        loss.backward()
        norm = self._clip_grads(self.cfg.optim.grad_clip)
        if self.cfg.optim.weight_decay:
            for param in self.optimizer.params:
                if getattr(param, "grad", None) is not None:
                    param.grad = np.asarray(param.grad) + self.cfg.optim.weight_decay * param.data
        self.optimizer.step()
        self.step += 1
        self.history.grad_norm.append(norm)
        self.history.lr.append(float(self.optimizer.lr))
        return float(loss.data)

    # ------------------------------------------------------------ 评估与保存
    def evaluate(self) -> dict:
        return evaluate_loss(self.model, self.val_examples, self.cfg.train.batch_size)

    def _snapshot_best(self) -> None:
        self.best_weights = {
            name: np.array(p.data, copy=True) for name, p in walk_parameters(self.model)
        }

    def _restore_best(self) -> None:
        if self.best_weights is None:
            return
        for name, param in walk_parameters(self.model):
            if name in self.best_weights:
                param.data[...] = self.best_weights[name]

    # ------------------------------------------------------------ 主循环
    def run(
        self,
        n_steps: "int | None" = None,
        *,
        ckpt_path: "str | Path | None" = None,
        best_ckpt_path: "str | Path | None" = None,
    ) -> dict:
        """跑完整训练，返回报告字典（M06 的所有数字都从这里出）。"""
        from .data import batch_iter

        total = int(n_steps if n_steps is not None else self.cfg.train.n_steps)
        eval_every = max(1, int(self.cfg.train.eval_every))
        patience = int(self.cfg.train.patience)
        started = time.perf_counter()
        no_improve = 0
        batches = list(
            batch_iter(self.train_examples, self.cfg.train.batch_size, rng=self.rng,
                       drop_last=False)
        )
        if not batches:
            raise ValueError("训练集切不出 batch，请检查 max_len / 语料长度")
        cursor = 0

        for _ in range(total):
            if cursor >= len(batches):  # 一个 epoch 跑完 → 重新洗牌再来一轮
                batches = list(
                    batch_iter(self.train_examples, self.cfg.train.batch_size, rng=self.rng,
                               drop_last=False)
                )
                cursor = 0
            x, y, mask = batches[cursor]
            cursor += 1
            loss = self.train_step(x, y, mask)
            self.history.steps.append(self.step)
            self.history.train_loss.append(loss)

            if self.verbose and self.cfg.train.log_every and self.step % self.cfg.train.log_every == 0:
                print(f"  step {self.step:>4}/{total}  train_loss = {loss:.4f}  lr = {self.optimizer.lr:.5f}")

            if self.step % eval_every == 0 or self.step == total:
                val = self.evaluate()
                self.history.val_loss.append(val["loss"])
                self.history.val_ppl.append(val["perplexity"])
                if self.verbose:
                    print(
                        f"         eval  val_loss = {val['loss']:.4f}"
                        f"  ppl = {val['perplexity']:.2f}"
                        f"  token_acc = {val['token_accuracy']:.4f}"
                    )
                if val["loss"] < self.best_val_loss - 1e-12:
                    self.best_val_loss = val["loss"]
                    self.best_step = self.step
                    self._snapshot_best()
                    no_improve = 0
                    if best_ckpt_path is not None:
                        save_checkpoint(
                            self.model, best_ckpt_path, step=self.step,
                            optimizer=self.optimizer,
                            meta={"best_val_loss": self.best_val_loss,
                                  "val_perplexity": val["perplexity"],
                                  "config": self.cfg.to_dict()},
                        )
                else:
                    no_improve += 1
                    if patience and no_improve >= patience:
                        self.stopped_early = True
                        if self.verbose:
                            print(f"  ⚠ 连续 {no_improve} 次评估未改善 → 早停，回滚到第 {self.best_step} 步")
                        break

        self.wall_seconds = time.perf_counter() - started
        if self.stopped_early:
            self._restore_best()
        if ckpt_path is not None:
            save_checkpoint(
                self.model, ckpt_path, step=self.step, optimizer=self.optimizer,
                meta={"best_val_loss": self.best_val_loss, "best_step": self.best_step,
                      "config": self.cfg.to_dict()},
            )

        curve = self.history.train_loss
        head = curve[: max(1, len(curve) // 10)]
        tail = curve[-max(1, len(curve) // 10) :]
        return {
            "steps": self.step,
            "requested_steps": total,
            "stopped_early": self.stopped_early,
            "best_step": self.best_step,
            "first_loss": curve[0] if curve else float("nan"),
            "last_loss": curve[-1] if curve else float("nan"),
            "head_mean": float(np.mean(head)) if head else float("nan"),
            "tail_mean": float(np.mean(tail)) if tail else float("nan"),
            "best_val_loss": self.best_val_loss,
            "best_val_perplexity": float(math.exp(min(self.best_val_loss, 20.0))
                                         if self.best_val_loss < float("inf") else float("nan")),
            "final_val": self.evaluate(),
            "wall_seconds": self.wall_seconds,
            "steps_per_second": self.step / max(self.wall_seconds, 1e-9),
            "max_grad_norm": float(np.max(self.history.grad_norm)) if self.history.grad_norm else 0.0,
            "lr_first": self.history.lr[0] if self.history.lr else 0.0,
            "lr_last": self.history.lr[-1] if self.history.lr else 0.0,
            "curve": curve,
            "val_curve": self.history.val_loss,
        }
