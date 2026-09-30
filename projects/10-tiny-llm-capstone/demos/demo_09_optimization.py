#!/usr/bin/env python
"""M09 · Optimization：把「能跑的模型」变成「部署得起的模型」。

模型训完要面对三个现实问题：**太大、太慢、太贵**。本章给出三条优化路径，
每条都同时回答「省了多少」和「代价是什么」——不量化代价的优化等于没做。

一个刻意保留的反直觉结论：**在这个 20 万参数的小模型上，INT4 的代价明显
大于 INT8**。小模型每层权重少、冗余低，4 bit 的粗粒度误差占比反而更高，
这和 7B 模型上「INT4 基本无损」的常识是相反的。真实数字在第 3 节。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.infer import Generator  # noqa: E402
from tiny.optimize import (  # noqa: E402
    deployment_size_table,
    granularity_report,
    kv_cache_report,
    quantization_report,
)


def main() -> None:
    with Printer("demo_09_optimization") as out:
        out.section("M09 · Optimization：量化 / KV Cache / 部署体积 —— 收益与代价一起量")

        cfg = build_cfg()
        cfg, tokenizer, dataset, model, _report, _cache = ensure_bundle(cfg)
        generator = Generator(model, tokenizer, cfg)

        from tiny.model import parameter_report  # noqa: PLC0415

        params = parameter_report(model)
        out.subsection("1. 起点：这个模型到底有多大")
        out.kv("参数量", f"{params['total']:,}")
        out.kv("张量数", params["n_tensors"])
        out.kv("fp64（训练时）", f"{params['mib']:.2f} MiB")
        for name, count in sorted(params["groups"].items(), key=lambda kv: -kv[1]):
            out.kv(f"  └ {name}", f"{count:,}  ({count / params['total'] * 100:.1f}%)")

        # ---------------------------------------------------------- 部署体积
        out.subsection("2. 部署体积账：同一份权重，五档精度")
        rows = []
        for row in deployment_size_table(model, params["total"]):
            rows.append([
                row["precision"],
                f"{row['bytes_per_param']:g}",
                f"{row['bytes']:,}",
                f"{row['mib']:.2f}",
            ])
        out.table(["精度", "字节/参数", "总字节", "MiB"], rows, aligns=["<", ">", ">", ">"])
        out.kv("fp64 → INT4 的压缩比", f"{8 / 0.5:.0f}×")
        out.kv("现实约束", "训练要 fp64/fp32，推理只要 fp16，边缘部署才上 INT8/INT4")

        # ---------------------------------------------------------- KV Cache
        out.subsection("3. KV Cache 账本：每 token 多少字节，多长上下文会超过权重")
        rows_holder = kv_cache_report(cfg, model, params["total"])
        arch = rows_holder["architecture"]
        out.kv("架构", f"layers={arch['layers']}  kv_heads={arch['kv_heads']}  head_dim={arch['head_dim']}")
        out.kv("每 token（fp32 / fp16）",
               f"{rows_holder['bytes_per_token_fp32']} B / {rows_holder['bytes_per_token_fp16']} B")
        out.kv("公式", "2（K和V）× layers × kv_heads × head_dim × dtype_bytes")
        out.kv("模型权重（fp32）", f"{rows_holder['weight_bytes_fp32']:,} B")
        table_rows = []
        for row in rows_holder["table"]:
            table_rows.append([
                row["batch_size"],
                row["seq_len"],
                f"{row['kv_bytes']:,}",
                f"{row['kv_gib']:.6f}",
                "-" if row["vs_weights"] is None else f"{row['vs_weights'] * 100:.4f}%",
            ])
        out.table(["batch", "seq_len", "KV 字节", "KV GiB", "占权重比"],
                  table_rows, aligns=[">", ">", ">", ">", ">"])
        exceed = rows_holder["seq_len_to_exceed_weights"]
        out.kv("KV Cache 追上模型权重所需长度", exceed, "fp16、batch=1")
        out.kv("实测 max_len 下的 KV", f"{rows_holder['kv_bytes_at_max_len']:,} B"
               f"（{rows_holder['kv_bytes_at_max_len'] / 1024:.2f} KiB）")
        out.kv("结论", "这个模型小到 KV Cache 几乎不花钱；但公式在 7B 上是致命的")

        # ---------------------------------------------------------- 量化
        out.subsection("4. 量化：压缩比 vs 精度代价（在真实验证集上量）")
        q = quantization_report(cfg, model, dataset.val_examples)
        base = q["baseline"]
        out.kv("基线（未量化）", f"val_loss={base['loss']:.4f}  ppl={base['perplexity']:.2f}"
               f"  token_acc={base['token_accuracy']:.4f}")
        rows = []
        for name, item in q["quantizers"].items():
            rows.append([
                name,
                item["granularity"],
                f"{item['compression_ratio']:.2f}×",
                f"{item['mse']:.3e}",
                f"{item['ppl_before']:.2f}",
                f"{item['ppl_after']:.2f}",
                f"{item['ppl_delta_pct']:+.2f}%",
                f"{item['token_accuracy_after']:.4f}",
            ])
        out.table(["精度", "粒度", "压缩比", "MSE", "量化前 PPL", "量化后 PPL", "ΔPPL", "token_acc"],
                  rows, aligns=["<", "<", ">", ">", ">", ">", ">", ">"])
        out.kv("判据", "压缩比只说明省了多少空间；ΔPPL 才说明代价 —— 两个都要看")
        int8 = q["quantizers"]["INT8"]
        int4 = q["quantizers"]["INT4"]
        nf4 = q["quantizers"]["NF4"]
        out.kv("反直觉结论", f"INT4 ΔPPL {int4['ppl_delta_pct']:+.2f}% 远大于 INT8 {int8['ppl_delta_pct']:+.2f}%")
        out.kv("为什么", "小模型每层权重少、冗余低，4 bit 的粗粒度误差占比反而更高")
        out.kv("NF4 是否更划算", f"NF4 ΔPPL {nf4['ppl_delta_pct']:+.2f}% / 压缩 {nf4['compression_ratio']:.2f}×")

        # ---------------------------------------------------------- 粒度
        out.subsection("5. 粒度：per-tensor vs per-channel vs NF4（同一份权重的误差对照）")
        gran = granularity_report(model)
        out.kv("取样张量", gran["tensor"])
        out.kv("形状", gran["shape"])
        out.kv("权重幅度离散度 std/mean|w|", f"{gran['std_over_mean_abs']:.3f}", "越大说明各通道尺度越不齐")
        rows = []
        for name in ("INT8", "INT4", "NF4"):
            pt = gran["per_tensor"][name]
            pc = gran["per_channel"][name]
            rows.append([
                name,
                f"{pt['mse']:.3e}",
                f"{pc['mse']:.3e}",
                f"{(1 - pc['mse'] / pt['mse']) * 100:.1f}%" if pt["mse"] else "-",
                f"{pt['relative_l2']:.4f}",
                f"{pc['relative_l2']:.4f}",
            ])
        out.table(["精度", "per-tensor MSE", "per-channel MSE", "MSE 降低", "rL2(per-t)", "rL2(per-c)"],
                  rows, aligns=["<", ">", ">", ">", ">", ">"])
        out.kv("结论", "per-channel 是**免费**的精度：只多存一点尺度，误差就明显下降")

        # ---------------------------------------------------------- 速度
        out.subsection("6. 另一半优化：KV Cache 的速度收益（M08 已证明等价）")
        prompt = "问：什么是 LoRA？答："
        bench = generator.benchmark(prompt, repeats=5, max_new_tokens=24)
        out.kv("无缓存 / 有缓存 中位耗时", f"{bench['no_cache_ms']:.2f} ms / {bench['kv_cache_ms']:.2f} ms")
        out.kv("加速比", f"{bench['speedup']:.2f}×")
        out.kv("输出是否一致", bench["outputs_equal"], "不等价的速度优化是 bug，不是优化")
        out.kv("logits 最大绝对误差", f"{bench['max_logit_error']:.3e}")

        # ---------------------------------------------------------- 综合
        out.subsection("7. 一张表说清楚：每种优化的收益与代价")
        tradeoffs = [
            ["INT8 per-channel", "体积 ÷4", f"PPL {int8['ppl_delta_pct']:+.2f}%", "小模型首选"],
            ["INT4 per-channel", "体积 ÷8", f"PPL {int4['ppl_delta_pct']:+.2f}%", "小模型上不划算"],
            ["NF4（block 64 双重量化）", f"体积 ÷{nf4['compression_ratio']:.1f}",
             f"PPL {nf4['ppl_delta_pct']:+.2f}%", "比 INT4 稳"],
            ["KV Cache", f"延迟 ÷{bench['speedup']:.2f}", "显存 +每 token 字节", "严格无损"],
        ]
        out.table(["优化手段", "收益", "代价", "适用判断"], tradeoffs, aligns=["<", ">", ">", "<"])

        out.subsection("关键数字")
        out.kv("参数量", f"{params['total']:,}")
        out.kv("fp64 → INT8 体积", f"{params['mib']:.2f} MiB → {int8['storage_bytes'] / 1024 ** 2:.2f} MiB"
               f"（{int8['compression_ratio']:.2f}×）")
        out.kv("INT8 / INT4 ΔPPL", f"{int8['ppl_delta_pct']:+.2f}% / {int4['ppl_delta_pct']:+.2f}%")
        out.kv("KV Cache 每 token（fp16）", f"{rows_holder['bytes_per_token_fp16']} B")
        out.kv("KV Cache 加速比", f"{bench['speedup']:.2f}×（误差 {bench['max_logit_error']:.1e}）")
        out.kv("一句话结论", "优化必须同时报收益和代价；只报压缩比的优化方案不可信")


if __name__ == "__main__":
    main()
