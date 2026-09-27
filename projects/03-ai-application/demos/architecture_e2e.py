"""Milestone 09 实验：把分层架构端到端跑一遍。

做法是「真的起 uvicorn，真的发 HTTP」：
- app 来自 assistant.api.create_app()，只把 lifespan 里的客户端换成 FakeClient，
  路由、依赖注入、异常处理仍是真实代码；
- 五个端点都打一遍，并对比「一次性 / 流式 / 结构化 / Agent」四种形态的差异；
- 最后跑一遍全量测试，证明这一层改动没有打破下层。
"""

from __future__ import annotations

import json
import socket
import subprocess
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

from assistant.api import create_app  # noqa: E402
from assistant.client import FakeClient  # noqa: E402
from assistant.service import ChatService  # noqa: E402
from assistant.settings import Settings  # noqa: E402

HOST = "127.0.0.1"
PORT = 8793
BASE = f"http://{HOST}:{PORT}"
REPLY = "[fake] 分层跑通了：API → Service → Client。"
# 与 assistant.models.SkillExtraction 的字段一一对应（name / skills / years / summary）
STRUCTURED = ('{"name": "小明", "skills": ["Java", "Spring Boot"], '
              '"years": 5, "summary": "5 年 Java 后端，熟悉 Spring Boot。"}')


class StructuredFake(FakeClient):
    """只在「要结构化输出」时返回 JSON；其余照常。

    FakeClient 默认回的是纯文本，直接打 /chat/structured 会 502 并刷一屏
    服务端 traceback，把真正想展示的分层链路盖掉。这里补一个最小替身。
    """

    async def chat(self, messages, response_format=None, tools=None):
        if response_format:
            return STRUCTURED
        return await super().chat(messages, response_format=response_format, tools=tools)


@asynccontextmanager
async def fake_lifespan(app):
    """只换掉最底层的 client；上面四层（API/Service/Memory/Schema）全是真实代码。"""
    app.state.service = ChatService(client=StructuredFake(reply=REPLY),
                                    settings=Settings(api_key="test-key"),
                                    system_prompt="你是一个简洁的中文 AI 助手。")
    yield


def wait_port(timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((HOST, PORT)) == 0:
                return
        time.sleep(0.2)
    raise SystemExit("服务没起来")


def post(path: str, body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> None:
    app = create_app()
    app.router.lifespan_context = fake_lifespan
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    wait_port()
    print(f"uvicorn 已启动：{BASE}")
    print("链路：HTTP → api.py → ChatService → memory/schema/tools → FakeClient")

    print("\n===== 1. GET /health =====")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"{BASE}/health", timeout=10) as resp:
        print(" ", resp.status, resp.read().decode())

    print("\n===== 2. POST /chat（一次性）=====")
    code, body = post("/chat", {"message": "讲讲 RAG", "session_id": "demo"})
    print(" ", code, body)

    print("\n===== 3. POST /chat/stream（流式，SSE 逐帧）=====")
    req = urllib.request.Request(f"{BASE}/chat/stream",
                                 data=json.dumps({"message": "讲讲 RAG"}).encode(),
                                 method="POST")
    req.add_header("Content-Type", "application/json")
    with opener.open(req, timeout=15) as resp:
        print("  Content-Type:", resp.headers.get("Content-Type"))
        frames = [ln.decode().rstrip() for ln in resp if ln.strip()]
    print(f"  共 {len(frames)} 帧，前 3 帧：")
    for f in frames[:3]:
        print("   ", f)

    print("\n===== 4. POST /chat/structured（结构化输出）=====")
    code, body = post("/chat/structured", {
        "message": "我叫小明，会 Java 和 Spring Boot，干了 5 年",
        "schema_name": "skill",
    })
    print(" ", code, body[:200])

    print("  → schema_name 写错会先在 API 层被挡住（400），不会打到模型：")
    code, body = post("/chat/structured", {"message": "同上", "schema_name": "nope"})
    print(" ", code, body[:160])

    print("\n===== 5. POST /chat/agent（工具循环）=====")
    code, body = post("/chat/agent", {"message": "3 加 4 等于几"})
    print(" ", code, body[:200])

    print("\n===== 6. POST /reset =====")
    code, body = post("/reset", {"session_id": "demo"})
    print(" ", code, body)

    print("\n===== 7. 入参校验：message 为空 → 422（在 API 层就被挡住）=====")
    code, body = post("/chat", {"message": ""})
    print(" ", code, body[:160])

    server.should_exit = True

    print("\n===== 8. 全量测试：这一层改动有没有打破下层 =====")
    proc = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "-p", "no:warnings"],
        cwd=ROOT, capture_output=True, text=True)
    print(" ", proc.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    main()
