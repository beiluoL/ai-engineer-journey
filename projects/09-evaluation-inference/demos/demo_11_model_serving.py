#!/usr/bin/env python
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request as URLRequest

import numpy as np

np.random.seed(0)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from _common import base_bundle  # noqa: E402
from _emit import Printer  # noqa: E402
from ie.engine import CausalLMWithKVCache  # noqa: E402
from ie.serve import no_proxy_opener, start_server, stop_server  # noqa: E402


def post(url: str, payload: dict) -> tuple[int, bytes]:
    request = URLRequest(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with no_proxy_opener().open(request, timeout=30) as response:
        return response.status, response.read()


def get_json(url: str) -> tuple[int, dict]:
    with no_proxy_opener().open(url, timeout=30) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def payload(content: str, max_tokens: int = 4, stream: bool = False) -> dict:
    return {
        "model": "p09-numpy-lm",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": stream,
        "stream_options": {"include_usage": True},
    }


def main() -> None:
    with Printer("demo_11_model_serving") as out:
        out.section("M11 · Model Serving：http.server + OpenAI API + SSE")
        model, tokenizer, _info, _split, _train, _eval = base_bundle()
        engine = CausalLMWithKVCache(model)
        server, thread, base_url = start_server(engine, tokenizer, port=0)
        try:
            health_status, health = get_json(base_url + "/health")
            status, raw = post(base_url + "/v1/chat/completions", payload("解释 volatile", max_tokens=5))
            normal = json.loads(raw.decode("utf-8"))
            stream_status, stream_raw = post(
                base_url + "/v1/chat/completions",
                payload("解释 HashMap", max_tokens=6, stream=True),
            )
            data_lines = [
                line[6:] for line in stream_raw.decode("utf-8").splitlines()
                if line.startswith("data: ")
            ]
            chunks = [json.loads(line) for line in data_lines if line != "[DONE]"]
            token_chunks = [chunk for chunk in chunks if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content") is not None]
            usage_chunks = [chunk for chunk in chunks if "usage" in chunk]

            prompts = ["解释 CAS", "解释 AQS", "解释 JVM", "解释 Spring IoC"]
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(post, base_url + "/v1/chat/completions", payload(text, max_tokens=4)) for text in prompts]
                concurrent = [future.result() for future in futures]
            concurrent_ms = (time.perf_counter() - started) * 1000.0
            metrics_status, metrics = get_json(base_url + "/metrics")

            out.kv("服务地址（port=0 实际分配）", base_url)
            out.kv("GET /health", f"HTTP {health_status}, status={health['status']}")
            out.kv("Non-stream", f"HTTP {status}, object={normal['object']}")
            out.kv("Non-stream completion tokens", normal["usage"]["completion_tokens"])
            out.kv("SSE", f"HTTP {stream_status}")
            out.kv("SSE token chunks", len(token_chunks))
            out.kv("SSE usage chunks", len(usage_chunks), "stream_options.include_usage=true")
            out.kv("SSE 总 data 事件", len(data_lines), "含 finish、usage、[DONE]")
            out.kv("4 个并发请求", f"{sum(status == 200 for status, _ in concurrent)}/4 成功，墙钟 {concurrent_ms:.2f} ms")
            out.subsection("GET /metrics（真实请求计数与延迟）")
            out.kv("HTTP", metrics_status)
            out.kv("请求数", metrics["requests"])
            out.kv("错误数", metrics["errors"])
            out.kv("生成 token 数", metrics["generated_tokens"])
            out.kv("平均延迟", f"{metrics['mean_latency_ms']:.3f} ms")
            out.kv("p95 延迟", f"{metrics['p95_latency_ms']:.3f} ms")
            out.kv("Token 吞吐", f"{metrics['throughput_tokens_per_sec']:.2f} token/s")
            out.line("  客户端显式使用 ProxyHandler({})，已验证本机 HTTP_PROXY 不会劫持 localhost。")
        finally:
            stop_server(server, thread)


if __name__ == "__main__":
    main()
