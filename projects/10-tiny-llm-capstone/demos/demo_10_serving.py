#!/usr/bin/env python
"""M10 · Serving：把模型变成一个**有接口、有指标、能被压测**的服务。

这一层刻意不自己写 HTTP 服务器，而是复用 P09 已经跑通并压测过的
``ie.serve``（标准库 ``http.server`` + OpenAI 兼容协议 + SSE）。理由很实在：
HTTP 里最容易翻车的是协议细节（Content-Length、分块、连接复用、
代理劫持 localhost），这些坑 P09 已经全踩过一遍。

本章补的是「上线前必须自己跑一遍」的那四件事：
健康检查 / 非流式 / 流式（含 usage）/ 错误码，再加一轮并发压测。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bundle import build_cfg, ensure_bundle  # noqa: E402
from _emit import Printer  # noqa: E402

from tiny.serve import (  # noqa: E402
    ServingSession,
    chat_completion,
    chat_payload,
    health,
    load_test,
    metrics,
    smoke_test,
    stream_completion,
)

PROMPTS = [
    "问：什么是 LoRA？答：",
    "问：什么是 KV Cache？答：",
    "问：什么是幻觉？答：",
    "问：什么是早停？答：",
    "问：什么是量化？答：",
    "问：什么是 RAG？答：",
]


def main() -> None:
    with Printer("demo_10_serving") as out:
        out.section("M10 · Serving：OpenAI 兼容接口 / SSE 流式 / 健康检查 / 并发压测")

        cfg = build_cfg()
        cfg, tokenizer, _dataset, model, _report, _cache = ensure_bundle(cfg)

        out.subsection("1. 服务配置")
        out.kv("绑定地址", f"{cfg.serve.host}:端口由操作系统分配（port=0）")
        out.kv("为什么用 port=0", "测试与 demo 永不撞端口，CI 上也不会随机失败")
        out.kv("max_tokens", cfg.serve.max_tokens)
        out.kv("压测并发", cfg.serve.concurrency)
        out.kv("协议", "OpenAI 兼容：POST /v1/chat/completions、GET /health、GET /metrics")

        # --------------------------------------------------------- 请求体长什么样
        out.subsection("2. 请求体（OpenAI 兼容形状）")
        payload = chat_payload("问：什么是 LoRA？答：", max_tokens=16)
        out.line("  " + json.dumps(payload, ensure_ascii=False))
        out.kv("为什么照抄这个形状", "任何 OpenAI SDK / 前端都能无改造接上，省掉一层适配")

        with ServingSession(cfg, model, tokenizer) as session:
            base = session.url
            out.subsection("3. 起服务")
            out.kv("base_url", base)
            out.kv("线程数", "1（标准库 http.server + 线程化处理）")

            # --------------------------------------------------- 健康检查与指标
            out.subsection("4. 健康检查 / 指标端点")
            hs, hb = health(base)
            out.kv("GET /health 状态码", hs)
            out.kv("GET /health 响应", json.dumps(hb, ensure_ascii=False))
            ms, mb = metrics(base)
            out.kv("GET /metrics 状态码", ms)
            out.kv("GET /metrics 字段", ", ".join(sorted(mb)) if isinstance(mb, dict) else mb)
            out.kv("此刻的数值", "全 0 —— 还没发过请求（见第 10 节打完流量后的读数）")
            out.kv("为什么要 P95 而不是平均值", "平均值会被大量快请求稀释，尾延迟才是用户体验")

            # --------------------------------------------------- 非流式
            out.subsection("5. 非流式对话 + usage 计量")
            status, body = chat_completion(base, PROMPTS[0], max_tokens=16, temperature=0.0)
            out.kv("HTTP 状态码", status)
            choice = body.get("choices", [{}])[0]
            out.kv("finish_reason", choice.get("finish_reason"))
            out.kv("content", repr(choice.get("message", {}).get("content", "")))
            usage = body.get("usage", {})
            out.kv("usage", json.dumps(usage, ensure_ascii=False))
            out.kv("为什么 usage 必须准", "计费、限流、成本核算全依赖它，差一个 token 都是账目问题")

            # --------------------------------------------------- 流式
            out.subsection("6. 流式（SSE）：逐 token 交付 + 末尾 usage")
            sstatus, events = stream_completion(base, PROMPTS[0], max_tokens=16, temperature=0.0)
            token_events = [e for e in events if e != "[DONE]"
                            and e.get("choices") and e["choices"][0].get("delta", {}).get("content")]
            usage_events = [e for e in events if e != "[DONE]" and "usage" in e]
            out.kv("HTTP 状态码", sstatus)
            out.kv("总事件数", len(events))
            out.kv("含内容的 delta 事件数", len(token_events))
            out.kv("含 usage 的事件数", len(usage_events), "stream_options.include_usage 打开时才有")
            out.kv("是否收到 [DONE] 结束标记", "[DONE]" in events)
            rebuilt = "".join(e["choices"][0]["delta"]["content"] for e in token_events)
            out.kv("事件拼起来 = 完整答案", repr(rebuilt))
            for index, event in enumerate(token_events[:5], 1):
                out.line(f"  event {index}: data: {json.dumps(event['choices'][0]['delta'], ensure_ascii=False)}")

            # --------------------------------------------------- 错误路径
            out.subsection("7. 错误路径：非法参数必须返回 4xx，而不是 500")
            bad_status, bad_body = chat_completion(base, PROMPTS[0], max_tokens=0)
            out.kv("max_tokens=0 的状态码", bad_status)
            out.kv("错误体", json.dumps(bad_body, ensure_ascii=False)[:120])
            out.kv("为什么要测这个", "错误被吞成 500，前端就没法区分「我传错了」和「服务挂了」")

            # --------------------------------------------------- 冒烟
            out.subsection("8. 一键冒烟：health → 非流式 → 流式 → 错误码")
            smoke = smoke_test(base, PROMPTS[0], max_tokens=8)
            out.kv("health 状态码", smoke["health"]["status"])
            out.kv("非流式状态码", smoke["non_stream"]["status"])
            out.kv("流式 token 事件 / usage 事件", f"{smoke['stream']['token_events']} / {smoke['stream']['usage_events']}")
            out.kv("流式是否有 [DONE]", smoke["stream"]["done"])
            out.kv("非法参数状态码", smoke["bad_request"]["status"])
            out.kv("冒烟是否整体通过", smoke["passed"], "四项全过才算服务可用")

            # --------------------------------------------------- 压测
            out.subsection("9. 并发压测")
            for concurrency in (1, 4):
                result = load_test(base, PROMPTS, concurrency=concurrency, max_tokens=cfg.serve.max_tokens)
                out.kv(f"并发 {concurrency}：请求 / 成功",
                       f"{result['requests']} / {result['success']}")
                out.kv("  墙钟 / 单请求（顺序）",
                       f"{result['wall_ms']:.0f} ms / {result['single_request_ms']:.0f} ms")
                out.kv("  吞吐", f"{result['requests_per_sec']:.2f} req/s"
                       f"  {result['tokens_per_sec']:.1f} tok/s")
                out.kv("  相对串行的加速", f"{result['speedup_vs_serial']:.2f}×")

            # --------------------------------------------------- 打完流量后的指标
            out.subsection("10. 打完流量后的运行指标")
            _, mb_after = metrics(base)
            for key, label in (
                ("requests", "累计请求数"),
                ("generated_tokens", "累计生成 token"),
                ("errors", "错误数（含被正确拒绝的 400）"),
                ("mean_latency_ms", "平均延迟"),
                ("p50_latency_ms", "P50 延迟"),
                ("p95_latency_ms", "P95 延迟"),
            ):
                if key in mb_after:
                    value = mb_after[key]
                    out.kv(label, f"{value:.2f} ms" if "latency" in key else value)
            out.kv("平均 vs P95", f"{mb_after.get('mean_latency_ms', 0):.2f} ms vs "
                   f"{mb_after.get('p95_latency_ms', 0):.2f} ms",
                   "平均值被快请求稀释，尾延迟才是用户体验")
        # --------------------------------------------------------- 关键数字
        out.subsection("关键数字")
        out.kv("冒烟四项", f"health={smoke['health']['status']} 非流式={smoke['non_stream']['status']}"
               f" 流式={smoke['stream']['status']} 错误={smoke['bad_request']['status']}")
        out.kv("流式事件", f"{len(token_events)} 个 delta + {len(usage_events)} 个 usage + [DONE]")
        out.kv("并发 4 吞吐", f"{result['requests_per_sec']:.2f} req/s"
               f"（{result['success']}/{result['requests']} 成功）")
        out.kv("一句话结论", "服务化的验收标准不是「能返回」，而是「四项冒烟 + 压测都过」")


if __name__ == "__main__":
    main()
