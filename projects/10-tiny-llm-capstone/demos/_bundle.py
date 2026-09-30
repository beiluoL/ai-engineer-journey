"""11 个 demo 共享的「同一份分词器 / 数据集 / 模型」。

**为什么必须共享**：Capstone 的价值在于「同一条链路上的数字互相能对上」。
如果每个 demo 各训一个模型，M06 说困惑度 316、M07 说 328，那就全乱了。
所以这里做三层缓存（和 P08 缓存基座同一个道理）：

    models/tokenizer.json    分词器（词表一变，所有权重全部错位）
    models/tiny_lm_best.npz  最优检查点（早停回滚后的权重）
    models/report.json       流水线报告

第一次跑会真训（约 30 秒），之后所有 demo 直接复用。
``--force`` 或删掉 ``models/`` 即可重训。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from tiny.config import TinyConfig, default_config  # noqa: E402
from tiny.data import build_dataset, clean_lines, load_corpus, split_lines  # noqa: E402
from tiny.infer import Generator  # noqa: E402
from tiny.model import build_model, build_optimizer  # noqa: E402
from tiny.paths import P10_MODELS  # noqa: E402
from tiny.tok import ensure_tokenizer  # noqa: E402
from tiny.train import LMTrainer, load_checkpoint  # noqa: E402

TOKENIZER_JSON = P10_MODELS / "tokenizer.json"
BEST_NPZ = P10_MODELS / "tiny_lm_best.npz"
LAST_NPZ = P10_MODELS / "tiny_lm.npz"
REPORT_JSON = P10_MODELS / "report.json"

FORCE = "--force" in sys.argv


def build_cfg(**overrides) -> TinyConfig:
    cfg = default_config()
    for key, value in overrides.items():
        section, field_name = key.split("__", 1)
        setattr(getattr(cfg, section), field_name, value)
    return cfg.validate()


def corpus_split(cfg: TinyConfig):
    """语料 → 清洗 → 切分（切分必须在**训词表之前**，否则验证集泄漏）。"""
    raw = load_corpus(cfg)
    kept, clean_report = clean_lines(raw, cfg.data.min_chars, cfg.data.dedup)
    train_lines, val_lines = split_lines(kept, cfg.data.val_ratio, cfg.data.seed)
    return raw, kept, train_lines, val_lines, clean_report


def ensure_bundle(cfg: "TinyConfig | None" = None):
    """取出（必要时训练）``(cfg, tokenizer, dataset, model, train_report)``。"""
    cfg = cfg or build_cfg()
    raw, _kept, train_lines, _val_lines, _clean = corpus_split(cfg)
    tokenizer, trained = ensure_tokenizer(cfg, train_lines, TOKENIZER_JSON)
    dataset = build_dataset(cfg, tokenizer, raw)

    model = build_model(cfg, tokenizer)
    optimizer = build_optimizer(cfg, model)
    reused = False
    report: dict = {"reused": False}
    if not FORCE and BEST_NPZ.is_file() and BEST_NPZ.with_suffix(".json").is_file():
        info = load_checkpoint(model, BEST_NPZ, optimizer=optimizer)
        reused = True
        report = {"reused": True, "meta": info["meta"], "restored": info["restored"]}
    else:
        trainer = LMTrainer(cfg, model, optimizer, dataset.train_examples,
                            dataset.val_examples, verbose=False)
        report = trainer.run(ckpt_path=LAST_NPZ, best_ckpt_path=BEST_NPZ)
        report["reused"] = False
    return cfg, tokenizer, dataset, model, report, {"tokenizer_trained": trained, "model_reused": reused}


def make_generator(model, tokenizer, cfg) -> Generator:
    return Generator(model, tokenizer, cfg)
