"""FastAPI 集成测试（对应 milestones/09-fastapi.md 挑战 3）—— 不联网。

关键技巧：

1. dependency_overrides 把真实 service 换成 Fake 驱动的
2. 不用 with TestClient(app)（那会执行 lifespan、读取真实配置），
   直接构造 TestClient —— lifespan 不跑，依赖被 override，完全离线
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from assistant.api import app, get_service
from assistant.client import FakeClient
from assistant.service import AssistantService


@pytest.fixture
def client() -> TestClient:
    fake_service = AssistantService(FakeClient(reply="测试回答"), system_prompt="测试")
    app.dependency_overrides[get_service] = lambda: fake_service
    yield TestClient(app)          # 故意不用 with：不触发 lifespan
    app.dependency_overrides.clear()


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_returns_reply(client: TestClient):
    resp = client.post("/chat", json={"message": "你好"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "测试回答"


def test_chat_validates_empty_message(client: TestClient):
    """空消息被 Pydantic 拦下：422 + 明确指出错在 body.message。"""
    resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["body", "message"]


def test_chat_validates_too_long(client: TestClient):
    resp = client.post("/chat", json={"message": "x" * 4001})
    assert resp.status_code == 422


def test_reset_clears_history(client: TestClient):
    resp = client.post("/reset")
    assert resp.status_code == 200
    assert resp.json() == {"status": "reset"}


def test_stream_sse_format(client: TestClient):
    """SSE 硬性要求：data: 前缀、\\n\\n 分隔、最后一条是 [DONE]。"""
    resp = client.post("/chat/stream", json={"message": "流式"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    raw_events = [ln[6:] for ln in resp.text.split("\n\n") if ln.startswith("data: ")]
    assert raw_events[-1] == "[DONE]"

    deltas = "".join(json.loads(e)["delta"] for e in raw_events[:-1])
    assert deltas == "测试回答"        # FakeClient 逐字 yield，拼接后必须完整


def test_stream_records_full_answer_in_history(client: TestClient):
    client.post("/chat/stream", json={"message": "流式"})
    svc = app.dependency_overrides[get_service]()
    assert svc.history[-1] == {"role": "assistant", "content": "测试回答"}
