"""demo_01 —— 最小可用调用：把 REST 请求摊开看清楚。

这条 demo 回答一个问题：**「所谓调用大模型」在 HTTP 层面到底做了什么**。

真实验证点（都来自本次运行，不看文档背书）：
- usage 守恒：total_tokens == prompt_tokens + completion_tokens
- 本地粗估 token 数与服务端真实 usage 的差距
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import Tee, fmt_table, rule  # noqa: E402
from llm_client import (  # noqa: E402
    API_BASE,
    call_chat,
    estimate_tokens,
    load_api_key,
    redacted,
)


def main() -> None:
    with Tee("demo_01_chat") as out:
        out.print(rule("demo_01_chat：最小可用调用"))
        out.print("")

        key = load_api_key()
        out.print("1) 鉴权方式：Authorization 头带 Bearer token")
        out.print(f"   key（脱敏）= {redacted(key)}")
        out.print(f"   endpoint   = {API_BASE}/chat/completions")
        out.print("")

        messages = [
            {
                "role": "system",
                "content": "你是资深 Java 面试官。回答简洁准确，控制在 80 字以内。",
            },
            {"role": "user", "content": "用一句话解释 Java 里 volatile 关键字的作用。"},
        ]
        out.print("2) 请求体里的 messages —— 三种 role 的分工：")
        out.print("   system    = 人设/全局约束（每轮都带，也要计费）")
        out.print("   user      = 本轮提问")
        out.print("   assistant = 历史回答（多轮对话时由我们把上一轮结果塞回去）")
        for m in messages:
            out.print(f"   - {m['role']:9s} | {m['content']}")
        out.print("")

        prompt_text = "".join(m["content"] for m in messages)
        local_est = estimate_tokens(prompt_text)
        out.print(f"3) 本地粗估 prompt token ≈ {local_est}")
        out.print("   （口径：中文约 1 字 1 token，英文约 4 字符 1 token —— 这是估算，不是分词器结果）")
        out.print("")

        out.print(rule("等价 curl（教学对照）"))
        out.print(f"   curl {API_BASE}/chat/completions \\")
        out.print("     -H 'Content-Type: application/json' \\")
        out.print("     -H 'Authorization: Bearer $DEEPSEEK_API_KEY' \\")
        out.print("     -d '{\"model\":\"deepseek-chat\",\"messages\":[...],\"stream\":false}'")
        out.print("")

        out.print(rule("真实调用结果"))
        result = call_chat(messages, temperature=0.2, max_tokens=300)

        out.print(f"   model         = {result.model}")
        out.print(f"   finish_reason = {result.finish_reason}")
        out.print(f"   latency       = {result.latency_s:.3f} s")
        out.print("")
        out.print("   usage 明细：")
        out.lines(fmt_table(
            ["字段", "值"],
            [
                ["prompt_tokens", result.usage.prompt_tokens],
                ["completion_tokens", result.usage.completion_tokens],
                ["total_tokens", result.usage.total_tokens],
            ],
        ))
        out.print("")
        conserved = result.usage.is_conserved()
        out.print(f"   守恒校验 total == prompt + completion ? -> {conserved}")
        out.print(f"   本地估算 vs 真实 prompt token 误差 = "
                  f"{abs(local_est - result.usage.prompt_tokens)} "
                  f"（估算 {local_est} / 真实 {result.usage.prompt_tokens}）")
        out.print("")
        out.print(rule("回答内容"))
        out.print(f"   {result.content}")
        out.print("")

        out.save_json({
            "model": result.model,
            "finish_reason": result.finish_reason,
            "latency_s": round(result.latency_s, 4),
            "local_estimate_prompt_tokens": local_est,
            "usage": result.usage.as_dict(),
            "usage_conserved": conserved,
            "content": result.content,
        })


if __name__ == "__main__":
    main()
