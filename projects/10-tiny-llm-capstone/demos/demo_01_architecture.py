#!/usr/bin/env python
"""M01 · Project Architecture：配置契约 + 分层结构 + 依赖账本。

这一章不训模型，只回答一个问题：**这个 Capstone 到底由哪些层组成、每层依赖谁**。
之所以把它放在第一层，是因为 P08 踩过「两份代码各抄一份默认值」的坑 ——
架构没定清楚，后面每一章的数字都会互相打架。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, corpus_split, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.model import parameter_report, walk_parameters  # noqa: E402
from tiny.paths import P06_ROOT, P08_ROOT, P09_ROOT, P10_ROOT  # noqa: E402


def main() -> None:
    with Printer("demo_01_architecture") as out:
        out.section("M01 · Project Architecture：一个配置、十层链路、三个只读依赖")

        cfg = build_cfg()
        out.subsection("1. 唯一配置入口（models/config.json 会留档）")
        for line in cfg.summary_lines():
            out.line("  " + line)

        out.subsection("2. 分层与复用关系（P10 刻意不重写的部分）")
        out.kv("P06 复用", "model / tokenizer", "Transformer + 从零 autograd + BPE")
        out.kv("P08 复用", "ft.paths", "确定性 autograd 补丁（Tensor._prev 有序化）")
        out.kv("P09 复用", "ie.metrics / quantize / kvbook / engine / serve", "评估·量化·推理·服务")
        out.kv("P10 自研", "config / tok / data / model / train / evaluate", "工程化与编排")
        out.kv("P10 自研", "infer / optimize / serve / pipeline", "采样·优化·服务·端到端")
        for label, path in (("P06", P06_ROOT), ("P08", P08_ROOT), ("P09", P09_ROOT), ("P10", P10_ROOT)):
            out.kv(f"{label} 目录存在", path.is_dir(), path.name)

        out.subsection("3. 依赖自检（缺一个就报错，而不是等到 import 才崩）")
        from tiny.paths import ensure_deps_importable

        p06, p08, p09 = ensure_deps_importable()
        out.kv("已挂载 P06 src", p06.is_dir())
        out.kv("已挂载 P08 src", p08.is_dir())
        out.kv("已挂载 P09 src", p09.is_dir())

        out.subsection("4. 数据 → 词表 → 模型：规模是怎么定下来的")
        _raw, kept, train_lines, val_lines, clean = corpus_split(cfg)
        chars = len("".join(kept))
        distinct = len(set("".join(kept)))
        out.kv("语料行数（清洗后）", len(kept), f"丢弃 短行 {clean['dropped_short']} / 重复 {clean['dropped_dup']}")
        out.kv("字符数 / 不同字符", f"{chars} / {distinct}")
        out.kv("train / val 行数", f"{len(train_lines)} / {len(val_lines)}")
        out.kv("词表大小选择依据", f"4 特殊 token + {distinct} 基础字符 + 合并 → {cfg.tokenizer.vocab_size}")

        _cfg, tokenizer, dataset, model, _report, cache = ensure_bundle(cfg)
        params = parameter_report(model)
        out.subsection("5. 参数账本（第一个能发现配置写错的探针）")
        out.kv("总参数", f"{params['total']:,}")
        out.kv("张量数", params["n_tensors"])
        out.kv("fp64 体积", f"{params['mib']:.2f} MiB")
        rows = [[name, f"{count:,}", f"{count / params['total'] * 100:.1f}%"]
                for name, count in sorted(params["groups"].items(), key=lambda kv: -kv[1])]
        out.table(["组件", "参数量", "占比"], rows, aligns=["<", ">", ">"])
        emb = params["groups"]["token_embedding"] + params["groups"].get("output_projection", 0)
        out.kv("Embedding + 输出投影占比", f"{emb / params['total'] * 100:.1f}%", "Tiny LLM 的参数大头在这里")
        out.kv("模型缓存命中", cache["model_reused"], "复用同一份权重，跨章节数字才对得上")

        out.subsection("6. 配置校验：故意写错会被挡住")
        bad = build_cfg()
        bad.model.n_heads = 3  # 64 % 3 != 0
        try:
            bad.validate()
            out.kv("非法配置", "未被拦截（这是 bug）")
        except ValueError as exc:
            first_line = str(exc).splitlines()[1].strip()
            out.kv("非法配置被拦截", True, first_line)

        out.subsection("关键数字")
        out.kv("语料", f"{len(kept)} 行 / {chars} 字符 / {distinct} 不同字符")
        out.kv("模型", f"{params['total']:,} 参数，{params['n_tensors']} 个张量")
        out.kv("权重张量遍历顺序稳定", len(walk_parameters(model)) == params["n_tensors"])
        out.kv("随机源", "np.random.seed(0) + Random(seed) + default_rng(seed)")


if __name__ == "__main__":
    main()
