#!/usr/bin/env python
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import adapter_bundle  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.compare import evaluate_models, paired_compare  # noqa: E402
from ie.metrics import evaluate  # noqa: E402
from ie.quantize import quantize_model  # noqa: E402
from ie.paths import ensure_deps_importable  # noqa: E402

ensure_deps_importable()
from ft import ensure_base_model, merge_lora  # noqa: E402


def _example_losses(model, examples) -> np.ndarray:
    return np.asarray([evaluate(model, [example], batch_size=1, n_bins=5)["mean_ce"] for example in examples])


def main() -> None:
    with Printer("demo_05_model_comparison") as out:
        out.section("M05 · Model Comparison：多种子配对比较")
        adapter, _tok, _info, split, _train, examples, artifact = adapter_bundle()
        base, _, _ = ensure_base_model()
        merged = deepcopy(adapter)
        merge_lora(merged)
        quantized, qreport = quantize_model(merged, bits=8, granularity="per_channel")
        model_losses = {
            "基座": _example_losses(base, examples),
            "加载 adapter": _example_losses(adapter, examples),
            "合并后": _example_losses(merged, examples),
            "INT8 量化后": _example_losses(quantized, examples),
        }
        seeds = list(range(10))

        def bootstrap(values: np.ndarray, seed: int) -> float:
            rng = np.random.default_rng(seed)
            indices = rng.integers(0, len(values), size=len(values))
            return float(values[indices].mean())

        result = evaluate_models(model_losses, seeds, bootstrap, baseline="基座", lower_is_better=True)
        out.kv("held-out", len(split.heldout), "与 adapter 训练集 instruction 交集为 0")
        out.kv("重复 seed", len(seeds), "同一 seed 使用同一组 bootstrap 下标")
        out.kv("P09 adapter", artifact["path"])
        out.kv("本次是否新训练", artifact["trained"])
        if artifact["losses"]:
            out.kv("adapter 训练 loss", f"{artifact['losses'][0]:.4f} → {artifact['losses'][-1]:.4f}")
        out.kv("INT8 权重 MSE", f"{qreport['mse']:.8e}")
        out.subsection("答案区交叉熵：均值 ± 样本标准差（越低越好）")
        out.table(
            ["排名", "模型", "mean", "std", "相对基座胜/负/平", "稳定"],
            [[rank, name, f"{result['summary'][name]['mean']:.6f}",
              f"{result['summary'][name]['std']:.6f}",
              "-" if name == "基座" else f"{result['paired'][name]['wins']}/{result['paired'][name]['losses']}/{result['paired'][name]['ties']}",
              "基线" if name == "基座" else ("是" if result['paired'][name]['stable'] else "否")]
             for rank, name in enumerate(result["ranking"], 1)],
            aligns=[">", "<", ">", ">", ">", "<"],
        )
        adapter_merge = paired_compare(
            [bootstrap(model_losses["加载 adapter"], seed) for seed in seeds],
            [bootstrap(model_losses["合并后"], seed) for seed in seeds],
            lower_is_better=True,
            atol=1e-10,
        )
        out.subsection("配对结论")
        out.kv("adapter vs 合并后", f"胜/负/平 = {adapter_merge['wins']}/{adapter_merge['losses']}/{adapter_merge['ties']}")
        out.kv("是否稳定翻盘", "是" if any(v["noise_flip"] for v in result["paired"].values()) else "否")
        noisy = [name for name, value in result["paired"].items() if value["noise_flip"]]
        out.kv("发生噪声内翻转的比较", ", ".join(noisy) if noisy else "无")
        out.line("  merge 与 adapter 理论等价；配对中的平局不是缺数据，而是等价性的实测证据。")


if __name__ == "__main__":
    main()
