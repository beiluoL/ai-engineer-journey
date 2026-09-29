"""把 LoRA 注入 P06 的 TransformerLM —— 「冻结基座」到底是怎么落地的。

P06 的模型是一棵普通 Python 对象树：

    TransformerLM
      ├── token_emb.weight        (V, d_model)
      ├── decoder
      │     ├── blocks[0..N]
      │     │     ├── ln1.gamma/beta
      │     │     ├── attn.Wq / Wk / Wv / Wo
      │     │     ├── ln2.gamma/beta
      │     │     └── ffn.W1 / b1 / W2 / b2
      │     ├── ln_f.gamma/beta
      │     └── proj              (d_model, V)

「注入」= 把树里某些 ``Parameter`` 位置**换成** :class:`LoRALinear`（它自己
又抱着原来的 ``W`` + 新的 ``A``/``B``）。因为 P06 的前向是 ``linear(x, self.Wq)``，
而 ``LoRALinear`` 伪装成了 Tensor（``.data`` 即时合成 ``W+ΔW``），所以 P06
一行都不用改，前向就自动带上了 LoRA 分支。

「冻结」= **不把基座参数交给优化器**。这里额外把它们的 ``requires_grad``
置 False，让意图显式可见（并在 demo 里用字节级比对证明它们真的没动）。

.. note:: 一个实测发现（值得写进文档）
   P06 的 ``Module.parameters()`` **漏掉了 ``token_emb.weight``** ——
   ``TokenEmbedding`` 是普通类，没有继承 ``Module``，而
   ``_collect_params`` 只认 ``Parameter`` / ``Module`` / list / dict。
   本项目不改 P06，于是自己写了一个更彻底的 :func:`walk_parameters`
   （遍历任意对象的 ``__dict__``），把词嵌入也纳进参数表与 npz 缓存，
   否则基座永远学不到词向量。
"""

from __future__ import annotations

from typing import Iterator

import numpy as np

from .paths import ensure_p06_importable

ensure_p06_importable()

from model import Module, Parameter, Tensor  # noqa: E402

from .lora import LoRAConfig, LoRALinear  # noqa: E402
from .qlora import QLoRALinear  # noqa: E402

__all__ = [
    "LORA_TYPES",
    "DEFAULT_TARGETS",
    "base_parameters",
    "count_parameters",
    "freeze_base",
    "inject_lora",
    "iter_targets",
    "lora_layers",
    "named_parameters",
    "trainable_parameters",
    "walk_parameters",
]

LORA_TYPES = (LoRALinear, QLoRALinear)

#: 默认注入位置：注意力四个投影 + FFN 两个投影 + 输出投影。
#: 经验上「全都注入」比只注入 Q/V 效果更好，代价是 adapter 大一点。
DEFAULT_TARGETS: tuple[str, ...] = ("Wq", "Wk", "Wv", "Wo", "W1", "W2", "proj")


# ==========================================================================
#  参数树遍历
# ==========================================================================


#: 遍历时要跳过的属性名。``_prev`` 是 autograd 的计算图边（``Tensor`` 列表），
#: 不是参数 —— 它原本是 ``set``（没有 ``__dict__``，自然被跳过），但 P08 为了
#: 可复现把它换成了有序 list（见 :func:`ft.paths.ordered_prev`），于是会被
#: 当成容器递归进去，产出 ``xxx._prev.0`` 这种假参数路径。
_SKIP_KEYS = frozenset({"_prev"})


def walk_parameters(obj: object, prefix: str = "") -> "Iterator[tuple[str, object, str, Parameter]]":
    """递归产出 ``(path, parent, key, Parameter)``。

    ``parent`` 是直接持有该参数的对象，``key`` 是属性名（容器里是下标），
    这样调用方可以直接把它替换掉（注入 LoRA 就是靠这个）。

    和 P06 的 ``Module.parameters()`` 的区别：本函数遍历**任意**对象的
    ``__dict__``，所以不会漏掉没继承 ``Module`` 的 ``TokenEmbedding``。
    """
    out: list[tuple[str, object, str, Parameter]] = []
    seen: set[int] = set()

    def _walk(node: object, path: str, parent: object, key: object) -> None:
        if isinstance(node, Parameter):
            out.append((path, parent, key, node))  # type: ignore[arg-type]
            return
        if id(node) in seen:
            return
        seen.add(id(node))
        d = getattr(node, "__dict__", None)
        if not d:
            return
        for k, v in list(d.items()):
            if k in _SKIP_KEYS:
                continue
            child_path = f"{path}.{k}" if path else k
            if isinstance(v, Parameter):
                out.append((child_path, node, k, v))
            elif isinstance(v, (list, tuple)):
                for i, item in enumerate(v):
                    _walk(item, f"{child_path}.{i}", v, i)
            elif hasattr(v, "__dict__") and not isinstance(v, np.ndarray):
                if isinstance(v, Tensor) and not isinstance(v, LORA_TYPES):
                    continue  # 普通 Tensor 里没有可学参数，别浪费时间
                _walk(v, child_path, node, k)

    _walk(obj, prefix, None, "")
    yield from out


def named_parameters(obj: object) -> list[tuple[str, Parameter]]:
    """``(path, Parameter)`` 列表，顺序稳定（可用于 npz 存盘）。"""
    return [(p, param) for p, _parent, _k, param in walk_parameters(obj)]


def set_param(obj: object, path: str, value: object) -> None:
    """按 ``walk_parameters`` 产出的 path 把参数写回对象树。"""
    parts = path.split(".")
    node: object = obj
    for part in parts[:-1]:
        if isinstance(node, (list, tuple)):
            node = node[int(part)]
        else:
            node = getattr(node, part)
    last = parts[-1]
    if isinstance(node, (list, tuple)):
        node[int(last)] = value  # type: ignore[index]
    else:
        setattr(node, last, value)


def get_by_path(obj: object, path: str) -> object:
    """按 path 取值（存盘/加载时用来定位）。"""
    node: object = obj
    for part in path.split("."):
        node = node[int(part)] if isinstance(node, (list, tuple)) else getattr(node, part)
    return node


# ==========================================================================
#  注入 / 冻结 / 参数统计
# ==========================================================================


def iter_targets(model, targets=DEFAULT_TARGETS) -> list[tuple[str, object, str, Parameter]]:
    """找出所有待注入的二维权重（按 path 的最后一段匹配）。"""
    hits = []
    for path, parent, key, param in walk_parameters(model):
        leaf = path.split(".")[-1]
        if leaf in targets and param.data.ndim == 2:
            hits.append((path, parent, key, param))
    return hits


def inject_lora(
    model,
    targets=DEFAULT_TARGETS,
    r: int = 8,
    alpha: float = 16.0,
    kind: str = "lora",
    block_size: int = 64,
    double_quant: bool = True,
    rng: "np.random.Generator | int | None" = None,
):
    """把模型里所有 target 位置的权重换成 LoRA / QLoRA 层。

    Returns
    -------
    list[tuple[str, LoRALinear]]: 被注入的 (path, layer)，顺序即注入顺序。
    """
    if kind not in ("lora", "qlora"):
        raise ValueError(f"kind 必须是 'lora' 或 'qlora'，收到 {kind!r}")
    injected: list[tuple[str, object]] = []
    for path, parent, key, param in iter_targets(model, targets):
        in_f, out_f = param.data.shape
        if kind == "lora":
            layer = LoRALinear(in_f, out_f, r=r, alpha=alpha, weight=param, rng=rng)
        else:
            layer = QLoRALinear(
                in_f, out_f, r=r, alpha=alpha, weight=param,
                block_size=block_size, double_quant=double_quant, rng=rng,
            )
        set_param(model, path, layer)
        injected.append((path, layer))
    if not injected:
        raise RuntimeError("一个 LoRA 层都没注入 —— 检查 targets 是否写错")
    freeze_base(model)
    return injected


def freeze_base(model) -> int:
    """把所有非 adapter 参数的 ``requires_grad`` 置 False，返回被冻结的个数。

    真正的冻结是「不交给优化器」；这一步是让意图显式、可被测试断言。
    """
    frozen = 0
    for path, parent, key, param in walk_parameters(model):
        leaf = path.split(".")[-1]
        if isinstance(parent, LORA_TYPES) and leaf in ("A", "B"):
            param.requires_grad = True
        else:
            param.requires_grad = False
            frozen += 1
    return frozen


def lora_layers(model) -> list[tuple[str, object]]:
    """模型里所有 LoRA 层，按遍历顺序。"""
    found: list[tuple[str, object]] = []
    seen: set[int] = set()

    def _walk(node: object, path: str) -> None:
        if isinstance(node, LORA_TYPES):
            found.append((path, node))
            return
        if isinstance(node, Parameter) or id(node) in seen:
            return
        seen.add(id(node))
        d = getattr(node, "__dict__", None)
        if not d:
            return
        for k, v in list(d.items()):
            if k in _SKIP_KEYS:
                continue
            child = f"{path}.{k}" if path else k
            if isinstance(v, (list, tuple)):
                for i, item in enumerate(v):
                    _walk(item, f"{child}.{i}")
            elif isinstance(v, LORA_TYPES):
                found.append((child, v))
            elif hasattr(v, "__dict__") and not isinstance(v, np.ndarray):
                if isinstance(v, Tensor):
                    continue
                _walk(v, child)

    _walk(model, "")
    return found


def trainable_parameters(model) -> list[Parameter]:
    """所有 adapter 参数（A / B）—— 这是唯一该进优化器的列表。"""
    params: list[Parameter] = []
    for _path, layer in lora_layers(model):
        params.extend(layer.trainable_parameters())
    return params


def base_parameters(model) -> list[tuple[str, Parameter]]:
    """所有**非 adapter** 参数（含 LoRA 层里被冻结的 ``W``）。

    路径统一去掉 ``.W`` 后缀，这样注入前（``...attn.Wq``）和注入后
    （``...attn.Wq.W``）的快照可以**同名对齐**，用来证明「训练后基座没动」。
    """
    out: list[tuple[str, Parameter]] = []
    for path, parent, key, param in walk_parameters(model):
        leaf = path.split(".")[-1]
        if isinstance(parent, LORA_TYPES):
            if leaf in ("A", "B"):
                continue
            if leaf == "W":
                path = path[: -len(".W")]
        out.append((path, param))
    return out


def count_parameters(model) -> dict:
    """参数量三连：总量 / 可训练 / 基座，以及 P06 口径的对照。"""
    total = 0
    trainable = 0
    for path, parent, key, param in walk_parameters(model):
        total += param.data.size
        leaf = path.split(".")[-1]
        if isinstance(parent, LORA_TYPES) and leaf in ("A", "B"):
            trainable += param.data.size
    p06_count = len(model.parameters()) if isinstance(model, Module) else 0
    p06_elems = sum(p.data.size for p in model.parameters()) if isinstance(model, Module) else 0
    return {
        "total": total,
        "trainable": trainable,
        "base": total - trainable,
        "trainable_ratio": trainable / total if total else 0.0,
        "p06_len": p06_count,
        "p06_elements": p06_elems,
        "n_lora_layers": len(lora_layers(model)),
    }
