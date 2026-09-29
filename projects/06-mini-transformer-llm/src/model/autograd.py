"""极简向量化自动微分 ``Tensor`` —— 用 numpy 手搓的反向传播。

为什么不用 PyTorch：本项目是「从零理解 Transformer」，自动微分也必须自己写。
理解了 ``loss.backward()`` 背后那张计算图是怎么拓扑排序、怎么把梯度从输出
一路乘回每个参数，才算真的懂了训练循环 —— 而不是只会调 ``optimizer.step()``。

设计要点：
- 每个 ``Tensor`` 包一块 numpy 数组，记录父节点 ``_prev`` 和反向函数 ``_backward``。
- ``.backward()`` 做拓扑排序，从标量损失出发，依次调用每个节点的 ``_backward``，
  把梯度沿 ``_set_grad`` 累加回各自父节点 —— 这就是「链式法则」的具象化。
- 所有算子都支持广播（broadcast），梯度回传时用 ``_unbroadcast`` 把广播出来的
  维度重新求和，和对齐真实 DL 框架（如 PyTorch）的行为一致。

约定：
- 叶子可学习参数用 :class:`Parameter`（``requires_grad=True``）。
- 常量（如 one-hot、位置编码、mask）只是普通 ``Tensor``（``requires_grad=False``），
  它们不贡献梯度，但能参与前向计算。
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

import numpy as np


class Tensor:
    """最小自动微分张量：包一块 numpy 数组 + 计算图信息。"""

    def __init__(
        self,
        data: "np.ndarray | float | int | Sequence",
        requires_grad: bool = False,
        _children: tuple["Tensor", ...] = (),
        _op: str = "",
    ) -> None:
        self.data = np.asarray(data, dtype=np.float64)
        self.requires_grad = requires_grad
        self.grad: "np.ndarray | None" = None
        self._backward: Callable[[], None] = lambda: None
        self._prev = set(_children)
        self._op = _op

    # ---------- 梯度累加（广播友好） ----------
    def _set_grad(self, grad: "np.ndarray") -> None:
        """把上游传来的梯度累加进自己的 ``.grad``。"""
        grad = np.asarray(grad, dtype=np.float64)
        if self.grad is None:
            self.grad = grad.copy()
        else:
            self.grad = self.grad + grad

    # ---------- 反向传播：拓扑排序 + 链式求导 ----------
    def backward(self) -> None:
        """从「自己」（必须是标量损失）出发，跑一遍反向传播。"""
        if self.data.ndim != 0:
            raise ValueError(
                f"backward 只能从标量损失出发，收到 shape={self.data.shape}"
            )
        topo: list[Tensor] = []
        visited: set[int] = set()

        def build(v: Tensor) -> None:
            if id(v) not in visited:
                visited.add(id(v))
                for child in v._prev:
                    build(child)
                topo.append(v)

        build(self)

        # 清零所有节点梯度，避免多次 backward 累加
        for v in topo:
            v.grad = np.zeros_like(v.data)
        self.grad = np.ones_like(self.data)  # 损失对自身的导数是 1

        for v in reversed(topo):
            v._backward()

    # ---------- 便捷 dunder，让模块代码更像公式 ----------
    def __matmul__(self, other: "object") -> "Tensor":
        return matmul(self, other)

    def __add__(self, other: "object") -> "Tensor":
        return add(self, other)

    def __mul__(self, other: "object") -> "Tensor":
        return mul(self, other)

    def __rmul__(self, other: "object") -> "Tensor":
        return mul(other, self)

    def __sub__(self, other: "object") -> "Tensor":
        return sub(self, other)

    def __neg__(self) -> "Tensor":
        return neg(self)

    def __truediv__(self, other: "object") -> "Tensor":
        return div(self, other)

    def __repr__(self) -> str:
        return f"Tensor(shape={self.data.shape}, requires_grad={self.requires_grad})"


class Parameter(Tensor):
    """可学习参数：一个永远是叶子、且 ``requires_grad=True`` 的 Tensor。

    Embedding 权重、各种线性层 ``W``、LayerNorm 的 ``gamma/beta`` 都应该是它，
    这样 ``.backward()`` 才会把梯度写回去，优化器才能更新。
    """

    def __init__(self, data: "np.ndarray | float | int | Sequence") -> None:
        super().__init__(data, requires_grad=True)


class Module:
    """极简模块基类：负责递归收集所有 Parameter，供优化器遍历。

    下游模块（Embedding / MHA / Block / DecoderStack / 整机）都继承它，
    于是 ``model.parameters()`` 能一把把整张网络里所有可学参数都捞出来。
    """

    def parameters(self) -> list[Parameter]:
        params: list[Parameter] = []
        for value in self.__dict__.values():
            params.extend(_collect_params(value))
        return params

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.grad = None


def _collect_params(obj: object) -> list[Parameter]:
    """递归收集一个对象（及其子模块 / 容器）里所有的 Parameter。"""
    if isinstance(obj, Parameter):
        return [obj]
    if isinstance(obj, Module):
        return obj.parameters()
    if isinstance(obj, (list, tuple)):
        out: list[Parameter] = []
        for item in obj:
            out.extend(_collect_params(item))
        return out
    if isinstance(obj, dict):
        out = []
        for item in obj.values():
            out.extend(_collect_params(item))
        return out
    return []


def _ensure_tensor(x: "object") -> Tensor:
    """数字或 numpy 数组 → 常量 Tensor（不需要梯度）。"""
    if isinstance(x, Tensor):
        return x
    return Tensor(np.asarray(x, dtype=np.float64), requires_grad=False)


def _unbroadcast(grad: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    """把广播出来的梯度还原回 ``shape``：多出来的前导维求和，size=1 的维求和。"""
    while grad.ndim > len(shape):
        grad = grad.sum(axis=0)
    for i in range(len(shape)):
        if shape[i] == 1 and grad.shape[i] != 1:
            grad = grad.sum(axis=i, keepdims=True)
    return grad


def _restore_sum_shape(
    grad: np.ndarray, shape: tuple[int, ...], axis: "int | tuple[int, ...] | None", keepdims: bool
) -> np.ndarray:
    """sum/mean 反向时，把压缩了的梯度恢复回输入 ``shape``。"""
    if keepdims:
        return grad
    if axis is None:
        return np.broadcast_to(grad, shape).copy()
    axes = axis if isinstance(axis, tuple) else (axis,)
    g = grad
    for ax in sorted(axes):
        g = np.expand_dims(g, ax)
    return g


# ==========================================================================
#  算子：每个都是「前向算 numpy + 闭包里写反向」
# ==========================================================================


def matmul(a: "object", b: "object") -> Tensor:
    """矩阵乘（2D / 3D 批处理都支持，行为对齐 numpy ``@``）。"""
    a = _ensure_tensor(a)
    b = _ensure_tensor(b)
    out_data = a.data @ b.data
    out = Tensor(out_data, _children=(a, b), _op="matmul")

    def _backward() -> None:
        grad = out.grad
        ga = grad @ np.swapaxes(b.data, -1, -2)
        gb = np.swapaxes(a.data, -1, -2) @ grad
        a._set_grad(_unbroadcast(ga, a.data.shape))
        b._set_grad(_unbroadcast(gb, b.data.shape))

    out._backward = _backward
    return out


def add(a: "object", b: "object") -> Tensor:
    """逐元素加，支持广播（bias 加进激活就是靠它）。"""
    a = _ensure_tensor(a)
    b = _ensure_tensor(b)
    out = Tensor(a.data + b.data, _children=(a, b), _op="add")

    def _backward() -> None:
        a._set_grad(_unbroadcast(out.grad, a.data.shape))
        b._set_grad(_unbroadcast(out.grad, b.data.shape))

    out._backward = _backward
    return out


def sub(a: "object", b: "object") -> Tensor:
    """逐元素减。"""
    a = _ensure_tensor(a)
    b = _ensure_tensor(b)
    out = Tensor(a.data - b.data, _children=(a, b), _op="sub")

    def _backward() -> None:
        a._set_grad(_unbroadcast(out.grad, a.data.shape))
        b._set_grad(_unbroadcast(-out.grad, b.data.shape))

    out._backward = _backward
    return out


def mul(a: "object", b: "object") -> Tensor:
    """逐元素乘，支持标量（如 ``scores * (1/sqrt(d_k))``）。"""
    a = _ensure_tensor(a)
    b = _ensure_tensor(b)
    out = Tensor(a.data * b.data, _children=(a, b), _op="mul")

    def _backward() -> None:
        ga = out.grad * b.data
        gb = out.grad * a.data
        a._set_grad(_unbroadcast(ga, a.data.shape))
        b._set_grad(_unbroadcast(gb, b.data.shape))

    out._backward = _backward
    return out


def neg(a: "object") -> Tensor:
    """取负。"""
    a = _ensure_tensor(a)
    out = Tensor(-a.data, _children=(a,), _op="neg")

    def _backward() -> None:
        a._set_grad(-out.grad)

    out._backward = _backward
    return out


def div(a: "object", b: "object") -> Tensor:
    """逐元素除。"""
    a = _ensure_tensor(a)
    b = _ensure_tensor(b)
    out = Tensor(a.data / b.data, _children=(a, b), _op="div")

    def _backward() -> None:
        ga = out.grad / b.data
        gb = -out.grad * a.data / (b.data ** 2)
        a._set_grad(_unbroadcast(ga, a.data.shape))
        b._set_grad(_unbroadcast(gb, b.data.shape))

    out._backward = _backward
    return out


def sum(t: Tensor, axis: "int | tuple[int, ...] | None" = None, keepdims: bool = False) -> Tensor:
    """沿 ``axis`` 求和；``axis=None`` 时求全部元素之和（标量）。"""
    out = Tensor(t.data.sum(axis=axis, keepdims=keepdims), _children=(t,), _op="sum")

    def _backward() -> None:
        t._set_grad(_restore_sum_shape(out.grad, t.data.shape, axis, keepdims))

    out._backward = _backward
    return out


def mean(t: Tensor, axis: "int | tuple[int, ...] | None" = None, keepdims: bool = False) -> Tensor:
    """沿 ``axis`` 求平均。"""
    if axis is None:
        count = t.data.size
    elif isinstance(axis, tuple):
        count = 1
        for ax in axis:
            count *= t.data.shape[ax]
    else:
        count = t.data.shape[axis]
    return div(sum(t, axis=axis, keepdims=keepdims), 1.0 * count)


def log(t: Tensor) -> Tensor:
    """逐元素自然对数。"""
    out = Tensor(np.log(t.data), _children=(t,), _op="log")

    def _backward() -> None:
        t._set_grad(out.grad / t.data)

    out._backward = _backward
    return out


def exp(t: Tensor) -> Tensor:
    """逐元素指数。"""
    out_data = np.exp(t.data)
    out = Tensor(out_data, _children=(t,), _op="exp")

    def _backward() -> None:
        t._set_grad(out.grad * out_data)

    out._backward = _backward
    return out


def relu(t: Tensor) -> Tensor:
    """ReLU 激活。"""
    out_data = np.maximum(0.0, t.data)
    out = Tensor(out_data, _children=(t,), _op="relu")

    def _backward() -> None:
        t._set_grad(out.grad * (t.data > 0))

    out._backward = _backward
    return out


def softmax(t: Tensor, axis: int = -1) -> Tensor:
    """数值稳定的 softmax（减最大值防溢出），默认对最后一轴。"""
    m = t.data.max(axis=axis, keepdims=True)
    e = np.exp(t.data - m)
    out_data = e / e.sum(axis=axis, keepdims=True)
    out = Tensor(out_data, _children=(t,), _op="softmax")

    def _backward() -> None:
        # dy/dx = y * (grad - sum(grad * y, axis))
        gy = out.grad
        sm = np.sum(gy * out_data, axis=axis, keepdims=True)
        t._set_grad(out_data * (gy - sm))

    out._backward = _backward
    return out


def transpose(t: Tensor, axes: "list[int] | tuple[int, ...]") -> Tensor:
    """维度置换；反向时按逆置换换回来。"""
    axes = list(axes)
    out = Tensor(np.transpose(t.data, axes), _children=(t,), _op="transpose")
    inv = [axes.index(i) for i in range(len(axes))]

    def _backward() -> None:
        t._set_grad(np.transpose(out.grad, inv))

    out._backward = _backward
    return out


def reshape(t: Tensor, shape: "list[int] | tuple[int, ...]") -> Tensor:
    """重塑形状；反向时换回原形状。"""
    out = Tensor(t.data.reshape(shape), _children=(t,), _op="reshape")

    def _backward() -> None:
        t._set_grad(out.grad.reshape(t.data.shape))

    out._backward = _backward
    return out


def layernorm(x: Tensor, gamma: Tensor, beta: Tensor, eps: float = 1e-5) -> Tensor:
    """LayerNorm（沿最后一轴），带可学习的 ``gamma`` / ``beta``。

    是对上一轴做标准化再仿射：``y = gamma * (x-mu)/std + beta``。
    """
    data = x.data
    mu = data.mean(axis=-1, keepdims=True)
    xc = data - mu
    var = (xc ** 2).mean(axis=-1, keepdims=True)
    istd = 1.0 / np.sqrt(var + eps)
    xhat = xc * istd
    out_data = xhat * gamma.data + beta.data
    out = Tensor(out_data, _children=(x, gamma, beta), _op="layernorm")

    def _backward() -> None:
        dy = out.grad
        lead_axes = tuple(range(dy.ndim - 1))
        dbeta = dy.sum(axis=lead_axes)
        dgamma = (dy * xhat).sum(axis=lead_axes)
        dxhat = dy * gamma.data
        mean_dxhat = dxhat.mean(axis=-1, keepdims=True)
        mean_dxhat_xhat = (dxhat * xhat).mean(axis=-1, keepdims=True)
        dx = istd * (dxhat - mean_dxhat - xhat * mean_dxhat_xhat)
        x._set_grad(dx)
        gamma._set_grad(dgamma)
        beta._set_grad(dbeta)

    out._backward = _backward
    return out


def cross_entropy(logits: Tensor, targets: "np.ndarray | list[int]", mask: "np.ndarray | None" = None) -> Tensor:
    """交叉熵损失：吃 logits ``(..., V)`` + 整数 targets ``(...)``，返回标量。

    内部用 ``log_softmax`` 的稳健写法（减最大值），并支持 ``mask``（每位置 0/1）：
    只对 ``mask==1`` 的真实 token 算损失、回传梯度，pad 位置权重为 0。
    """
    data = logits.data
    V = data.shape[-1]
    lead = data.shape[:-1]
    N = int(np.prod(lead))
    z = data.reshape(N, V)
    t = np.asarray(targets, dtype=np.int64).reshape(N)
    if mask is None:
        w = np.ones(N, dtype=np.float64)
    else:
        w = np.asarray(mask, dtype=np.float64).reshape(N)
    W = w.sum()
    if W <= 0:
        raise ValueError("mask 全为 0，损失无法定义")

    m = z.max(axis=1, keepdims=True)
    e = np.exp(z - m)
    p = e / e.sum(axis=1, keepdims=True)
    logp = np.log(p[np.arange(N), t] + 1e-12)
    loss_val = -(w * logp).sum() / W

    out = Tensor(np.array(loss_val, dtype=np.float64), _children=(logits,), _op="ce")

    def _backward() -> None:
        gz = p.copy()
        gz[np.arange(N), t] -= 1.0
        gz = gz * (w / W)[:, None]
        logits._set_grad(gz.reshape(data.shape))

    out._backward = _backward
    return out


def linear(x: Tensor, weight: Tensor, bias: "Tensor | None" = None) -> Tensor:
    """线性层 ``y = x @ W + bias``；bias 可选。"""
    out = matmul(x, weight)
    if bias is not None:
        out = add(out, bias)
    return out


# ==========================================================================
#  梯度校验：用有限差分（中心差分）对拍自动微分
# ==========================================================================


def grad_check(
    func: Callable[..., Tensor],
    inputs: "list[Tensor]",
    eps: float = 1e-5,
    tol: float = 1e-4,
) -> float:
    """对拍自动微分与有限差分，返回最大相对误差。

    ``func`` 接收若干 Tensor（必须是可学参数），返回一个**标量** Tensor。
    我们用中心差分扰动每个输入的元素，得到数值梯度，再和 ``.backward()`` 得到的
    解析梯度比相对误差。返回的最大误差 < ``tol`` 即说明自动微分正确。
    """
    # 解析梯度
    loss = func(*inputs)
    loss.backward()
    analytical = [inp.grad.copy() for inp in inputs]

    # 数值梯度（中心差分）
    numeric: list[np.ndarray] = []
    for inp in inputs:
        g = np.zeros_like(inp.data)
        it = np.nditer(inp.data, flags=["multi_index"])
        while not it.finished:
            idx = it.multi_index
            original = inp.data[idx]
            inp.data[idx] = original + eps
            lp = func(*inputs).data.item()
            inp.data[idx] = original - eps
            lm = func(*inputs).data.item()
            inp.data[idx] = original
            g[idx] = (lp - lm) / (2.0 * eps)
            it.iternext()
        numeric.append(g)

    # 误差度量：对较大梯度用相对误差；对接近 0 的梯度改用绝对误差，
    # 否则相对误差会被浮点噪声放大、产生假阳性（深层网络里很多梯度本就≈0）。
    max_err = 0.0
    for a, n in zip(analytical, numeric):
        denom = np.maximum(np.abs(a), np.abs(n))
        abs_err = np.abs(a - n)
        rel = abs_err / np.where(denom < 1e-6, 1.0, denom)
        max_err = max(max_err, float(rel.max()))
    return max_err
