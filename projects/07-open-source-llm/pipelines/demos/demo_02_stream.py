"""demo_02 —— 流式输出（SSE）：把「打字机效果」拆成可测量的三段指标。

为什么要测 TTFT（首字延迟）而不是只看总耗时？
因为**用户体验取决于第一个字多久出来**，而不是整段多久完成。
非流式调用里 TTFT 与总耗时是同一个数，用户只能干等；
流式把它拆开：先出字、再持续吐，体感完全不同。

三个实现坑（代码里已处理）：
- SSE 行以 ``data: {...}`` 承载增量，``data: [DONE]`` 收尾；
- 流式下想拿到 usage，**必须**显式请求 ``stream_options.include_usage``；
- usage 只出现在收尾 chunk，且那个 chunk 的 choices 通常是空数组，要容错否则 IndexError。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import Tee, fmt_table, rule  # noqa: E402
from llm_client import call_chat_stream  # noqa: E402

QUESTION = "请解释 Java 中线程池的 corePoolSize 和 maximumPoolSize 的区别，并举例说明。"
PREVIEW_CHUNKS = 8          # 打印前若干个 chunk，直观展示「分包」粒度
PREVIEW_CHARS = 160         # 最终内容预览长度


def main() -> None:
    with Tee("demo_02_stream") as out:
        out.print(rule("demo_02_stream：SSE 流式输出"))
        out.print("")
        out.print(f"提问：{QUESTION}")
        out.print("")
        out.print(rule(f"前 {PREVIEW_CHUNKS} 个 SSE chunk（看分包粒度）"))

        shown = 0
        final = None
        for delta, snap in call_chat_stream(
            [{"role": "user", "content": QUESTION}],
            temperature=0.3,
            max_tokens=400,
        ):
            if delta and shown < PREVIEW_CHUNKS:
                shown += 1
                out.print(f"   chunk #{shown:02d}  len={len(delta):3d}  内容={delta!r}")
            final = snap

        assert final is not None, "流式调用没有产出任何快照"
        out.print("")
        out.print(rule("累积指标（本次真实运行测量）"))
        out.lines(fmt_table(
            ["指标", "数值", "含义"],
            [
                ["chunks", final.chunks, "收到的内容分片数（不含收尾统计包）"],
                ["TTFT (s)", f"{final.ttft_s:.3f}", "首字延迟：发出请求到收到第一个字"],
                ["total (s)", f"{final.total_s:.3f}", "端到端总耗时"],
                ["completion_tokens", final.usage.completion_tokens, "服务端统计的输出 token"],
                ["gen_tps", f"{final.generation_tps:.1f}", "净生成吞吐（去掉首包后的速度）"],
                ["gross_tps", f"{final.usage.completion_tokens / final.total_s:.1f}", "毛吞吐（含首包等待）"],
            ],
        ))
        out.print("")
        out.print(f"   占比：TTFT 占总耗时 {final.ttft_s / final.total_s * 100:.1f}%")
        out.print("   -> 结论：流式并不能让模型变快，它只是把等待时间**摊到用户眼前**，")
        out.print("      让人在等待期间就已经开始阅读。TTFT 才是要优化的那个数。")
        out.print("")
        out.print(rule(f"还原后的完整回答（前 {PREVIEW_CHARS} 字）"))
        out.print(f"   {final.content[:PREVIEW_CHARS]}...")
        out.print("")

        out.save_json({
            "model": final.model,
            "chunks": final.chunks,
            "ttft_s": round(final.ttft_s, 4),
            "total_s": round(final.total_s, 4),
            "ttft_ratio": round(final.ttft_s / final.total_s, 4),
            "generation_tps": round(final.generation_tps, 2),
            "usage": final.usage.as_dict(),
            "content": final.content,
        })


if __name__ == "__main__":
    main()
