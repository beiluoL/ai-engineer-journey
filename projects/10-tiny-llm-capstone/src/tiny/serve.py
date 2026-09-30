"""Milestone 10 —— 服务化：把模型变成一个**有接口、有指标、能被压测**的服务。

Capstone 的这一层刻意**不自己写 HTTP 服务器**，而是直接复用 P09 已经跑通并
压测过的 :mod:`ie.serve`（标准库 ``http.server`` + OpenAI 兼容协议 + SSE）。
理由很实在：HTTP 服务里最容易出错的是协议细节（Content-Length、分块、
连接复用、代理劫持 localhost），这些坑 P09 已经全踩过一遍了。

本模块补的是「上线」还缺的三件事：

1. **一键起服务** :func:`serve_model` —— 引擎、分词器、端口装配好直接返回 URL；
2. **客户端** :func:`chat_completion` / :func:`health` / :func:`metrics`，
   并且显式绕过本机 ``HTTP_PROXY``（P07 踩过的坑：代理会劫持 localhost 请求）；
3. **冒烟 + 压测** :func:`smoke_test` / :func:`load_test`：
   健康检查、非流式、流式、错误码、并发吞吐 —— 全跑一遍才算「服务可用」。

一个容易被忽略但不做就会出事的点：``port=0`` 让操作系统分配空闲端口，
测试与 demo 永远不会撞端口，也不会在 CI 上随机失败。
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request as URLRequest

import numpy as np

from .config import TinyConfig

from ie.engine import CausalLMWithKVCache  # noqa: E402
from ie.serve import (  # noqa: E402
    no_proxy_opener,
    start_server,
    stop_server,
)

__all__ = [
    "build_engine",
    "chat_completion",
    "chat_payload",
    "health",
    "load_test",
    "metrics",
    "serve_model",
    "smoke_test",
]


def build_engine(model) -> CausalLMWithKVCache:
    """把模型包装成 P09 的推理引擎（带 KV Cache）。"""
    return CausalLMWithKVCache(model)


def serve_model(
    cfg: TinyConfig,
    model,
    tokenizer,
    *,
    host: "str | None" = None,
    port: "int | None" = None,
):
    """起一个 OpenAI 兼容服务，返回 ``(server, thread, base_url, engine)``。"""
    engine = build_engine(model)
    server, thread, url = start_server(
        engine,
        tokenizer,
        host=host or cfg.serve.host,
        port=cfg.serve.port if port is None else port,
    )
    return server, thread, url, engine


# ------------------------------------------------------------------ 客户端
def chat_payload(content: str, *, max_tokens: int = 16, stream: bool = False,
                 temperature: float = 0.0, model_name: str = "tiny-llm") -> dict:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def _post(url: str, payload: dict, timeout: float = 60.0):
    """POST 并返回 ``(状态码, 原始 body)``。

    ⚠ ``urllib`` 默认把 4xx/5xx 当成**异常**抛出来，但服务端返回的错误体
    （``{"error": {...}}``）恰恰是冒烟测试要检查的东西。所以这里显式捕获
    :class:`HTTPError` 并把 body 读出来 —— 否则「错误路径」根本测不到。
    """
    request = URLRequest(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with no_proxy_opener().open(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as error:  # noqa: PERF203
        return error.code, error.read()


def _get(url: str, timeout: float = 30.0):
    with no_proxy_opener().open(url, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def chat_completion(base_url: str, content: str, **kwargs):
    """非流式对话；返回 ``(HTTP 状态码, 解析后的 dict)``。"""
    status, raw = _post(base_url + "/v1/chat/completions", chat_payload(content, **kwargs))
    return status, json.loads(raw.decode("utf-8"))


def stream_completion(base_url: str, content: str, **kwargs):
    """流式对话；返回「解析后的 SSE 事件列表」（已剥掉 ``data: `` 前缀）。"""
    status, raw = _post(base_url + "/v1/chat/completions", chat_payload(content, stream=True, **kwargs))
    body = raw.decode("utf-8")
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            text = line[6:]
            events.append("[DONE]" if text == "[DONE]" else json.loads(text))
    return status, events


def health(base_url: str):
    return _get(base_url + "/health")


def metrics(base_url: str):
    return _get(base_url + "/metrics")


# ------------------------------------------------------------------ 冒烟 / 压测
def smoke_test(base_url: str, prompt: str = "问：什么是 KV Cache？答：", max_tokens: int = 8) -> dict:
    """服务冒烟：health → 非流式 → 流式 → 非法参数（应返回 4xx）。"""
    health_status, health_body = health(base_url)
    ok_status, ok_body = chat_completion(base_url, prompt, max_tokens=max_tokens)
    stream_status, events = stream_completion(base_url, prompt, max_tokens=max_tokens)
    token_events = [
        e for e in events
        if e != "[DONE]" and e.get("choices") and e["choices"][0].get("delta", {}).get("content")
    ]
    usage_events = [e for e in events if e != "[DONE]" and "usage" in e]
    bad_status, bad_body = chat_completion(base_url, prompt, max_tokens=0)
    return {
        "health": {"status": health_status, "body": health_body},
        "non_stream": {
            "status": ok_status,
            "content": ok_body.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "usage": ok_body.get("usage", {}),
        },
        "stream": {
            "status": stream_status,
            "token_events": len(token_events),
            "usage_events": len(usage_events),
            "done": "[DONE]" in events,
        },
        "bad_request": {"status": bad_status, "error": bad_body.get("error", {}).get("type", "")},
        "passed": (
            health_status == 200
            and ok_status == 200
            and stream_status == 200
            and len(token_events) > 0
            and bad_status == 400
        ),
    }


def load_test(
    base_url: str,
    prompts: list[str],
    *,
    concurrency: int = 4,
    max_tokens: int = 8,
) -> dict:
    """并发压测：``concurrency`` 个线程同时发请求，统计墙钟、成功率与吞吐。"""
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(chat_completion, base_url, prompt, max_tokens=max_tokens)
            for prompt in prompts
        ]
        results = [future.result() for future in futures]
    wall_ms = (time.perf_counter() - started) * 1000.0
    successes = sum(1 for status, _body in results if status == 200)
    total_tokens = sum(
        int((body or {}).get("usage", {}).get("completion_tokens", 0))
        for status, body in results if status == 200
    )
    single_started = time.perf_counter()
    chat_completion(base_url, prompts[0], max_tokens=max_tokens)
    single_ms = (time.perf_counter() - single_started) * 1000.0
    return {
        "requests": len(prompts),
        "concurrency": concurrency,
        "success": successes,
        "failed": len(prompts) - successes,
        "wall_ms": wall_ms,
        "single_request_ms": single_ms,
        "requests_per_sec": len(prompts) / (wall_ms / 1000.0) if wall_ms else 0.0,
        "tokens_per_sec": total_tokens / (wall_ms / 1000.0) if wall_ms else 0.0,
        "completion_tokens": total_tokens,
        "speedup_vs_serial": (single_ms * len(prompts)) / wall_ms if wall_ms else 0.0,
        "all_ok": successes == len(prompts),
    }


class ServingSession:
    """``with`` 语法管理服务生命周期，保证线程一定被回收。"""

    def __init__(self, cfg: TinyConfig, model, tokenizer, **kwargs) -> None:
        self.cfg = cfg
        self.model = model
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        self.server = None
        self.thread: "threading.Thread | None" = None
        self.url = ""

    def __enter__(self) -> "ServingSession":
        self.server, self.thread, self.url, _engine = serve_model(
            self.cfg, self.model, self.tokenizer, **self.kwargs
        )
        return self

    def __exit__(self, *_args) -> None:
        if self.server is not None and self.thread is not None:
            stop_server(self.server, self.thread)
