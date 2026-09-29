"""demo_03 —— 生成参数对照：temperature 到底改变了什么。

设计原则：**同一个 prompt、同一句话，只改一个变量**。
这样才能把差异归因到参数本身，而不是被 prompt 波动污染。

重点观察两件事：
1. temperature=0 连续两次是否**完全一致**（贪婪解码的确定性）
2. temperature 升高后输出是否开始发散
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import Tee, fmt_table, rule  # noqa: E402
from llm_client import call_chat  # noqa: E402

QUESTION = "用一句话解释 Java 里的 happens-before 原则。"
CONFIGS = [0.0, 0.0, 0.7, 1.5]
PREVIEW_CHARS = 70


def main() -> None:
    with Tee("demo_03_params") as out:
        out.print(rule("demo_03_params：生成参数对照实验"))
        out.print("")
        out.print(f"固定提问：{QUESTION}")
        out.print("固定其余参数：top_p=1.0, max_tokens=120；唯一自变量 = temperature")
        out.print("")

        runs = []
        for idx, temp in enumerate(CONFIGS, start=1):
            result = call_chat(
                [{"role": "user", "content": QUESTION}],
                temperature=temp,
                max_tokens=120,
            )
            runs.append(result)
            preview = result.content.replace("\n", " ")[:PREVIEW_CHARS]
            out.print(f"[{idx}] temperature={temp}")
            out.print(f"    回答：{preview}...")
            out.print(f"    tokens={result.usage.completion_tokens}  latency={result.latency_s:.3f}s")
            out.print("")

        out.print(rule("汇总对照表"))
        out.lines(fmt_table(
            ["#", "temperature", "completion_tokens", "latency(s)"],
            [
                [i, c, r.usage.completion_tokens, f"{r.latency_s:.3f}"]
                for i, (c, r) in enumerate(zip(CONFIGS, runs), start=1)
            ],
        ))
        out.print("")

        r1, r2 = runs[0], runs[1]
        identical = r1.content == r2.content
        out.print(rule("确定性校验（temperature=0 跑两次）"))
        out.print(f"   两次输出完全一致？ -> {identical}")
        out.print(f"   两次 token 数：{r1.usage.completion_tokens} vs {r2.usage.completion_tokens}")
        out.print("   说明：temperature=0 走贪婪解码，每步都选概率最大的 token，")
        out.print("         所以同一份输入在没有服务端抖动时应当复现同一结果。")
        out.print("         注意这只保证『近似确定性』——batch/算子层面的浮点误差仍可能带来极偶发差异。")
        out.print("")

        temps = [c for c in CONFIGS]
        uniq = len(set(r.content for r in runs))
        out.print(rule("发散性观察"))
        out.print(f"   共 {len(runs)} 次调用，去重后得到 {uniq} 种不同回答")
        out.print(f"   temperature 取值序列：{temps}")
        out.print("   趋势：temperature 越高，低概率 token 越可能被采到，输出越发散、也越容易跑题。")
        out.print("")

        out.save_json({
            "question": QUESTION,
            "configs": [
                {
                    "temperature": c,
                    "completion_tokens": r.usage.completion_tokens,
                    "latency_s": round(r.latency_s, 4),
                    "content": r.content,
                }
                for c, r in zip(CONFIGS, runs)
            ],
            "two_runs_at_zero_identical": identical,
            "unique_outputs": uniq,
        })


if __name__ == "__main__":
    main()
