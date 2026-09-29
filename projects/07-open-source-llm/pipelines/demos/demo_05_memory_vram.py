"""demo_05 —— 显存账本：权重占多少？KV Cache 占多少？

这是「要不要上量化 / 能不能跑长上下文」这两个决策的算术基础。
同样全部本地计算，数据是 demo_04 用过的那份真实 config.json。

两个常见误区，本 demo 用数字纠正：
1. 以为「模型 7B → 显存 7GB」。实际 bf16 下 ≈ 14GiB，fp32 下 ≈ 28GiB，int4 下 ≈ 3.6GiB。
2. 以为「量化了显存就够用」。权重确实降了，但 **KV Cache 是另一个独立变量**，
   长上下文下它才是大头，且不随权重量化自动下降。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import Tee, fmt_table, rule  # noqa: E402
from llm_client.baselines import (  # noqa: E402
    BYTES_PER_PARAM,
    build_kv_table,
    build_weight_table,
    estimate_params,
    kv_bytes_per_token,
    kv_gb,
    load_models,
    weight_gb,
)

SEQ_LENS = (2048, 8192, 32768)


def main() -> None:
    with Tee("demo_05_memory_vram") as out:
        out.print(rule("demo_05_memory_vram：权重与 KV Cache 显存账本"))
        out.print("")

        meta, models = load_models()
        out.print(f"数据来源：pipelines/data/open_models_weights.json（状态 {meta.get('fetch_status')}）")
        out.print("")

        out.print(rule("换算口径"))
        out.lines(fmt_table(
            ["dtype", "字节/参数"],
            [[k, v] for k, v in BYTES_PER_PARAM.items()],
        ))
        out.print("   公式：权重 GiB = 参数量 × 字节/参数 ÷ 1024³")
        out.print("   公式：KV Cache/token = 2(K,V) × 层数 × kv_heads × head_dim × 字节/参数")
        out.print("")

        out.print(rule("表 1：同一模型在不同精度下的权重大小（GiB）"))
        out.lines(fmt_table(
            ["模型", "标称", "手算(B)", "fp16", "int8", "int4"],
            build_weight_table(models),
        ))
        out.print("")
        spec7 = models[-1]
        est = estimate_params(spec7.config)
        out.print(f"   以 {spec7.repo.split('/')[-1]} 为例：")
        for dtype in ("fp32", "bf16", "int8", "int4"):
            out.print(f"     {dtype:>5s} 权重 = {weight_gb(est['total'], dtype):6.2f} GiB")
        out.print(f"   -> bf16 → int4 把 {weight_gb(est['total'], 'bf16'):.2f} GiB 压到 "
                  f"{weight_gb(est['total'], 'int4'):.2f} GiB，降为 1/4。")
        out.print("")

        out.print(rule("表 2：KV Cache（bf16，batch=1）随上下文长度增长"))
        out.lines(fmt_table(
            ["模型", "层数", "KV头", "字节/token"]
            + [f"{s // 1024}K tokens" for s in SEQ_LENS],
            build_kv_table(models, SEQ_LENS),
        ))
        out.print("")

        out.print(rule("关键对照：KV Cache 会不会追上权重？"))
        for spec in models:
            est = estimate_params(spec.config)
            w = weight_gb(est["total"], "bf16")
            per_token = kv_bytes_per_token(spec.config)
            name = spec.repo.split("/")[-1]
            out.print(f"   {name}")
            out.print(f"     权重(bf16)        = {w:6.2f} GiB")
            out.print(f"     KV/token          = {per_token:6.0f} B")
            crossover = None
            for s in SEQ_LENS:
                kv = kv_gb(spec.config, s)
                out.print(f"     seq={s:>6d} -> KV = {kv:6.2f} GiB"
                          f"   (KV/权重 = {kv / w * 100:5.1f}%)")
                if crossover is None and kv >= w:
                    crossover = s
            out.print(f"     -> 首次超过权重的序列长度：{crossover if crossover else '在测试范围内未超过'}")
            out.print("")

        out.print(rule("两个结论"))
        out.print("   1. 量化权重 ≠ 解决长上下文。KV Cache 独立按 上下文长度 × batch 线性增长，")
        out.print("      要压它得单独量化 KV（或用 GQA/MLA 这类结构上就省 KV 的架构）。")
        out.print("   2. GQA 的价值在这里变现：表里 KV 头数远小于注意力头数，")
        out.print("      同样算力下能撑的上下文长度直接翻倍。")
        out.print("")

        out.save_json({
            "weight_table": build_weight_table(models),
            "kv_table": build_kv_table(models, SEQ_LENS),
            "seq_lens": list(SEQ_LENS),
        })


if __name__ == "__main__":
    main()
