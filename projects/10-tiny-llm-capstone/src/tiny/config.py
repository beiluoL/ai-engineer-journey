"""Project 10 —— 配置契约：整个工程只有**一个**配置对象。

为什么第一层就写配置：Capstone 要跑的是「Tokenizer → Dataset → Model →
Training → Evaluation → Inference → Optimization → Serving」八段链路，
而前面几个项目的踩坑经验是 —— **超参数一旦散落在各个脚本里，实验就不可复现**。
P08 的 hparams 扫描、P09 的模型对比都出现过「两份代码各自抄了一份默认值」的问题。

所以本模块定三条硬规矩：

1. 所有可调项都进 :class:`TinyConfig`，任何脚本只能从它读，不许自带默认值；
2. :meth:`TinyConfig.validate` 在**建模型之前**把不自洽的组合挡掉
   （比如 ``d_model % n_heads != 0``、``vocab_size`` 小于字符集大小）；
3. 配置能 :meth:`save` 成 JSON、能 :meth:`load` 回来，训练产物目录里一定
   留一份，报告里的每个数字都能对上是哪份配置跑出来的。

约定：``model.vocab_size`` 允许先写 0 表示「跟着分词器走」，建模型前由
:func:`resolve_vocab_size` 填实。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

__all__ = [
    "DataConfig",
    "GenConfig",
    "ModelConfig",
    "OptimConfig",
    "ServeConfig",
    "TinyConfig",
    "TokenizerConfig",
    "TrainConfig",
    "default_config",
    "load_config",
    "resolve_vocab_size",
    "save_config",
]


@dataclass
class TokenizerConfig:
    """分词器配置。"""

    kind: str = "bpe"  # bpe | char
    #: 1280 = 4 个特殊 token + ~870 个基础字符 + ~400 次合并
    vocab_size: int = 1280
    #: 低于该频次的相邻符号对不再合并（BPE 早停）
    min_pair_freq: int = 1


@dataclass
class ModelConfig:
    """模型结构配置。``vocab_size=0`` 表示沿用分词器词表。"""

    vocab_size: int = 0
    d_model: int = 64
    n_heads: int = 4
    d_ff: int = 128
    n_layers: int = 2
    max_len: int = 64


@dataclass
class DataConfig:
    """语料与数据集配置。"""

    #: 相对 P10 根目录的路径；None 表示用自带的 data/corpus.txt
    corpus: "str | None" = None
    #: 是否额外混入 P06 的通用语料（通用 + 领域混合预训练）
    include_general: bool = True
    min_chars: int = 8
    dedup: bool = True
    val_ratio: float = 0.15
    #: True=把语料首尾相接再滑窗（少 padding）；False=每行一个样本
    pack: bool = True
    stride: int = 32  # pack 模式下的滑窗步长
    seed: int = 0


@dataclass
class OptimConfig:
    """优化器与学习率调度。"""

    optimizer: str = "adam"  # adam | sgd
    #: 1e-3 是实测扫出来的：3e-3 会让 val 在第 300 步就开始回升（M06 有对照表）
    lr: float = 1e-3
    betas: tuple[float, float] = (0.9, 0.999)
    eps: float = 1e-8
    weight_decay: float = 0.0
    warmup_steps: int = 20
    #: 余弦衰减的终点 = lr * min_lr_ratio
    min_lr_ratio: float = 0.05
    grad_clip: float = 1.0


@dataclass
class TrainConfig:
    """训练过程配置。"""

    batch_size: int = 8
    n_steps: int = 1200
    eval_every: int = 100
    #: 验证指标连续多少次评估没改善就早停（0=不早停）
    patience: int = 4
    log_every: int = 100
    seed: int = 0
    #: 断点续训时从这里恢复；None 表示从头训
    resume_from: "str | None" = None


@dataclass
class GenConfig:
    """推理采样配置。"""

    max_new_tokens: int = 24
    temperature: float = 0.8
    top_k: int = 0  # 0=不启用
    top_p: float = 0.95
    #: 1.15 —— M08 实测：贪心解码在这个小模型上会退化成复读（重复率 94.7%）
    repetition_penalty: float = 1.15
    seed: int = 0
    use_kv_cache: bool = True


@dataclass
class ServeConfig:
    """服务化配置。"""

    host: str = "127.0.0.1"
    port: int = 0  # 0=由操作系统分配空闲端口
    max_tokens: int = 32
    #: 压测并发数
    concurrency: int = 4


@dataclass
class TinyConfig:
    """Project 10 的唯一配置入口。"""

    name: str = "tiny-llm"
    seed: int = 0
    tokenizer: TokenizerConfig = field(default_factory=TokenizerConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    optim: OptimConfig = field(default_factory=OptimConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    gen: GenConfig = field(default_factory=GenConfig)
    serve: ServeConfig = field(default_factory=ServeConfig)

    # ---------------------------------------------------------------- 校验
    def validate(self) -> "TinyConfig":
        """检查配置自洽，任一处不合法就抛 :class:`ValueError`（带具体原因）。"""
        problems: list[str] = []
        m, t, d, g = self.model, self.tokenizer, self.data, self.gen

        if m.d_model <= 0:
            problems.append(f"model.d_model 必须为正，当前 {m.d_model}")
        if m.n_heads <= 0:
            problems.append(f"model.n_heads 必须为正，当前 {m.n_heads}")
        elif m.d_model % m.n_heads:
            problems.append(
                f"model.d_model({m.d_model}) 必须能被 n_heads({m.n_heads}) 整除，"
                "否则无法把向量均分到各头"
            )
        if m.n_layers <= 0:
            problems.append(f"model.n_layers 必须为正，当前 {m.n_layers}")
        if m.max_len <= 1:
            problems.append(f"model.max_len 必须大于 1，当前 {m.max_len}")
        if m.vocab_size < 0:
            problems.append(f"model.vocab_size 不能为负，当前 {m.vocab_size}")
        if t.vocab_size < 8:
            problems.append(f"tokenizer.vocab_size 太小（{t.vocab_size}），至少要容纳特殊 token")
        if t.kind not in ("bpe", "char"):
            problems.append(f"tokenizer.kind 只支持 bpe/char，当前 {t.kind!r}")
        if not 0.0 < d.val_ratio < 0.5:
            problems.append(f"data.val_ratio 必须落在 (0, 0.5)，当前 {d.val_ratio}")
        if d.stride <= 0 or d.stride > m.max_len:
            problems.append(
                f"data.stride({d.stride}) 必须落在 (0, model.max_len={m.max_len}]"
            )
        if self.train.batch_size <= 0:
            problems.append(f"train.batch_size 必须为正，当前 {self.train.batch_size}")
        if self.train.n_steps <= 0:
            problems.append(f"train.n_steps 必须为正，当前 {self.train.n_steps}")
        if self.optim.lr <= 0:
            problems.append(f"optim.lr 必须为正，当前 {self.optim.lr}")
        if self.optim.warmup_steps < 0:
            problems.append(f"optim.warmup_steps 不能为负，当前 {self.optim.warmup_steps}")
        if not 0.0 <= self.optim.min_lr_ratio <= 1.0:
            problems.append(f"optim.min_lr_ratio 必须落在 [0, 1]，当前 {self.optim.min_lr_ratio}")
        if g.temperature < 0:
            problems.append(f"gen.temperature 不能为负，当前 {g.temperature}")
        if not 0.0 < g.top_p <= 1.0:
            problems.append(f"gen.top_p 必须落在 (0, 1]，当前 {g.top_p}")
        if g.top_k < 0:
            problems.append(f"gen.top_k 不能为负，当前 {g.top_k}")
        if g.repetition_penalty <= 0:
            problems.append(f"gen.repetition_penalty 必须为正，当前 {g.repetition_penalty}")

        if problems:
            joined = "\n".join(f"  - {p}" for p in problems)
            raise ValueError(f"TinyConfig 校验未通过：\n{joined}")
        return self

    # ---------------------------------------------------------------- 序列化
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # tuple 在 JSON 里会变成 list，回来时再转回 tuple
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TinyConfig":
        """从字典重建；**只认已知字段**，拼错的配置项会被显式拒绝。"""
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"未知配置项：{unknown}")
        payload = dict(data)
        for section, klass in (
            ("tokenizer", TokenizerConfig),
            ("model", ModelConfig),
            ("data", DataConfig),
            ("optim", OptimConfig),
            ("train", TrainConfig),
            ("gen", GenConfig),
            ("serve", ServeConfig),
        ):
            raw = payload.pop(section, None)
            if raw is None:
                continue
            section_known = {f.name for f in fields(klass)}
            section_unknown = sorted(set(raw) - section_known)
            if section_unknown:
                raise ValueError(f"{section} 段出现未知配置项：{section_unknown}")
            payload[section] = klass(**raw)
        cfg = cls(**payload)
        if isinstance(cfg.optim.betas, list):
            cfg.optim.betas = tuple(cfg.optim.betas)  # type: ignore[assignment]
        return cfg

    def save(self, path: "str | Path") -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: "str | Path") -> "TinyConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---------------------------------------------------------------- 展示
    def summary_lines(self) -> list[str]:
        """给 demo / 报告用的一行行配置摘要。"""
        m, t, d, o, tr = self.model, self.tokenizer, self.data, self.optim, self.train
        return [
            f"name                {self.name}",
            f"tokenizer           {t.kind}  vocab_size={t.vocab_size}  min_pair_freq={t.min_pair_freq}",
            f"model               d_model={m.d_model}  n_heads={m.n_heads}  d_ff={m.d_ff}"
            f"  n_layers={m.n_layers}  max_len={m.max_len}",
            f"data                val_ratio={d.val_ratio}  pack={d.pack}  stride={d.stride}"
            f"  dedup={d.dedup}  include_general={d.include_general}",
            f"optim               {o.optimizer}  lr={o.lr}  warmup={o.warmup_steps}"
            f"  min_lr_ratio={o.min_lr_ratio}  grad_clip={o.grad_clip}",
            f"train               batch={tr.batch_size}  steps={tr.n_steps}"
            f"  eval_every={tr.eval_every}  patience={tr.patience}",
            f"gen                 max_new_tokens={self.gen.max_new_tokens}"
            f"  temperature={self.gen.temperature}  top_k={self.gen.top_k}"
            f"  top_p={self.gen.top_p}",
            f"serve               {self.serve.host}:{self.serve.port}"
            f"  max_tokens={self.serve.max_tokens}  concurrency={self.serve.concurrency}",
        ]


def default_config() -> TinyConfig:
    """默认配置（约 20 万参数的 Tiny LLM）。"""
    return TinyConfig().validate()


def resolve_vocab_size(cfg: TinyConfig, tokenizer) -> TinyConfig:
    """把 ``model.vocab_size`` 的 0 填成分词器的真实词表大小。

    为什么需要这一步：词表大小由**分词器**决定，而分词器要先看到语料才能训出来；
    但模型结构配置在写文件时并不知道这个数。所以约定 0 = 「跟着分词器走」，
    建模型前统一在这里填实，避免出现「模型词表 1000、分词器词表 1024」这种
    **能跑但越界** 的隐患。
    """
    real = int(getattr(tokenizer, "vocab_size"))
    if cfg.model.vocab_size == 0:
        cfg.model.vocab_size = real
    elif cfg.model.vocab_size != real:
        raise ValueError(
            f"配置里的 vocab_size({cfg.model.vocab_size}) 与分词器词表({real}) 不一致；"
            "若想跟随分词器，请把 model.vocab_size 设为 0"
        )
    return cfg


def save_config(cfg: TinyConfig, path: "str | Path") -> Path:
    return cfg.save(path)


def load_config(path: "str | Path") -> TinyConfig:
    return TinyConfig.load(path)
