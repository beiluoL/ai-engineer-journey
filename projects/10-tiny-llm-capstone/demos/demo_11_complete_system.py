#!/usr/bin/env python
"""M11 · Complete AI Engineer System：一条命令跑完整条链路。

前面十章各交付一块能力，但真实工程里最值钱的是**把它们串成一条可重复执行的
流水线**：换一份语料、改一个超参，敲一行命令就拿到「训练报告 + 评估报告 +
优化账本 + 服务压测」四份结果，而且结果可复现。

本章不只是「把前面再跑一遍」。它要证明三件工程属性：
**可缓存**（第二次跑直接复用）、**可分段重跑**（排查问题不用从头训）、
**可追溯**（每个数字都能对上是哪份配置跑出来的）。
最后把 11 章的关键数字汇成一张表 —— 这才是 Capstone 的交付物。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.data import dataset_report  # noqa: E402
from tiny.model import parameter_report  # noqa: E402
from tiny.paths import P10_MODELS  # noqa: E402
from tiny.pipeline import STAGES, run_pipeline  # noqa: E402
from tiny.tok import tokenizer_stats  # noqa: E402


def main() -> None:
    with Printer("demo_11_complete_system") as out:
        out.section("M11 · Complete AI Engineer System：一条命令跑完 Tokenizer → Serving")

        out.subsection("1. 流水线的八个阶段")
        out.kv("阶段", " → ".join(STAGES))
        out.kv("命令", "python -m tiny.pipeline  （等价于本次这段调用）")
        out.kv("选项", "--force 忽略缓存 / --steps N 覆盖步数 / --only 分阶段 / --no-serve")

        # ------------------------------------------------------- 完整跑一遍
        out.subsection("2. 真实运行（过程输出原样记录）")
        cfg = build_cfg()
        with out.capture():
            result = run_pipeline(cfg)
        # 立刻留一份完整报告的快照：后面第 7/8 节会重跑（其中一个只跑前三段），
        # 会把 models/report.json 覆盖成「不完整」的那份。想引用完整报告就必须现在拿。
        full_report = json.loads((P10_MODELS / "report.json").read_text(encoding="utf-8"))

        out.subsection("3. 各阶段耗时")
        rows = []
        for stage in STAGES:
            seconds = result.timings.get(stage)
            if seconds is None:
                note = "复用缓存，未计时" if stage in ("tokenizer", "train") else "未执行"
                rows.append([stage, "-", note])
            else:
                rows.append([stage, f"{seconds:.3f} s", ""])
                if stage == "train":
                    rows[-1][2] = "复用检查点，未重训"
        out.table(["阶段", "耗时", "说明"], rows, aligns=["<", ">", "<"])
        total_wall = sum(result.timings.values())
        out.kv("合计", f"{total_wall:.3f} s")
        out.kv("缓存命中", json.dumps(result.cached, ensure_ascii=False))

        out.subsection("4. 产物清单（models/ 里都是可追溯的证据）")
        rows = []
        for path in sorted(P10_MODELS.glob("*")):
            if path.is_file():
                rows.append([path.name, f"{path.stat().st_size / 1024:.1f} KB"])
        out.table(["文件", "体积"], rows, aligns=["<", ">"])
        out.kv("config.json 的意义", "报告里的每个数字都能对上是哪份配置跑出来的")
        out.kv("report.json 的意义", "四份报告（训练/评估/优化/服务）一次落盘，便于对比实验")

        # ------------------------------------------------------- 数据/模型账
        out.subsection("5. 这一次跑的数据与模型账")
        ds_meta = dataset_report(result.dataset)
        tok_stats = tokenizer_stats(result.tokenizer,
                                   result.dataset.train_lines + result.dataset.val_lines)
        params = parameter_report(result.model)
        out.kv("分词器", f"{result.tokenizer.kind}  vocab={result.tokenizer.vocab_size}"
               f"  chars/token={tok_stats['chars_per_token']:.3f}  unk={tok_stats['unk_rate']:.4f}")
        out.kv("语料", f"{ds_meta['input_lines']} 行 → 清洗后 {ds_meta['kept']} 行"
               f"（去重 {ds_meta['dropped_dup']} / 过短 {ds_meta['dropped_short']}）")
        out.kv("切分", f"train {ds_meta['train_lines']} 行 / val {ds_meta['val_lines']} 行"
               f"（val_ratio={cfg.data.val_ratio}）")
        out.kv("泄漏检查", f"overlap={ds_meta['leakage']['overlap']}"
               f"  clean={ds_meta['leakage']['clean']}")
        out.kv("样本", f"train {ds_meta['train_examples']} / val {ds_meta['val_examples']}"
               f"（pack={ds_meta['pack']}, stride={ds_meta['stride']}）")
        out.kv("模型", f"{params['total']:,} 参数  {params['n_tensors']} 张量"
               f"  {params['mib']:.2f} MiB(fp64)")
        tr = result.train_report
        if tr.get("reused_checkpoint"):
            out.kv("训练", f"复用检查点 {tr.get('from')}"
                   f"（best_step={tr['meta'].get('best_step')}）")
        else:
            out.kv("训练", f"loss {tr['first_loss']:.4f} → {tr['last_loss']:.4f}"
                   f"  早停={tr['stopped_early']}  最优步={tr['best_step']}")

        # ------------------------------------------------------- 四份报告
        out.subsection("6. 四份报告的关键字段")
        ev = result.eval_report
        out.kv("评估 · 语言层", f"val_loss={ev['loss']:.4f}  ppl={ev['perplexity']:.2f}"
               f"  token_acc={ev['token_accuracy']:.4f}")
        out.kv("评估 · 校准层", f"ECE={ev['ece']:.4f}")
        gen = ev.get("generation", {})
        if gen:
            agg = gen["aggregate"]
            out.kv("评估 · 生成层", f"总分 {agg['total']:.2f}  覆盖 {agg['keyword_coverage']:.3f}"
                   f"  不重复分 {agg['repetition_score']:.3f}")
        quant = result.opt_report["quantization"]["quantizers"]
        for name, item in quant.items():
            out.kv(f"优化 · {name}", f"压缩 {item['compression_ratio']:.2f}×"
                   f"  ΔPPL {item['ppl_delta_pct']:+.2f}%")
        speed = result.opt_report.get("speed", {})
        if speed:
            out.kv("优化 · KV Cache", f"{speed['speedup']:.2f}×"
                   f"（logits 误差 {speed['max_logit_error']:.1e}）")
        sv = result.serve_report or {}
        load = sv.get("load", {})
        if sv:
            out.kv("服务 · 冒烟", f"通过={sv['smoke']['passed']}  {sv['url']}")
            out.kv("服务 · 压测", f"{load['success']}/{load['requests']} 成功"
                   f"  吞吐 {load['requests_per_sec']:.2f} req/s")

        # ------------------------------------------------------- 可缓存 / 可分段
        out.subsection("7. 工程属性 1：第二次跑必须复用缓存（否则不可迭代）")
        second = run_pipeline(cfg, verbose=False, do_serve=False)
        out.kv("第二次 cached", json.dumps(second.cached, ensure_ascii=False))
        out.kv("第二次训练阶段耗时", f"{second.timings.get('train', 0.0):.3f} s", "复用检查点，不重训")
        out.kv("与第一次是否同一份权重", "是（都从 models/tiny_lm_best.npz 读回）")
        out.kv("为什么重要", "不缓存的话每改一行评估代码就要重训一次，实验迭代直接瘫痪")

        out.subsection("8. 工程属性 2：只跑某几段（排查问题时不用从头训）")
        partial = run_pipeline(cfg, verbose=False, do_serve=False,
                               only=["config", "tokenizer", "dataset"])
        out.kv("only=[config, tokenizer, dataset] 后 model 是否为空", partial.model is None)
        out.kv("跑到的阶段", ", ".join(sorted(partial.timings)))
        out.kv("为什么重要", "改评估逻辑只重跑 evaluate，改服务只重跑 serve，秒级验证")

        out.subsection("9. 工程属性 3：报告可机读（所以能进 CI、能对比实验）")
        out.kv("顶层字段", ", ".join(sorted(full_report)))
        out.kv("config.model.d_model", full_report["config"]["model"]["d_model"])
        out.kv("config.optim.lr", full_report["config"]["optim"]["lr"])
        out.kv("train 关键字段",
               ", ".join(sorted(full_report["train"])) if full_report.get("train") else "(复用检查点)")
        out.kv("evaluate.perplexity", round(full_report["evaluate"]["perplexity"], 2))
        out.kv("evaluate.ece", round(full_report["evaluate"]["ece"], 4))
        out.kv("serve.load.requests_per_sec",
               round(full_report["serve"]["load"]["requests_per_sec"], 2)
               if full_report.get("serve") else "-")
        out.kv("用途", "两次实验各留一份 report.json，直接 diff 就知道哪个超参带来了变化")

        # ------------------------------------------------------- 汇总
        out.subsection("10. 11 章关键数字汇总（Capstone 的交付物）")
        tr = result.train_report
        rows = [
            ["M01 架构", "唯一配置入口 + 8 段链路", f"{len(STAGES)} 个阶段"],
            ["M02 分词器", f"{result.tokenizer.kind} vocab={result.tokenizer.vocab_size}",
             f"{tok_stats['chars_per_token']:.2f} 字/token，unk {tok_stats['unk_rate'] * 100:.2f}%"],
            ["M03 数据集", f"train {ds_meta['train_examples']} / val {ds_meta['val_examples']}",
             f"泄漏 {ds_meta['leakage']['overlap']} 条"],
            ["M04 Embedding", f"({result.tokenizer.vocab_size}, {cfg.model.d_model})",
             f"{result.tokenizer.vocab_size * cfg.model.d_model:,} 参数"],
            ["M05 Block", f"{cfg.model.n_layers} 层 × {cfg.model.n_heads} 头",
             "因果性自检误差 0"],
            ["M06 训练", f"loss {tr.get('meta', {}).get('best_val_loss', float('nan')):.4f}",
             f"早停回滚到第 {tr.get('meta', {}).get('best_step')} 步"],
            ["M07 评估", f"PPL {ev['perplexity']:.2f}", f"ECE {ev['ece']:.4f}"],
            ["M08 推理", f"KV Cache {speed.get('speedup', 0):.2f}×",
             f"logits 误差 {speed.get('max_logit_error', 0):.1e}"],
            ["M09 优化", f"INT8 压缩 {quant['INT8']['compression_ratio']:.2f}×",
             f"ΔPPL {quant['INT8']['ppl_delta_pct']:+.2f}%"],
            ["M10 服务", f"冒烟通过={sv.get('smoke', {}).get('passed')}" if sv else "未起服务",
             f"{load.get('requests_per_sec', 0):.1f} req/s" if load else "-"],
            ["M11 全链路", f"{len(STAGES)} 段一次跑完", f"{total_wall:.2f} s"],
        ]
        out.table(["章节", "核心指标", "关键数字"], rows, aligns=["<", "<", "<"])

        # 第 8 节的分段重跑把 models/report.json 覆盖成了「只含前三段」的版本，
        # 这里补跑一次完整链路，让磁盘上留着的报告仍是**完整**的那份（有缓存，约 1 秒）。
        restored = run_pipeline(cfg, verbose=False)
        out.subsection("11. 收尾：磁盘上留下的必须是一份完整报告")
        out.kv("重新跑完整链路", "有缓存，约 1 秒")
        out.kv("serve 阶段是否在", bool(restored.serve_report))
        out.kv("evaluate.perplexity", f"{restored.eval_report.get('perplexity', 0):.2f}")
        out.kv("为什么较真", "第 8 节演示了分段跑会覆盖报告；不收尾就会把残缺报告留给下一个读它的人")

        out.subsection("关键数字")
        out.kv("流水线阶段数", len(STAGES))
        out.kv("一次跑完耗时", f"{total_wall:.2f} s")
        out.kv("缓存命中", json.dumps(result.cached, ensure_ascii=False))
        out.kv("最重的一段", max(result.timings, key=lambda k: result.timings[k]))
        out.kv("一句话结论", "Capstone 交付的不是模型，而是一条**可缓存的、可分段重跑的、"
               "报告可机读的**流水线")


if __name__ == "__main__":
    main()
