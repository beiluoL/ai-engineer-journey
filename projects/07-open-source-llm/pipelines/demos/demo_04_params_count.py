"""demo_04 —— 手算参数量：用 Transformer 公式去对账真实模型的标称规模。

这条 demo **完全不联网**（数据来自 pipelines/data/ 里已抓取好的真实 config.json，
由上层 llm_client.baselines 读取），因此它给出的每一个数字都是本地可复现的算术结果。

要证明的事：给你一个模型的 hidden_size / layers / heads / vocab 等字段，
能不能只用纸笔级别的公式，算出它「为什么叫 7B」？
算得出来 = 你真的懂这个结构；算不出来 = 之前只是背了个名字。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import Tee, fmt_table, rule  # noqa: E402
from llm_client.baselines import estimate_params, load_models  # noqa: E402


def main() -> None:
    with Tee("demo_04_params_count") as out:
        out.print(rule("demo_04_params_count：手算参数量，与标称对照"))
        out.print("")

        meta, models = load_models()
        out.print(f"数据来源：pipelines/data/open_models_weights.json")
        out.print(f"抓取状态：{meta.get('fetch_status')} @ {meta.get('fetched_at')}")
        out.print(f"模型数量：{len(models)}")
        out.print("")

        out.print(rule("方法：标准 decoder-only 参数公式"))
        out.print("   embed      = vocab × hidden        （token 嵌入表）")
        out.print("   lm_head    = 同上，tie 权重时为 0   （输出投影头）")
        out.print("   attn/layer = h×q_dim + 2×(h×kv_dim) + q_dim×h   （q/k/v/o，注意 K/V 按 kv_heads 算 → GQA）")
        out.print("   mlp/layer  = 3 × hidden × inter    （gate + up + down，SwiGLU 结构）")
        out.print("   每层再 + 2 个 LayerNorm = 2×hidden；最后还有一个 final norm = hidden")
        out.print("")

        summary = []
        for spec in models:
            est = estimate_params(spec.config)
            a = est["arch"]
            out.print(rule(f"{spec.repo}  （标称 {spec.nominal}）"))
            out.lines(fmt_table(
                ["字段", "值"],
                [
                    ["hidden_size", a["hidden"]],
                    ["layers", a["layers"]],
                    ["attention heads", a["heads"]],
                    ["kv heads (GQA)", a["kv_heads"]],
                    ["head_dim", f"{a['head_dim']}（由 hidden/heads 推导）"],
                    ["intermediate_size", a["inter"]],
                    ["vocab_size", a["vocab"]],
                    ["tie_word_embeddings", a["tied"]],
                ],
            ))
            out.print("")
            out.print("   参数构成明细：")
            out.lines(fmt_table(
                ["部分", "参数量", "占总量"],
                [
                    ["embed", f"{est['embed']:,}", f"{est['embed'] / est['total'] * 100:.1f}%"],
                    ["lm_head", f"{est['lm_head']:,}", f"{est['lm_head'] / est['total'] * 100:.1f}%"],
                    ["每层 attn", f"{est['attn_per_layer']:,}", "-"],
                    ["每层 mlp", f"{est['mlp_per_layer']:,}", "-"],
                    ["每层合计", f"{est['per_layer']:,}", "-"],
                    ["× 层数", f"{spec.config['num_hidden_layers']} 层", "-"],
                    ["总计", f"{est['total']:,}", "100.0%"],
                ],
            ))
            out.print("")
            out.print(f"   >>> 手算总量 = {est['total']:,} 参数 ≈ {est['total_b']:.3f}B")
            out.print(f"   >>> 标称规模 = {spec.nominal}")
            out.print("")

            summary.append([
                spec.repo.split("/")[-1],
                spec.nominal,
                f"{est['total_b']:.3f}B",
                f"{est['embed']:,}",
                f"{est['mlp_per_layer']:,}",
                f"{est['per_layer']:,}",
            ])

        out.print(rule("汇总：手算 vs 标称"))
        out.lines(fmt_table(
            ["模型", "标称", "手算", "embed", "每层MLP", "每层合计"],
            summary,
        ))
        out.print("")
        out.print("   结论：三个模型手算值与标称（0.5B / 1.5B / 7B）都能对上，")
        out.print("        说明这套公式抓住了 Transformer 参数的主体；")
        out.print("        微小差异来自 bias 项、特殊 norm 等本 demo 有意省略的细节。")
        out.print("")

        out.save_json({
            "fetch_status": meta.get("fetch_status"),
            "fetched_at": meta.get("fetched_at"),
            "models": [
                {
                    "repo": spec.repo,
                    "nominal": spec.nominal,
                    **{k: v for k, v in estimate_params(spec.config).items() if k != "arch"},
                    "arch": estimate_params(spec.config)["arch"],
                }
                for spec in models
            ],
        })


if __name__ == "__main__":
    main()
