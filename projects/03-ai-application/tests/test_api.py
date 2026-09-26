"""接入层集成测试（milestones/04、09）。

原则：HTTP 路径走真实代码，模型层换成 Fake。
**故意不触发 lifespan**（不用 `with TestClient(...)`）——
lifespan 会去读真实配置，测试必须能在没有 Key 的机器上跑。
"""

import json

from fastapi.testclient import TestClient

from assistant.api import create_app, get_service
from assistant.client import FakeClient
from assistant.service import ChatService
from assistant.settings import Settings


def _client(script=None, reply="固定回答") -> tuple[TestClient, ChatService]:
    service = ChatService(
        client=FakeClient(script=script, reply=reply),
        settings=Settings(api_key="test-key"),
        system_prompt="你是测试助手。",
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app), service


def test_health():
    client, _ = _client()
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_reply():
    client, _ = _client(reply="你好")
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "你好"


def test_chat_rejects_empty_message():
    client, _ = _client()
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_stream_is_sse_and_terminates():
    client, _ = _client(reply="流")
    resp = client.post("/chat/stream", json={"message": "hi"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert body.startswith("data: ")
    assert "data: [DONE]" in body
    assert json.loads(body.split("data: ")[1].split("\n\n")[0])["delta"] == "流"


def test_structured_endpoint():
    client, _ = _client(script=[
        {"role": "assistant",
         "content": '{"name": "小明", "skills": ["Java"], "years": 6, "summary": "后端工程师"}'},
    ])
    resp = client.post("/chat/structured", json={"message": "我叫小明，会 Java，6 年经验",
                                                 "schema_name": "skill"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "小明" and data["years"] == 6


def test_structured_unknown_schema_is_400():
    client, _ = _client()
    resp = client.post("/chat/structured", json={"message": "x", "schema_name": "nope"})
    assert resp.status_code == 400


def test_agent_endpoint_runs_tool():
    client, _ = _client(script=[
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "c1", "type": "function",
            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
        }]},
        {"role": "assistant", "content": "答案是 3"},
    ])
    resp = client.post("/chat/agent", json={"message": "1 加 2"})
    assert resp.status_code == 200
    assert "3" in resp.json()["reply"]


def test_sessions_are_isolated_over_http():
    client, service = _client(reply="ok")
    client.post("/chat", json={"message": "我是 A，喜欢 Java", "session_id": "A"})
    client.post("/chat", json={"message": "我是 B，喜欢 Go", "session_id": "B"})

    a = str(service.sessions.get("A").to_messages())
    b = str(service.sessions.get("B").to_messages())
    assert "Java" in a and "Go" not in a
    assert "Go" in b and "Java" not in b


def test_reset_clears_history():
    client, service = _client()
    client.post("/chat", json={"message": "记住我", "session_id": "S"})
    assert service.sessions.get("S").turns
    assert client.post("/reset", params={"session_id": "S"}).json() == {"reset": "S"}
    assert service.sessions.get("S").turns == []
