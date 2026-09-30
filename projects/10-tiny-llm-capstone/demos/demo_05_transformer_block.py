#!/usr/bin/env python
"""M05 · Transformer Block：结构、多头拆分，以及**因果性必须被证明**。

因果掩码是最容易写错又最难发现的一处：写错了模型照样能训、loss 照样会降，
只是它在偷偷看答案 —— 验证集上的所有数字都会变得好看且毫无意义。
所以本章把「改未来、看过去」做成一条硬性自检。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.model import build_model, forward_sanity, parameter_report, walk_parameters  # noqa: E402


def main() -> None:
    with Printer("demo_05_transformer_block") as out:
        out.section("M05 · Transformer Block：Pre-LN + 残差 + FFN，以及因果性自检")

        cfg = build_cfg()
        cfg, tokenizer, dataset, model, _report, _cache = ensure_bundle(cfg)

        out.subsection("1. 整机结构树")
        out.kv("Embedding + 位置编码", f"({model.vocab_size}, {model.d_model}) + ({model.max_len}, {model.d_model})")
        out.kv("DecoderStack 层数", len(model.decoder.blocks))
        block = model.decoder.blocks[0]
        out.kv("Block 组成", "ln1 → MultiHeadAttention → 残差 → ln2 → FFN → 残差")
        out.kv("注意力头数 / head_dim", f"{model.n_heads} / {model.d_model // model.n_heads}")
        out.kv("FFN 升维", f"{model.d_model} → {model.d_ff} → {model.d_model}")
        out.kv("输出投影", f"({model.d_model}, {model.vocab_size})")
        out.kv("最终 LayerNorm", "decoder.ln_f")

        out.subsection("2. 单 Block 的参数账")
        named = dict(walk_parameters(model))
        per_block = {name: p for name, p in named.items() if name.startswith("decoder.blocks.0.")}
        groups: dict[str, int] = {}
        for name, param in per_block.items():
            key = "attention" if ".attn." in name else ("ffn" if ".ffn." in name else "layernorm")
            groups[key] = groups.get(key, 0) + int(param.data.size)
        out.table(
            ["子层", "参数量", "占比"],
            [[key, f"{count:,}", f"{count / sum(groups.values()) * 100:.1f}%"]
             for key, count in sorted(groups.items(), key=lambda kv: -kv[1])],
            aligns=["<", ">", ">"],
        )
        out.kv("单 Block 合计", f"{sum(groups.values()):,}")
        out.kv("全部 Block 合计", f"{sum(groups.values()) * len(model.decoder.blocks):,}")
        out.kv("张量明细（第 0 层）", ", ".join(sorted(per_block)[:4]) + ", ...")

        out.subsection("3. 多头拆分：把 d_model 切成 h 份")
        rng = np.random.default_rng(0)
        x = rng.normal(size=(2, 8, model.d_model))
        head_dim = model.d_model // model.n_heads
        split = x.reshape(2, 8, model.n_heads, head_dim).transpose(0, 2, 1, 3)
        out.kv("输入形状", tuple(x.shape), "(B, T, d_model)")
        out.kv("分头后形状", tuple(split.shape), "(B, h, T, d/h)")
        merged = split.transpose(0, 2, 1, 3).reshape(2, 8, model.d_model)
        out.kv("拼回去是否还原", f"{np.max(np.abs(merged - x)):.3e}")

        out.subsection("4. 因果性自检（改未来 → 过去必须逐位不变）")
        sanity = forward_sanity(model, seq_len=16, batch=2, seed=0)
        out.kv("logits 形状", sanity["shape"])
        out.kv("形状正确 / 数值有限", f"{sanity['shape_ok']} / {sanity['finite']}")
        out.kv("改未来后：过去位置最大绝对误差", f"{sanity['causal_past_max_error']:.3e}", "必须为 0")
        out.kv("改未来后：未来位置最大绝对误差", f"{sanity['causal_future_max_error']:.3e}", "必须 > 0")
        out.kv("同输入两次前向最大绝对误差", f"{sanity['determinism_max_error']:.3e}")
        out.kv("三项自检是否全部通过", sanity["passed"])

        out.subsection("5. 因果掩码反例：把掩码去掉会发生什么")
        from model.decoder import DecoderStack  # noqa: PLC0415

        ids = rng.integers(0, model.vocab_size, size=(1, 8)).astype(np.int64)
        causal = model(ids, mask=None).data
        no_mask = np.zeros((8, 8))  # 全 0 = 谁都能看谁
        leaked = model(ids, mask=no_mask).data
        out.kv("带因果掩码 vs 不带掩码，最后一位 logits 最大差",
               f"{np.max(np.abs(causal[0, -1] - leaked[0, -1])):.4f}")
        out.kv("带掩码 / 不带掩码 的 argmax", f"{int(np.argmax(causal[0, -1]))} / {int(np.argmax(leaked[0, -1]))}")
        out.kv("结论", "掩码一旦失效，预测下一个 token 就变成了作弊，指标会虚高")

        out.subsection("6. 层数对照：深度换来的参数与耗时")
        rows = []
        for layers in (1, 2, 4):
            probe_cfg = build_cfg(model__n_layers=layers)
            probe = build_model(probe_cfg, tokenizer)
            params = parameter_report(probe)["total"]
            batch_x = rng.integers(0, model.vocab_size, size=(4, 32)).astype(np.int64)
            probe(batch_x, mask=None)  # 预热
            started = time.perf_counter()
            for _ in range(5):
                probe(batch_x, mask=None)
            per_step = (time.perf_counter() - started) / 5 * 1000
            rows.append([layers, f"{params:,}", f"{per_step:.2f} ms"])
        out.table(["n_layers", "参数量", "前向耗时 (4×32)"], rows, aligns=[">", ">", ">"])
        out.kv("当前配置", f"n_layers={cfg.model.n_layers}")

        out.subsection("关键数字")
        out.kv("结构", f"{len(model.decoder.blocks)} 层 × (4 头 × d_model {model.d_model})，d_ff={model.d_ff}")
        out.kv("单 Block 参数", f"{sum(groups.values()):,}（注意力 {groups['attention']:,} / FFN {groups['ffn']:,}）")
        out.kv("因果性", f"过去位置误差 {sanity['causal_past_max_error']:.3e}（=0），未来位置误差 > 0")
        out.kv("确定性", f"两次前向误差 {sanity['determinism_max_error']:.3e}")


if __name__ == "__main__":
    main()
