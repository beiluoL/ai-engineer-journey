"""仅用标准库实现的 OpenAI 兼容 HTTP/SSE 模型服务。"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import ProxyHandler, build_opener

import numpy as np


class ServingMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests = 0
        self.errors = 0
        self.generated_tokens = 0
        self.latencies_ms: list[float] = []

    def record(self, tokens: int, latency_ms: float, error: bool = False) -> None:
        with self._lock:
            self.requests += 1
            self.errors += int(error)
            self.generated_tokens += int(tokens)
            self.latencies_ms.append(float(latency_ms))

    def snapshot(self) -> dict:
        with self._lock:
            values = np.asarray(self.latencies_ms, dtype=np.float64)
            total_seconds = values.sum() / 1000.0
            return {
                "requests": self.requests,
                "errors": self.errors,
                "generated_tokens": self.generated_tokens,
                "mean_latency_ms": float(values.mean()) if values.size else 0.0,
                "p50_latency_ms": float(np.percentile(values, 50)) if values.size else 0.0,
                "p95_latency_ms": float(np.percentile(values, 95)) if values.size else 0.0,
                "throughput_tokens_per_sec": self.generated_tokens / total_seconds if total_seconds else 0.0,
            }


def _prompt_from_messages(messages: list[dict]) -> str:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages 必须是非空数组")
    lines = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = str(message.get("content", ""))
        lines.append(f"{role}: {content}")
    lines.append("assistant:")
    return "\n".join(lines)


def make_handler(engine, tokenizer, metrics: ServingMetrics):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *args) -> None:
            return

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(200, {"status": "ok"})
            elif self.path == "/metrics":
                self._json(200, metrics.snapshot())
            else:
                self._json(404, {"error": {"message": "not found", "type": "not_found"}})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/chat/completions":
                self._json(404, {"error": {"message": "not found", "type": "not_found"}})
                return
            started = time.perf_counter()
            generated = 0
            try:
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                prompt = _prompt_from_messages(payload.get("messages"))
                max_tokens = int(payload.get("max_tokens", 16))
                if max_tokens <= 0:
                    raise ValueError("max_tokens 必须大于 0")
                prompt_ids = list(tokenizer.encode(prompt))
                room = engine.max_len - max_tokens
                if room <= 0:
                    raise ValueError("max_tokens 超过模型上下文容量")
                prompt_ids = prompt_ids[-room:]
                if not prompt_ids:
                    prompt_ids = [1]
                all_ids = engine.generate_ids(
                    prompt_ids, max_tokens, use_kv_cache=True,
                    temperature=float(payload.get("temperature", 0.0)),
                    seed=int(payload.get("seed", 0)), stop_id=None,
                )
                completion_ids = all_ids[len(prompt_ids):]
                generated = len(completion_ids)
                request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                if payload.get("stream", False):
                    self._stream(request_id, completion_ids, len(prompt_ids), payload)
                else:
                    text = tokenizer.decode(completion_ids, skip_special=True)
                    response = {
                        "id": request_id,
                        "object": "chat.completion",
                        "model": payload.get("model", "numpy-transformer"),
                        "choices": [{
                            "index": 0,
                            "message": {"role": "assistant", "content": text},
                            "finish_reason": "length",
                        }],
                        "usage": {
                            "prompt_tokens": len(prompt_ids),
                            "completion_tokens": generated,
                            "total_tokens": len(prompt_ids) + generated,
                        },
                    }
                    self._json(200, response)
                metrics.record(generated, (time.perf_counter() - started) * 1000.0)
            except Exception as exc:
                metrics.record(generated, (time.perf_counter() - started) * 1000.0, error=True)
                try:
                    self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _stream(self, request_id: str, completion_ids: list[int], prompt_tokens: int, payload: dict) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            def send(data) -> None:
                encoded = f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
                self.wfile.write(encoded)
                self.wfile.flush()

            model_name = payload.get("model", "numpy-transformer")
            for token_id in completion_ids:
                send({
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": tokenizer.decode([token_id], skip_special=True)},
                        "finish_reason": None,
                    }],
                })
            send({
                "id": request_id,
                "object": "chat.completion.chunk",
                "model": model_name,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "length"}],
            })
            if (payload.get("stream_options") or {}).get("include_usage", False):
                send({
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "model": model_name,
                    "choices": [],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": len(completion_ids),
                        "total_tokens": prompt_tokens + len(completion_ids),
                    },
                })
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True

    return Handler


def create_server(engine, tokenizer, host: str = "127.0.0.1", port: int = 0):
    metrics = ServingMetrics()
    server = ThreadingHTTPServer((host, port), make_handler(engine, tokenizer, metrics))
    server.daemon_threads = True
    server.metrics = metrics
    return server


def start_server(engine, tokenizer, host: str = "127.0.0.1", port: int = 0):
    server = create_server(engine, tokenizer, host=host, port=port)
    thread = threading.Thread(target=server.serve_forever, name="numpy-llm-server", daemon=True)
    thread.start()
    actual_host, actual_port = server.server_address[:2]
    return server, thread, f"http://{actual_host}:{actual_port}"


def no_proxy_opener():
    """显式禁用 HTTP_PROXY，确保 localhost 请求不绕到代理。"""
    return build_opener(ProxyHandler({}))


def stop_server(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5.0)


__all__ = [
    "ServingMetrics", "create_server", "make_handler", "no_proxy_opener",
    "start_server", "stop_server",
]
