"""Milestone 11 —— 完整 AI Engineer System：一条命令，跑完整条链路。

前面十章各交付一块能力，但真实工程里最值钱的是**把它们串成一条可重复执行的
流水线**：换一份语料、改一个超参，敲一行命令就能拿到「训练报告 + 评估报告 +
优化账本 + 服务压测」四份结果，而且**结果可复现**。

本模块就是那条流水线。三条工程原则：

1. **一切产物可缓存**：分词器、模型权重、检查点都落在 ``models/`` 下，
   存在就复用，不存在才重算。这样九次 demo 运行共用同一份模型，
   跨章节的数字才对得上（P08 缓存基座是同一个道理）。
2. **每一步都可单独重跑**：``steps`` 参数能指定只跑某几步，
   排查问题时不用每次从头训。
3. **配置即产物**：``models/config.json`` 一定会留一份，
   报告里每个数字都能追溯到是哪份配置跑出来的。

用法::

    python -m tiny.pipeline                 # 跑完整链路（有缓存就复用）
    python -m tiny.pipeline --force         # 忽略缓存，从头重训
    python -m tiny.pipeline --steps 800     # 覆盖训练步数
    python -m tiny.pipeline --no-serve      # 跳过起服务（纯离线）
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import TinyConfig, default_config, resolve_vocab_size
from .data import build_dataset, dataset_report, load_corpus
from .infer import Generator
from .model import build_model, build_optimizer, parameter_report, set_seed
from .paths import P10_MODELS, ensure_dir, ensure_models_dir
from .tok import ensure_tokenizer

__all__ = ["Artifacts", "STAGES", "run_pipeline", "main"]

STAGES = ["config", "tokenizer", "dataset", "model", "train", "evaluate", "optimize", "serve"]

CONFIG_JSON = P10_MODELS / "config.json"
TOKENIZER_JSON = P10_MODELS / "tokenizer.json"
MODEL_NPZ = P10_MODELS / "tiny_lm.npz"
BEST_NPZ = P10_MODELS / "tiny_lm_best.npz"
REPORT_JSON = P10_MODELS / "report.json"


@dataclass
class Artifacts:
    """流水线跑完留下的全部东西。"""

    cfg: TinyConfig
    tokenizer: object = None
    dataset: object = None
    model: object = None
    generator: object = None
    train_report: dict = field(default_factory=dict)
    eval_report: dict = field(default_factory=dict)
    opt_report: dict = field(default_factory=dict)
    serve_report: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    cached: dict = field(default_factory=dict)


def _stage(result: Artifacts, name: str, fn):
    started = time.perf_counter()
    value = fn()
    result.timings[name] = time.perf_counter() - started
    return value


def run_pipeline(
    cfg: "TinyConfig | None" = None,
    *,
    force: bool = False,
    steps: "int | None" = None,
    verbose: bool = True,
    do_serve: bool = True,
    corpus: "list[str] | None" = None,
    only: "list[str] | None" = None,
) -> Artifacts:
    """跑完整的 Tiny LLM 工程链路。

    ``only`` 用来只跑指定阶段（调试用），``force=True`` 忽略所有缓存。
    """
    cfg = (cfg or default_config()).validate()
    if steps is not None:
        cfg.train.n_steps = int(steps)
    ensure_models_dir()
    result = Artifacts(cfg=cfg)

    def want(stage: str) -> bool:
        return only is None or stage in only

    # ------------------------------------------------------------ 1 配置
    cfg.save(CONFIG_JSON)
    result.timings["config"] = 0.0
    if verbose:
        print("[1/8] 配置")
        for line in cfg.summary_lines():
            print("      " + line)

    # ------------------------------------------------------------ 2 分词器
    raw_corpus = corpus if corpus is not None else load_corpus(cfg)
    if want("tokenizer"):
        from .data import clean_lines, split_lines

        kept, _ = clean_lines(raw_corpus, cfg.data.min_chars, cfg.data.dedup)
        train_lines, _val = split_lines(kept, cfg.data.val_ratio, cfg.data.seed)
        if force:
            from .tok import build_tokenizer, save_tokenizer

            tokenizer = build_tokenizer(cfg, train_lines)
            save_tokenizer(tokenizer, TOKENIZER_JSON)
            result.cached["tokenizer"] = False
        else:
            tokenizer, trained = ensure_tokenizer(cfg, train_lines, TOKENIZER_JSON)
            result.cached["tokenizer"] = not trained
        result.tokenizer = tokenizer
        if verbose:
            print(f"[2/8] 分词器  vocab={tokenizer.vocab_size}  缓存命中={result.cached['tokenizer']}")

    # ------------------------------------------------------------ 3 数据集
    if want("dataset"):
        result.dataset = _stage(
            result, "dataset", lambda: build_dataset(cfg, result.tokenizer, raw_corpus)
        )
        if verbose:
            meta = dataset_report(result.dataset)
            print(
                f"[3/8] 数据集  train={meta['train_examples']}  val={meta['val_examples']}"
                f"  泄漏={meta['leakage']['overlap']}"
            )

    # ------------------------------------------------------------ 4 模型
    if want("model"):
        resolve_vocab_size(cfg, result.tokenizer)
        set_seed(cfg.seed)
        result.model = _stage(result, "model", lambda: build_model(cfg, result.tokenizer))
        params = parameter_report(result.model)
        if verbose:
            print(
                f"[4/8] 模型    {params['total']:,} 参数  "
                f"{params['mib']:.2f} MiB(fp64)  张量={params['n_tensors']}"
            )

    # ------------------------------------------------------------ 5 训练
    if want("train"):
        from .model import walk_parameters
        from .train import LMTrainer, load_checkpoint, save_checkpoint

        optimizer = build_optimizer(cfg, result.model)
        trainer = LMTrainer(
            cfg, result.model, optimizer,
            result.dataset.train_examples, result.dataset.val_examples,
            verbose=verbose,
        )
        # 复用优先级：**最优检查点** > 最后一步检查点。
        # 为什么不是「哪个新用哪个」：早停回滚后的权重才是该上线的那个（M06/M07 都证明了
        # 它逐条优于训练终点），而 ``tiny_lm.npz`` 存的是**最后一步**——直接用它会让
        # M11 的评估数字和 M07 报告的对不上，跨章节就串不起来了。
        reuse_path = next(
            (path for path in (BEST_NPZ, MODEL_NPZ)
             if path.is_file() and path.with_suffix(".json").is_file()),
            None,
        )
        reused = False
        if not force and reuse_path is not None:
            info = load_checkpoint(result.model, reuse_path, optimizer=optimizer)
            reused = True
            result.train_report = {
                "reused_checkpoint": True,
                "from": reuse_path.name,
                "restored": info["restored"],
                "meta": info["meta"],
            }
        if not reused:
            result.train_report = _stage(
                result, "train",
                lambda: trainer.run(ckpt_path=MODEL_NPZ, best_ckpt_path=BEST_NPZ),
            )
            result.train_report["reused_checkpoint"] = False
        result.cached["model"] = reused
        if verbose:
            if reused:
                print(f"[5/8] 训练    复用检查点 {reuse_path.name}"
                      f"（step={result.train_report['meta'].get('step')}）")
            else:
                tr = result.train_report
                print(
                    f"[5/8] 训练    loss {tr['first_loss']:.4f} → {tr['last_loss']:.4f}"
                    f"  val_ppl {tr['best_val_perplexity']:.2f}  {tr['wall_seconds']:.1f}s"
                )

    # ------------------------------------------------------------ 6 评估
    if want("evaluate"):
        from .evaluate import evaluate_model

        result.generator = Generator(result.model, result.tokenizer, cfg)

        def _eval():
            return evaluate_model(
                cfg,
                result.model,
                result.dataset.val_examples,
                result.dataset.val_lines,
                generate_fn=lambda p: result.generator.generate(
                    p, max_new_tokens=cfg.gen.max_new_tokens, temperature=0.0
                ),
            )

        result.eval_report = _stage(result, "evaluate", _eval)
        if verbose:
            e = result.eval_report
            print(f"[6/8] 评估    val_ppl={e['perplexity']:.2f}  token_acc={e['token_accuracy']:.4f}"
                  f"  ECE={e['ece']:.4f}")

    # ------------------------------------------------------------ 7 优化
    if want("optimize"):
        from .optimize import optimization_report

        result.opt_report = _stage(
            result, "optimize",
            lambda: optimization_report(
                cfg, result.model, result.dataset.val_examples, result.generator
            ),
        )
        if verbose:
            q = result.opt_report["quantization"]["quantizers"]
            line = "  ".join(f"{k}: 压缩{v['compression_ratio']:.2f}×/ppl{v['ppl_delta_pct']:+.2f}%"
                             for k, v in q.items())
            print(f"[7/8] 优化    {line}")

    # ------------------------------------------------------------ 8 服务
    if want("serve") and do_serve:
        from .serve import ServingSession, load_test, smoke_test

        prompts = [
            "问：什么是 LoRA？答：",
            "问：什么是 KV Cache？答：",
            "问：什么是幻觉？答：",
            "问：什么是早停？答：",
        ]

        def _serve():
            with ServingSession(cfg, result.model, result.tokenizer) as session:
                smoke = smoke_test(session.url, prompts[0], max_tokens=cfg.serve.max_tokens)
                load = load_test(
                    session.url, prompts,
                    concurrency=cfg.serve.concurrency, max_tokens=cfg.serve.max_tokens,
                )
                return {"url": session.url, "smoke": smoke, "load": load}

        result.serve_report = _stage(result, "serve", _serve)
        if verbose:
            s = result.serve_report
            print(
                f"[8/8] 服务    {s['url']}  冒烟通过={s['smoke']['passed']}"
                f"  并发 {s['load']['requests']} 请求 {s['load']['wall_ms']:.0f}ms"
                f"  吞吐 {s['load']['requests_per_sec']:.2f} req/s"
            )

    # ------------------------------------------------------------ 报告落盘
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(_serializable(result), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def _serializable(result: Artifacts) -> dict:
    """把报告里不能 JSON 化的东西（ndarray / tuple）降维成基本类型。"""

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value]
        if isinstance(value, np.ndarray):
            return clean(value.tolist())
        if isinstance(value, (np.floating, np.integer)):
            return float(value)
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value

    return clean(
        {
            "config": result.cfg.to_dict(),
            "timings": result.timings,
            "cached": result.cached,
            "train": result.train_report,
            "evaluate": result.eval_report,
            "optimize": result.opt_report,
            "serve": result.serve_report,
        }
    )


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tiny.pipeline",
        description="Project 10 —— Tiny LLM 全链路：Tokenizer → Dataset → Model → "
                    "Training → Evaluation → Inference → Optimization → Serving",
    )
    parser.add_argument("--steps", type=int, default=None, help="覆盖训练步数")
    parser.add_argument("--force", action="store_true", help="忽略缓存，从头重跑")
    parser.add_argument("--no-serve", action="store_true", help="跳过服务化阶段")
    parser.add_argument("--only", type=str, default=None,
                        help="只跑指定阶段，逗号分隔：" + ",".join(STAGES))
    parser.add_argument("--quiet", action="store_true", help="减少过程输出")
    args = parser.parse_args(argv)

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    result = run_pipeline(
        steps=args.steps,
        force=args.force,
        verbose=not args.quiet,
        do_serve=not args.no_serve,
        only=only,
    )
    print()
    print("── 关键数字 " + "─" * 40)
    if result.train_report and not result.train_report.get("reused_checkpoint"):
        tr = result.train_report
        print(f"  训练 loss            {tr['first_loss']:.4f} → {tr['last_loss']:.4f}")
        print(f"  验证困惑度           {tr['best_val_perplexity']:.2f}（第 {tr['best_step']} 步最优）")
    if result.eval_report:
        e = result.eval_report
        print(f"  评估 token 准确率    {e['token_accuracy']:.4f}   ECE={e['ece']:.4f}")
    if result.opt_report:
        q = result.opt_report["quantization"]["quantizers"]
        for name, item in q.items():
            print(f"  {name:<16} 压缩 {item['compression_ratio']:.2f}×"
                  f"   困惑度 {item['ppl_delta_pct']:+.2f}%")
    if result.serve_report:
        load = result.serve_report["load"]
        print(f"  服务并发             {load['requests']} 请求 / {load['concurrency']} 并发"
              f"   成功率 {load['success']}/{load['requests']}")
    print(f"  总耗时               {sum(result.timings.values()):.1f}s")
    print(f"  报告已写入           {REPORT_JSON}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
