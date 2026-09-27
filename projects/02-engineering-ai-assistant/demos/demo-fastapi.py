"""Milestone 09 实验：真实启动 FastAPI 服务并发请求。

做法是「真的起 uvicorn，真的发 HTTP」：
- 复用 assistant.api 的 app（不另写一份），只把 lifespan 里的客户端换成 FakeClient，
  这样既不烧真实 API 额度，又完整走通 lifespan → 路由 → 响应的真实链路；
- 四个端点都打一遍：/health、/chat、/chat/stream（SSE）、/reset。
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

import assistant.api as api  # noqa: E402
from assistant.client import FakeClient  # noqa: E402
from assistant.service import AssistantService  # noqa: E402

HOST = "127.0.0.1"
PORT = 8782
BASE = f"http://{HOST}:{PORT}"
REPLY = "[fake] 这是 FakeClient 的固定回答，用来验证链路而不是烧额度。"


@asynccontextmanager
async def fake_lifespan(app):
    """替换 lifespan：只换掉客户端，路由与异常处理仍是真实代码。"""
    app.state.service = AssistantService(
        FakeClient(reply=REPLY), system_prompt="你是一个简洁的中文 AI 助手。")
    yield
    await app.state.service.aclose()


def wait_port(timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((HOST, PORT)) == 0:
                return
        time.sleep(0.2)
    raise SystemExit("服务没起来")


def request(method: str, path: str, body: dict | None = None):
    """发一次真实请求；stream=True 时返回原始响应对象供逐行读取。"""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    # 绕过本机代理，确保打到 127.0.0.1
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(req, timeout=10)


def main() -> None:
    api.app.router.lifespan_context = fake_lifespan

    config = uvicorn.Config(api.app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    wait_port()
    print(f"uvicorn 已启动：{BASE}（app 来自 assistant.api，lifespan 换成 FakeClient）")

    print("\n===== 1. GET /health（探活，不碰模型）=====")
    with request("GET", "/health") as resp:
        print("  状态码:", resp.status)
        print("  响应体:", resp.read().decode())

    print("\n===== 2. POST /chat（走完整 service → client 链路）=====")
    with request("POST", "/chat", {"message": "讲讲 RAG"}) as resp:
        print("  状态码:", resp.status)
        print("  响应体:", resp.read().decode())

    print("\n===== 3. POST /chat/stream（SSE，逐帧到达）=====")
    req = urllib.request.Request(f"{BASE}/chat/stream",
                                 data=json.dumps({"message": "讲讲 RAG"}).encode(),
                                 method="POST")
    req.add_header("Content-Type", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=10) as resp:
        print("  Content-Type:", resp.headers.get("Content-Type"))
        t0 = time.perf_counter()
        frames: list[tuple[int, str]] = []
        # 必须把整条流读完再断开：中途 break 会让服务端写失败，
        # 刷出一片 "socket.send() raised exception"，把真实输出淹掉。
        for raw in resp:
            line = raw.decode().rstrip()
            if line:
                frames.append((int((time.perf_counter() - t0) * 1000), line))
        for ms, line in frames[:6]:
            print(f"  [{ms:>4}ms] {line}")
        print(f"  ...（共 {len(frames)} 帧，以上只打印前 6 帧）")
        print(f"  最后一帧 [{frames[-1][0]}ms] {frames[-1][1]}")

    print("\n===== 4. POST /reset（清空会话）=====")
    with request("POST", "/reset", {}) as resp:
        print("  状态码:", resp.status)
        print("  响应体:", resp.read().decode())

    print("\n===== 5. 入参校验：空 message 会被 Pydantic 挡住（422）=====")
    try:
        request("POST", "/chat", {"message": ""})
    except urllib.error.HTTPError as exc:
        print("  状态码:", exc.code)
        print("  响应体:", exc.read().decode()[:220])

    server.should_exit = True
    print("\n服务已关闭")


if __name__ == "__main__":
    main()
