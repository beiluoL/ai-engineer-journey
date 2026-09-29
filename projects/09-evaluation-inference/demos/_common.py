"""多个 demo 共享的确定性模型与 held-out 构建。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from ie.evalset import build_evaluation_set  # noqa: E402
from ie.paths import P09_MODELS, ensure_deps_importable  # noqa: E402

ensure_deps_importable()

from ft import (  # noqa: E402
    LoRATrainer,
    build_sft_examples,
    ensure_base_model,
    inject_lora,
    load_adapter,
    load_java_records,
    save_adapter,
)

ADAPTER_PATH = P09_MODELS / "java_heldout_safe_adapter.npz"


def data_split(heldout_size: int = 8):
    records = load_java_records()
    return build_evaluation_set(records, heldout_size=heldout_size, seed=0)


def base_bundle(heldout_size: int = 8, max_len: int = 128):
    model, tokenizer, info = ensure_base_model()
    split = data_split(heldout_size)
    train_examples = build_sft_examples(split.train, tokenizer, max_len=max_len)
    eval_examples = build_sft_examples(split.heldout, tokenizer, max_len=max_len)
    return model, tokenizer, info, split, train_examples, eval_examples


def adapter_bundle(heldout_size: int = 8, max_len: int = 128, steps: int = 24):
    model, tokenizer, info, split, train_examples, eval_examples = base_bundle(heldout_size, max_len)
    inject_lora(model, r=4, alpha=8.0, rng=0)
    trained = False
    losses: list[float] = []
    if ADAPTER_PATH.is_file() and ADAPTER_PATH.with_suffix(".json").is_file():
        load_adapter(model, ADAPTER_PATH)
    else:
        trainer = LoRATrainer(model, lr=3e-3, optimizer="adam", seed=0)
        losses = trainer.run(train_examples, n_steps=steps, batch_size=4)
        save_adapter(
            model, ADAPTER_PATH, trainer=None, dtype=np.float64, include_optimizer=False,
            meta={"heldout_size": heldout_size, "seed": 0, "train_steps": steps},
        )
        trained = True
    return model, tokenizer, info, split, train_examples, eval_examples, {
        "path": ADAPTER_PATH, "trained": trained, "losses": losses,
    }
