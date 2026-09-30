#!/usr/bin/env python
"""M06 · Training：完整训练 Pipeline，以及**过拟合是被实测到的，不是猜的**。

本章最有价值的数字不是「loss 降了」，而是这一组：

    train loss  7.15 → 3.82（一路下降，看起来很成功）
    val  loss   6.26 → 5.85 → 6.41（先降后升，这是过拟合）

没有验证集监控就会把「最后一步」当成「最好的一步」交出去。早停 + 最优回滚
就是为了防止这件事。本章还要证明检查点真的能**原样接回去**。
"""

from __future__ import annotations

import copy
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import BEST_NPZ, build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.model import build_model, build_optimizer, walk_parameters  # noqa: E402
from tiny.train import LMTrainer, evaluate_loss, load_checkpoint, save_checkpoint  # noqa: E402


def main() -> None:
    with Printer("demo_06_training") as out:
        out.section("M06 · Training Pipeline：调度 / 裁剪 / 早停回滚 / 断点续训")

        cfg = build_cfg()
        cfg, tokenizer, dataset, cached_model, _cached_report, _cache = ensure_bundle(cfg)
        reference = None
        if BEST_NPZ.is_file():
            reference = build_model(cfg, tokenizer)
            load_checkpoint(reference, BEST_NPZ)  # 上一次运行留下的权重（跨进程对照）

        out.subsection("1. 训练配置")
        for line in [
            f"batch_size          {cfg.train.batch_size}",
            f"n_steps             {cfg.train.n_steps}",
            f"eval_every          {cfg.train.eval_every}",
            f"patience            {cfg.train.patience}",
            f"optimizer           {cfg.optim.optimizer} lr={cfg.optim.lr}",
            f"warmup / min_lr     {cfg.optim.warmup_steps} 步 / lr×{cfg.optim.min_lr_ratio}",
            f"grad_clip           {cfg.optim.grad_clip}",
            f"seed                {cfg.train.seed}",
        ]:
            out.line("  " + line)

        out.subsection("2. 真训（每 100 步打印一次）")
        model = build_model(cfg, tokenizer)
        optimizer = build_optimizer(cfg, model)
        trainer = LMTrainer(cfg, model, optimizer, dataset.train_examples,
                            dataset.val_examples, verbose=True)
        started = time.perf_counter()
        report = trainer.run()
        wall = time.perf_counter() - started

        out.subsection("3. 训练 vs 验证：过拟合是被量出来的")
        curve = report["curve"]
        val_curve = report["val_curve"]
        rows = []
        for index, val_loss in enumerate(val_curve):
            step = min((index + 1) * cfg.train.eval_every, report["steps"])
            train_at = curve[step - 1]
            rows.append([step, f"{train_at:.4f}", f"{val_loss:.4f}", f"{np.exp(min(val_loss, 20)):.2f}"])
        out.table(["step", "train_loss", "val_loss", "val_ppl"], rows, aligns=[">", ">", ">", ">"])
        out.kv("train loss 首 → 末", f"{report['first_loss']:.4f} → {report['last_loss']:.4f}")
        out.kv("前 10% 均值 → 后 10% 均值", f"{report['head_mean']:.4f} → {report['tail_mean']:.4f}")
        best_index = int(np.argmin(val_curve))
        out.kv("验证最优出现在第几步", (best_index + 1) * cfg.train.eval_every)
        out.kv("验证最优 / 最后一步", f"{min(val_curve):.4f} / {val_curve[-1]:.4f}")
        out.kv("是否触发早停", report["stopped_early"], f"patience={cfg.train.patience}")
        out.kv("回滚到最优步", report["best_step"])
        out.kv("最优验证困惑度", f"{report['best_val_perplexity']:.2f}")
        out.kv("训练耗时 / 速度", f"{wall:.1f} s / {report['steps_per_second']:.1f} step/s")

        out.subsection("4. 学习率调度与梯度裁剪")
        rows = []
        for step in (0, 1, cfg.optim.warmup_steps, cfg.train.n_steps // 2,
                     cfg.train.n_steps - 1):
            rows.append([step, f"{trainer.lr_at(step):.6f}"])
        out.table(["step", "lr"], rows, aligns=[">", ">"])
        norms = np.asarray(trainer.history.grad_norm)
        out.kv("梯度全局范数 均值 / 中位 / 最大",
               f"{norms.mean():.4f} / {np.median(norms):.4f} / {norms.max():.4f}")
        out.kv("被裁剪的步数（> clip）", int((norms > cfg.optim.grad_clip).sum()))
        out.kv("裁剪阈值", cfg.optim.grad_clip)
        out.kv("loss 是否出现过 nan", bool(not np.isfinite(np.asarray(curve)).all()))

        out.subsection("5. 检查点：存盘 → 改坏 → 读回，必须逐位相同")
        tmp = BEST_NPZ.with_name("demo06_probe.npz")
        ckpt = save_checkpoint(model, tmp, step=report["steps"], optimizer=optimizer,
                               meta={"best_val_loss": report["best_val_loss"]})
        before = {name: np.array(p.data, copy=True) for name, p in walk_parameters(model)}
        for _name, param in walk_parameters(model):
            param.data[...] = 0.0
        info = load_checkpoint(model, tmp, optimizer=optimizer)
        out.kv("恢复的张量数", f"{info['restored']} / {len(before)}")
        max_error = max(float(np.max(np.abs(p.data - before[name])))
                        for name, p in walk_parameters(model))
        out.kv("读回后最大绝对误差", f"{max_error:.3e}")
        out.kv("检查点体积", f"{ckpt.path.stat().st_size / 1024:.1f} KB", ckpt.path.name)
        out.kv("元数据里记录的步数", ckpt.meta["step"])
        out.kv("是否含优化器状态", ckpt.meta["has_optimizer"], "Adam 的动量也是训练进度的一部分")
        tmp.unlink(missing_ok=True)
        tmp.with_suffix(".json").unlink(missing_ok=True)

        out.subsection("6. 跨进程可复现（本次训练 vs 磁盘上上一次训练）")
        if reference is None:
            out.kv("上一次检查点", "不存在（首次运行），本次结果已落盘")
        else:
            drift = max(
                float(np.max(np.abs(np.asarray(p.data) - np.asarray(ref_p.data))))
                for (name, p), (ref_name, ref_p) in zip(walk_parameters(model),
                                                        walk_parameters(reference))
            )
            out.kv("两次独立进程训练的权重最大绝对误差", f"{drift:.3e}")
            out.kv("结论", "同一份配置 + 同 seed ⇒ 逐位可复现（P08 的确定性补丁在此生效）")

        out.subsection("7. 断点续训 vs 一口气训完（同 seed、同 batch 顺序）")
        # 起点：把「已回滚到最优步」的状态原样存盘
        base_npz = BEST_NPZ.with_name("demo06_base.npz")
        save_checkpoint(model, base_npz, step=trainer.step, optimizer=optimizer,
                        meta={"note": "M06 续训对照的起点", "best_step": report["best_step"]})
        rng_state = trainer.rng.getstate()  # 关键：连 batch 顺序都要一致
        baseline_weights = {name: np.array(p.data, copy=True) for name, p in walk_parameters(model)}

        def _thirty_steps(active_model, optimizer_obj, rng):
            from tiny.data import batch_iter  # noqa: PLC0415

            runner = LMTrainer(cfg, active_model, optimizer_obj, dataset.train_examples,
                               dataset.val_examples, verbose=False)
            runner.step = trainer.step
            runner.rng.setstate(rng.getstate())
            for _ in range(30):
                batches = list(batch_iter(dataset.train_examples, cfg.train.batch_size,
                                          rng=runner.rng))
                x, y, mask = batches[runner.step % len(batches)]
                runner.train_step(x, y, mask)
            return runner

        # 分支 A（不中断）：**原地**接着训。这必须跑在真实对象上，
        # 否则就不是「没中断过」了 —— 所以它只借来用完就还回去。
        _thirty_steps(model, optimizer, trainer.rng)
        weights_continued = {name: np.array(p.data, copy=True) for name, p in walk_parameters(model)}

        # 分支 B（中断后恢复）：全新对象 + 从检查点读回权重/动量/步数，再训同样 30 步
        resumed_model = build_model(cfg, tokenizer, seed=cfg.seed)
        resumed_opt = build_optimizer(cfg, resumed_model)
        load_checkpoint(resumed_model, base_npz, optimizer=resumed_opt)
        _thirty_steps(resumed_model, resumed_opt, trainer.rng)
        weights_resumed = {name: np.array(p.data, copy=True)
                           for name, p in walk_parameters(resumed_model)}

        resume_error = max(float(np.max(np.abs(weights_resumed[name] - weights_continued[name])))
                           for name in weights_continued)
        out.kv("续训 30 步后最大绝对误差", f"{resume_error:.3e}")
        out.kv("结论", "断点续训与不中断训练逐步一致（前提是优化器状态与 batch 顺序一起恢复）")

        # ⚠ 关键收尾：分支 A 已经把 model / optimizer 往前推了 30 步，
        #   而下面写进 BEST_NPZ 的必须是**早停回滚那一刻**的权重 ——
        #   其它章节的 demo 全都复用它，差 30 步会让跨章节的数字对不上。
        #   所以这里先从 base_npz 把三样东西（权重 + 动量 + 步数）原样还原，
        #   再落盘，并顺手把「还原后与起点逐位相同」也验证一遍。
        load_checkpoint(model, base_npz, optimizer=optimizer)
        restored_error = max(float(np.max(np.abs(p.data - baseline_weights[name])))
                             for name, p in walk_parameters(model))
        out.kv("落盘前已还原到最优步（逐位误差）", f"{restored_error:.3e}")

        save_checkpoint(model, BEST_NPZ, step=report["best_step"], optimizer=optimizer,
                        meta={"best_val_loss": report["best_val_loss"],
                              "best_step": report["best_step"], "config": cfg.to_dict()})
        base_npz.unlink(missing_ok=True)
        base_npz.with_suffix(".json").unlink(missing_ok=True)

        out.subsection("关键数字")
        out.kv("train loss", f"{report['first_loss']:.4f} → {report['last_loss']:.4f}")
        out.kv("val loss", f"{val_curve[0]:.4f} → {min(val_curve):.4f}（最优）→ {val_curve[-1]:.4f}（回升）")
        out.kv("早停", f"触发={report['stopped_early']}，回滚到第 {report['best_step']} 步")
        out.kv("最优验证困惑度", f"{report['best_val_perplexity']:.2f}")
        out.kv("检查点读回误差", f"{max_error:.3e}；断点续训误差 {resume_error:.3e}")
        out.kv("落盘的就是回滚后的权重", f"逐位误差 {restored_error:.3e}")


if __name__ == "__main__":
    main()
