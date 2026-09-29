"""Adapter 的存 / 取 / 续训 —— LoRA 在工程上最好用的地方。

全量微调一个 7B 模型，每个任务都要存一份 28GB 的权重：存不起，也传不动。
LoRA 之后每个任务只存 **几 MB** 的 A / B —— 这就是它能在生产里普及的原因。

本模块落盘两样东西：

- ``xxx.npz``  ：所有 adapter 张量（``A::path`` / ``B::path``）+ 可选的 Adam 动量
- ``xxx.json`` ：元信息（r / alpha / 注入位置 / 训练步数 / loss 曲线 / 优化器配置）

为什么 Adam 的动量也要存：
只存 A / B 不叫「断点续训」，叫「重新训练」。Adam 的一阶/二阶动量是**训练状态**
的一部分，丢了它们，resume 之后的第一步会像没训过一样大步乱走，loss 会先弹上去
再慢慢回落。本模块把 m / v / t 一起落盘，所以 resume 出来的 loss 曲线可以和
一次性训练**逐点接上**。

一个容易踩的坑（本项目已规避）：加载时必须**就地写入** ``A.data[:] = ...``，
不能替换 Parameter 对象 —— P06 的 Adam 是按 ``id(p)`` 建 state 的，换了对象
动量就全丢了。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .inject import count_parameters, lora_layers, trainable_parameters
from .quantize import nf4_storage_bytes  # noqa: F401  (报告里会用到)
from .qlora import human_bytes

__all__ = [
    "adapter_report",
    "load_adapter",
    "load_checkpoint",
    "save_adapter",
    "save_checkpoint",
]


def _meta_path(path: Path) -> Path:
    return path.with_suffix(".json")


def save_adapter(
    model,
    path: "str | Path",
    trainer=None,
    meta: "dict | None" = None,
    dtype=np.float32,
    include_optimizer: bool = True,
) -> dict:
    """把模型里所有 LoRA 层的 A / B 存成 npz + json，返回统计信息。

    Parameters
    ----------
    dtype:
        落盘精度。默认 **fp32** —— 训练时是 fp64，但 adapter 存 fp32 是
        工业界惯例（体积减半，精度足够），这也是「adapter 只有几 MB」的来源。
        要做**逐位**往返一致性验证时传 ``np.float64``。
    include_optimizer:
        是否连 Adam 的 m / v 一起存。只分发推理权重时关掉，体积立减 2/3。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    layers = lora_layers(model)
    arrays: dict[str, np.ndarray] = {}
    layer_info: list[dict] = []
    for p, layer in layers:
        arrays[f"A::{p}"] = np.asarray(layer.A.data).astype(dtype)
        arrays[f"B::{p}"] = np.asarray(layer.B.data).astype(dtype)
        layer_info.append(
            {
                "path": p,
                "in_features": layer.in_features,
                "out_features": layer.out_features,
                "r": layer.r,
                "alpha": layer.alpha,
                "scaling": layer.scaling,
                "kind": "qlora" if hasattr(layer, "qw") else "lora",
            }
        )

    counts = count_parameters(model)
    info: dict = {
        "format": "p08-lora-adapter-v1",
        "n_layers": len(layers),
        "layers": layer_info,
        "n_adapter_params": int(counts["trainable"]),
        "n_base_params": int(counts["base"]),
        "n_total_params": int(counts["total"]),
    }
    info["save_dtype"] = np.dtype(dtype).name
    info["include_optimizer"] = include_optimizer
    if trainer is not None and include_optimizer:
        opt = trainer.optimizer_state()
        for i, m in enumerate(opt.get("m", [])):
            arrays[f"opt_m::{i}"] = np.asarray(m).astype(dtype)
        for i, v in enumerate(opt.get("v", [])):
            arrays[f"opt_v::{i}"] = np.asarray(v).astype(dtype)
        info["optimizer"] = {
            "name": opt["name"], "lr": opt["lr"], "step": opt["step"], "t": opt.get("t", 0),
        }
        info["losses"] = [float(x) for x in trainer.losses]
    elif trainer is not None:
        info["optimizer"] = {"name": trainer.optimizer_name, "lr": trainer.lr, "step": trainer.step}
        info["losses"] = [float(x) for x in trainer.losses]
    if meta:
        info.update(meta)

    np.savez(path, **arrays)
    _meta_path(path).write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    info["npz_bytes"] = path.stat().st_size
    info["json_bytes"] = _meta_path(path).stat().st_size
    info["npz_path"] = str(path)
    info["json_path"] = str(_meta_path(path))
    return info


def load_adapter(model, path: "str | Path") -> dict:
    """把 npz 里的 A / B **就地**写回模型的 LoRA 层（不动 Parameter 对象）。"""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"adapter 文件不存在：{path}")
    meta = json.loads(_meta_path(path).read_text(encoding="utf-8"))
    blob = np.load(path)

    layers = dict(lora_layers(model))
    if len(layers) != len(meta["layers"]):
        raise ValueError(
            f"结构不匹配：模型有 {len(layers)} 个 LoRA 层，checkpoint 里是 {len(meta['layers'])} 个"
        )
    for entry in meta["layers"]:
        p = entry["path"]
        if p not in layers:
            raise ValueError(f"模型里找不到 LoRA 层：{p}")
        layer = layers[p]
        a = blob[f"A::{p}"]
        b = blob[f"B::{p}"]
        if a.shape != layer.A.data.shape or b.shape != layer.B.data.shape:
            raise ValueError(f"{p} 的 A/B 形状对不上：{a.shape}/{b.shape}")
        # 就地写入：Parameter 对象不能换，否则优化器按 id(p) 建的 state 会丢
        layer.A.data[:] = a.astype(layer.A.data.dtype)
        layer.B.data[:] = b.astype(layer.B.data.dtype)
    return meta


def save_checkpoint(
    model,
    trainer,
    path: "str | Path",
    meta: "dict | None" = None,
    dtype=np.float32,
    include_optimizer: bool = True,
) -> dict:
    """adapter + 优化器状态 + loss 曲线，一起存。"""
    return save_adapter(
        model, path, trainer=trainer, meta=meta, dtype=dtype, include_optimizer=include_optimizer
    )


def load_checkpoint(model, trainer, path: "str | Path") -> dict:
    """恢复 adapter 权重与优化器状态（含 step 计数），之后可直接继续 run。"""
    meta = load_adapter(model, path)
    opt = meta.get("optimizer")
    if trainer is None or not opt:
        return meta
    if not meta.get("include_optimizer", True):
        # 只存了权重：步数仍然恢复，但动量只能从 0 开始（= 假续训）
        trainer.step = int(opt.get("step", trainer.step))
        trainer.losses = [float(x) for x in meta.get("losses", [])]
        return meta
    blob = np.load(Path(path))
    n = len(trainable_parameters(model))
    payload = {
        "name": opt["name"], "lr": opt["lr"], "step": opt["step"], "t": opt.get("t", 0),
        "m": [blob[f"opt_m::{i}"] for i in range(n)],
        "v": [blob[f"opt_v::{i}"] for i in range(n)],
    }
    trainer.load_optimizer_state(payload)
    trainer.losses = [float(x) for x in meta.get("losses", [])]
    return meta


def adapter_report(path: "str | Path", model=None) -> dict:
    """adapter 文件 vs 基座权重的体积对比 —— LoRA 的价值直观体现。"""
    path = Path(path)
    npz = path.stat().st_size
    js = _meta_path(path).stat().st_size
    total = npz + js
    base_bytes = None
    if model is not None:
        counts = count_parameters(model)
        base_bytes = 4.0 * counts["base"]
    return {
        "npz_bytes": npz,
        "json_bytes": js,
        "total_bytes": total,
        "base_fp32_bytes": base_bytes,
        "ratio_of_base": (total / base_bytes) if base_bytes else None,
        "human": human_bytes(total),
        "human_base": human_bytes(base_bytes) if base_bytes else None,
    }
