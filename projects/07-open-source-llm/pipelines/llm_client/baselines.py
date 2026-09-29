"""开源 LLM 的「教科书 vs 现实」基线：把架构参数换算成真金白银的字节数。

诚实性边界（写文档时必须照抄这条）
---------------------------------
- :data:`open_models_weights.json` 里的 ``config`` 字段来自各模型公开的 HF config.json
  / model card。这部分是**公开事实**，会随版本变化，因此一律标注「以官方为准」。
- 但本模块负责的是**确定性的本地算术**——给定一个 hidden_size/layers/heads 的配置，
  参数量、权重体积、KV Cache 占用都可以在本机算出来，不联网、不问 LLM、100% 可复现。

换句话说：文档里称为「真实运行结果」的数字，指的是**这里算出来的**，
而不是从哪篇文章抄来的。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent / "data" / "open_models_weights.json"

BYTES_PER_PARAM = {
    "fp32": 4.0,
    "fp16": 2.0,
    "bf16": 2.0,
    "int8": 1.0,
    "int4": 0.5,   # NF4 / INT4 近似：4 bit = 0.5 byte
}
GIB = 1024**3


@dataclass
class ModelSpec:
    repo: str
    nominal: str
    config: dict
    fetch: str = "unknown"
    source: str = ""

    @property
    def dtype_default(self) -> str:
        return str(self.config.get("torch_dtype", "bf16")).replace("bfloat16", "bf16")


def load_models(path: str | Path = DEFAULT_DATA) -> tuple[dict, list[ModelSpec]]:
    """返回 ``(meta, models)``。meta 里带 fetch_status / source_note，便于文档标注可信度。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"数据文件不存在：{p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    models = [
        ModelSpec(
            repo=m["repo"],
            nominal=m.get("nominal", "?"),
            config=m.get("config", {}),
            fetch=m.get("fetch", "unknown"),
            source=m.get("source", ""),
        )
        for m in raw.get("models", [])
    ]
    meta = {k: v for k, v in raw.items() if k != "models"}
    return meta, models


def arch_of(cfg: dict) -> dict:
    """补齐字段推导：head_dim / kv_heads 缺了就按常规算法推出来。"""
    hidden = int(cfg["hidden_size"])
    heads = int(cfg["num_attention_heads"])
    return {
        "hidden": hidden,
        "layers": int(cfg["num_hidden_layers"]),
        "heads": heads,
        "kv_heads": int(cfg.get("num_key_value_heads", heads)),
        "head_dim": int(cfg.get("head_dim", hidden // heads)),
        "inter": int(cfg["intermediate_size"]),
        "vocab": int(cfg["vocab_size"]),
        "tied": bool(cfg.get("tie_word_embeddings", False)),
        "max_pos": int(cfg.get("max_position_embeddings", 0)),
    }


def estimate_params(cfg: dict) -> dict:
    """按标准 decoder-only（GQA + SwiGLU）结构手算参数量。

    返回明细字典，方便文档解释「每个部分各占多少」——这正是 P06 从零实现过、
    现在能在真实模型上对账的东西。注意这是**近似**：bias、MoE、特殊 norm 会让它有出入。
    """
    a = arch_of(cfg)
    h, L = a["hidden"], a["layers"]
    qi = a["heads"] * a["head_dim"]        # Q 的输出维度
    kvi = a["kv_heads"] * a["head_dim"]    # K/V 的输出维度
    inter = a["inter"]

    embed = a["vocab"] * h
    lm_head = 0 if a["tied"] else embed
    attn = h * qi + h * kvi + h * kvi + qi * h          # q/k/v/o
    mlp = 3 * h * inter                                  # gate + up + down
    ln = 2 * h                                           # 每层 2 个 LayerNorm
    per_layer = attn + mlp + ln
    final_norm = h

    total = embed + lm_head + L * per_layer + final_norm
    return {
        "arch": a,
        "embed": embed,
        "lm_head": lm_head,
        "per_layer": per_layer,
        "attn_per_layer": attn,
        "mlp_per_layer": mlp,
        "total": total,
        "total_b": total / 1e9,
    }


def weight_gb(n_params: int, dtype: str = "bf16") -> float:
    """参数量 → 权重大小（GiB）。"""
    return n_params * BYTES_PER_PARAM[dtype] / GIB


def kv_bytes_per_token(cfg: dict, dtype: str = "bf16") -> int:
    """每个 token 的 KV Cache 字节数。

    公式：2(K,V) × 层数 × kv_heads × head_dim × 每参数字节。
    注意这里用 kv_heads 而不是 heads —— GQA 正是靠它把 KV Cache 砍下来的，
    这是本文件里最有「工程含金量」的一行。
    """
    a = arch_of(cfg)
    # 用浮点而非整除：int4 时每参数是 0.5 字节，整除会把 KV Cache 直接算成 0。
    return 2.0 * a["layers"] * a["kv_heads"] * a["head_dim"] * BYTES_PER_PARAM[dtype]


def kv_gb(cfg: dict, seq_len: int, dtype: str = "bf16", batch: int = 1) -> float:
    """给定序列长度与 batch，估算 KV Cache 总占用（GiB）。"""
    return kv_bytes_per_token(cfg, dtype) * seq_len * batch / GIB


def build_weight_table(models: list[ModelSpec]) -> list[list]:
    """[[模型, 标称, 手算(B), fp16 GiB, int8 GiB, int4 GiB], ...]"""
    rows = []
    for m in models:
        est = estimate_params(m.config)
        rows.append([
            m.repo.split("/")[-1],
            m.nominal,
            f"{est['total_b']:.2f}",
            f"{weight_gb(est['total'], 'fp16'):.2f}",
            f"{weight_gb(est['total'], 'int8'):.2f}",
            f"{weight_gb(est['total'], 'int4'):.2f}",
        ])
    return rows


def build_kv_table(models: list[ModelSpec], seq_lens=(2048, 8192, 32768)) -> list[list]:
    """[[模型, 层数, KV头数, 每token字节, seq2k GiB, seq8k GiB, seq32k GiB], ...]"""
    rows = []
    for m in models:
        a = arch_of(m.config)
        per_token = kv_bytes_per_token(m.config)
        row = [
            m.repo.split("/")[-1],
            str(a["layers"]),
            str(a["kv_heads"]),
            str(per_token),
        ]
        row += [f"{kv_gb(m.config, s):.2f}" for s in seq_lens]
        rows.append(row)
    return rows


__all__ = [
    "BYTES_PER_PARAM",
    "ModelSpec",
    "arch_of",
    "build_kv_table",
    "build_weight_table",
    "estimate_params",
    "kv_bytes_per_token",
    "kv_gb",
    "load_models",
    "weight_gb",
]
