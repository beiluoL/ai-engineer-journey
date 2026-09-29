#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import base_bundle  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.metrics import perplexity  # noqa: E402
from ie.paths import P09_MODELS  # noqa: E402
from ie.quantize import (  # noqa: E402
    compare_quantizers,
    quantize_model,
    quantize_model_nf4,
    save_quantized_artifact,
)


def main() -> None:
    with Printer("demo_06_quantization") as out:
        out.section("M06 · Quantization：INT8 / INT4 / NF4")
        model, _tok, _info, _split, _train, examples = base_bundle(heldout_size=8, max_len=128)
        matrix = model.decoder.proj.data
        comparison = compare_quantizers(matrix, granularity="per_channel", block_size=64)
        out.kv("对比权重", f"decoder.proj {matrix.shape}，{matrix.size:,} 参数")
        out.subsection("权重误差与理论存储压缩")
        out.table(
            ["方案", "MSE", "相对 L2", "存储 bytes", "相对 fp32 压缩"],
            [[name, f"{row['mse']:.8e}", f"{row['relative_l2']:.6f}",
              f"{row['storage_bytes']:.0f}", f"{row['compression_ratio']:.2f}×"]
             for name, row in comparison.items()],
            aligns=["<", ">", ">", ">", ">"],
        )

        int8_model, int8_report = quantize_model(model, 8, "per_channel")
        int4_model, int4_report = quantize_model(model, 4, "per_channel")
        nf4_model, nf4_report = quantize_model_nf4(model, block_size=64, double_quant=True)
        save_quantized_artifact(int8_report, P09_MODELS / "base_int8_per_channel.npz")
        save_quantized_artifact(int4_report, P09_MODELS / "base_int4_per_channel.npz")
        ppls = {
            "FP64 计算基线": perplexity(model, examples, batch_size=2),
            "INT8": perplexity(int8_model, examples, batch_size=2),
            "INT4": perplexity(int4_model, examples, batch_size=2),
            "NF4": perplexity(nf4_model, examples, batch_size=2),
        }
        baseline = ppls["FP64 计算基线"]
        out.subsection("端到端答案区困惑度（同一 held-out）")
        out.table(
            ["方案", "PPL", "相对变化"],
            [[name, f"{value:.4f}", f"{(value / baseline - 1) * 100:+.3f}%"] for name, value in ppls.items()],
            aligns=["<", ">", ">"],
        )
        out.subsection("关键结论")
        out.kv("INT8 / INT4 / NF4 MSE", " / ".join(f"{comparison[n]['mse']:.3e}" for n in ("INT8", "INT4", "NF4")))
        out.kv("INT8 / INT4 / NF4 压缩比", " / ".join(f"{comparison[n]['compression_ratio']:.2f}×" for n in ("INT8", "INT4", "NF4")))
        out.kv("端到端 PPL 代价（INT8）", f"{ppls['INT8'] - baseline:+.4f}")
        out.kv("端到端 PPL 代价（INT4）", f"{ppls['INT4'] - baseline:+.4f}")
        out.kv("端到端 PPL 代价（NF4）", f"{ppls['NF4'] - baseline:+.4f}")
        out.line("  权重 MSE 最小不自动等价于端到端 PPL 最优，必须在任务集上复测。")


if __name__ == "__main__":
    main()
