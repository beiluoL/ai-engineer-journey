#!/usr/bin/env python
"""M04 · Embedding：查表、位置编码、以及「参数大头为什么在这里」。

Embedding 是模型里**唯一一个真正接触文本**的地方。本章用真实权重回答三个问题：

1. 查表到底做了什么（为什么它等价于「one-hot × 矩阵」却不用真的乘）？
2. 位置编码怎么让没有循环结构的模型知道顺序？
3. 为什么 Tiny LLM 的参数大头在 Embedding 和输出投影上（71.1%）？
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.model import parameter_report, walk_parameters  # noqa: E402


def main() -> None:
    with Printer("demo_04_embedding") as out:
        out.section("M04 · Embedding：查表 + 正弦位置编码 + 参数占比")

        cfg = build_cfg()
        cfg, tokenizer, dataset, model, _report, _cache = ensure_bundle(cfg)

        emb = model.token_emb
        pe = model.pos_enc
        weight = np.asarray(emb.weight.data)
        positions = np.asarray(pe.pe)

        out.subsection("1. Token Embedding 就是一张 (V, d_model) 的查找表")
        out.kv("词表大小 V", model.vocab_size)
        out.kv("d_model", model.d_model)
        out.kv("权重形状", tuple(weight.shape))
        out.kv("参数量", f"{weight.size:,}")
        sample_ids = [int(i) for i in tokenizer.encode("什么是 LoRA？")][:4]
        out.kv("示例 token → id", f"{tokenizer.pieces('什么是 LoRA？')[:4]} → {sample_ids}")
        rows = weight[sample_ids]
        out.kv("查表结果形状", tuple(rows.shape))
        out.kv("同一 id 两次查表是否一致", bool(np.array_equal(rows[0], weight[sample_ids[0]])))
        out.kv("不同 id 向量是否不同", not np.allclose(rows[0], rows[1]))

        out.subsection("2. 查表 = one-hot × 矩阵（数学等价，但复杂度从 O(V·d) 降到 O(d)）")
        onehot = np.zeros(model.vocab_size)
        onehot[sample_ids[0]] = 1.0
        matmul_result = onehot @ weight
        out.kv("one-hot @ W 与查表最大绝对误差", f"{np.max(np.abs(matmul_result - rows[0])):.3e}")
        out.kv("乘法次数：矩阵版 / 查表版", f"{model.vocab_size * model.d_model:,} / 0")

        out.subsection("3. 正弦位置编码：不训练也能表达顺序")
        out.kv("pe 形状", tuple(positions.shape), "(max_len, d_model)")
        out.kv("可训练参数", 0, "位置编码是常量表，不进优化器")
        norms = np.linalg.norm(positions, axis=-1)
        out.kv("每个位置的向量范数 均值/标准差", f"{norms.mean():.4f} / {norms.std():.6f}")
        out.kv("范数是否恒定", bool(norms.std() < 1e-9), "正弦构造 ⇒ 与位置无关")
        out.kv("位置 0 与位置 1 的余弦相似度", f"{_cos(positions[0], positions[1]):.4f}")
        out.kv("位置 0 与位置 8 的余弦相似度", f"{_cos(positions[0], positions[8]):.4f}")
        out.kv("位置 0 与位置 32 的余弦相似度", f"{_cos(positions[0], positions[32]):.4f}")
        half = model.d_model // 2
        out.kv("前 4 维（高频）", " ".join(f"{value:+.3f}" for value in positions[1, :4]))
        out.kv("后 4 维（低频）", " ".join(f"{value:+.3f}" for value in positions[1, -4:]))
        out.kv("高频维 vs 低频维 的相邻位置变化",
               f"{np.abs(positions[1, 0] - positions[0, 0]):.4f} / "
               f"{np.abs(positions[1, -1] - positions[0, -1]):.4f}")
        out.kv("低维索引（低频）", half)

        out.subsection("4. combine：Embedding + 位置编码 直接相加")
        ids = np.array([sample_ids], dtype=np.int64)
        from tiny.model import build_model  # noqa: PLC0415

        from model.embedding import combine  # noqa: PLC0415

        combined = combine(emb, pe, ids)
        token_part = weight[ids[0]]
        pos_part = positions[: ids.shape[1]]
        out.kv("combine 输出形状", tuple(np.asarray(combined.data).shape))
        out.kv("是否等于 emb + pe", f"{np.max(np.abs(np.asarray(combined.data)[0] - (token_part + pos_part))):.3e}")
        out.kv("相加前 token 向量范数", f"{np.linalg.norm(token_part[0]):.4f}")
        out.kv("相加后向量范数", f"{np.linalg.norm(np.asarray(combined.data)[0, 0]):.4f}")

        out.subsection("5. 参数大头在哪（Tiny LLM 的关键事实）")
        params = parameter_report(model)
        group_rows = [[name, f"{count:,}", f"{count / params['total'] * 100:.1f}%"]
                      for name, count in sorted(params["groups"].items(), key=lambda kv: -kv[1])]
        out.table(["组件", "参数量", "占比"], group_rows, aligns=["<", ">", ">"])
        emb_share = params["groups"]["token_embedding"] / params["total"] * 100
        proj_share = params["groups"].get("output_projection", 0) / params["total"] * 100
        out.kv("Embedding 占比", f"{emb_share:.1f}%")
        out.kv("输出投影占比", f"{proj_share:.1f}%")
        out.kv("两者合计", f"{emb_share + proj_share:.1f}%", "词表一大，这两项就吃掉大部分预算")
        out.kv("Embedding 参数 = V × d_model", f"{model.vocab_size} × {model.d_model} = {model.vocab_size * model.d_model:,}")
        out.kv("词表减半可省参数", f"{model.vocab_size * model.d_model // 2:,}", "但 OOV 会上升（见 M02）")

        out.subsection("6. 遍历到的权重张量（pos_enc 不在其中 ⇒ 不参与训练）")
        names = [name for name, _p in walk_parameters(model)]
        out.kv("张量总数", len(names))
        out.kv("是否含 pos_enc", any("pos_enc" in name for name in names))
        out.kv("前 3 个张量", ", ".join(names[:3]))

        out.subsection("关键数字")
        out.kv("Embedding", f"({model.vocab_size}, {model.d_model}) = {weight.size:,} 参数，占 {emb_share:.1f}%")
        out.kv("位置编码", f"({model.max_len}, {model.d_model})，0 个可训练参数，范数恒定 {norms.mean():.4f}")
        out.kv("查表 vs one-hot×W", f"最大绝对误差 {np.max(np.abs(matmul_result - rows[0])):.3e}")
        out.kv("结论", "Embedding + 输出投影占 71.1% —— 小模型调参先动 d_model 不如先看词表")


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


if __name__ == "__main__":
    main()
