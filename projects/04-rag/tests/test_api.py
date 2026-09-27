"""api.py：Web 接入层（13 章）。

这一层不该有业务逻辑，所以测的是三件事：
    1. 路由与状态码（422 校验、200 结构）
    2. SSE 的**帧序列**（顺序对不对、拼接结果对不对）
    3. 依赖注入取到的确实是注入的那个 service（而不是又装配了一遍）
全程离线：RAG_FAKE=1，走 FakeEmbeddingClient + FakeLLMClient。
"""

from __future__ import annotations

import json
import os

os.environ["RAG_FAKE"] = "1"          # 必须在 import rag.api 之前就位
os.environ.pop("RAG_SESSIONS_DIR", None)   # 17 章：默认纯内存，别把测试写进仓库

from fastapi.testclient import TestClient  # noqa: E402

from rag.api import create_app  # noqa: E402
from rag.llm import FakeLLMClient  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app(["data/"]))


def test_health():
    with _client() as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_stats报告索引规模():
    with _client() as c:
        data = c.get("/stats").json()
    assert data["chunks"] > 0
    assert data["embedding_model"]


def test_ask返回答案与引用():
    with _client() as c:
        r = c.post("/ask", json={"query": "生成器为什么能省内存？"})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"]
    assert data["context_tokens"] > 0
    assert data["refused"] is False
    assert data["citations"]


def test_ask拒绝空query():
    with _client() as c:
        r = c.post("/ask", json={"query": ""})
    assert r.status_code == 422


def test_ask_stream的帧序列与拼接结果():
    with _client() as c:
        with c.stream("POST", "/ask/stream", json={"query": "生成器为什么能省内存？"}) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            payloads = [ln.removeprefix("data: ").strip()
                        for ln in resp.iter_lines()
                        if ln.startswith("data: ") and ln != "data: [DONE]"]
    events = [json.loads(p) for p in payloads]
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "retrieved"
    assert kinds[-1] == "done"
    assert "delta" in kinds
    # 逐帧增量累加 == done 里的完整答案
    joined = "".join(e["text"] for e in events if e["kind"] == "delta")
    assert joined == events[-1]["answer"]
    assert events[0]["sources"]


def test_index可以重新入库():
    with _client() as c:
        before = c.get("/stats").json()["chunks"]
        r = c.post("/index", json={"paths": ["data/"]})
    assert r.status_code == 200
    assert r.json()["files_ok"] > 0
    assert r.json()["chunks"] >= before


# —— 17 章：会话与多轮 ——

def test_sessions端点全流程():
    with _client() as c:
        created = c.post("/sessions", json={"title": "写一个会话"})
        assert created.status_code == 200
        sid = created.json()["id"]
        assert created.json()["turn_count"] == 0

        listed = c.get("/sessions").json()
        assert [s["id"] for s in listed] == [sid]
        assert listed[0]["title"] == "写一个会话"

        detail = c.get(f"/sessions/{sid}").json()
        assert detail["turns"] == []

        renamed = c.patch(f"/sessions/{sid}", json={"title": "改过的名字"})
        assert renamed.status_code == 200 and renamed.json()["title"] == "改过的名字"

        deleted = c.delete(f"/sessions/{sid}")
        assert deleted.status_code == 200 and deleted.json()["status"] == "deleted"
        assert c.get("/sessions").json() == []
        assert c.get(f"/sessions/{sid}").status_code == 404


def test_访问不存在的会话返回404():
    with _client() as c:
        assert c.get("/sessions/deadbeef").status_code == 404


def test_ask带session_id会把问答记进历史():
    with _client() as c:
        sid = c.post("/sessions", json={}).json()["id"]
        first = c.post("/ask", json={"query": "生成器为什么能省内存？",
                                     "session_id": sid})
        assert first.status_code == 200
        sid_back = first.json()["session_id"]
        assert sid_back == sid and first.json()["turn_id"]
        turns = c.get(f"/sessions/{sid}").json()["turns"]
        assert len(turns) == 2                       # 一条 user + 一条 assistant
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"
        # 引用挂在助手那一轮上，前端渲染时直接拿得到
        assert turns[1]["sources"]


def test_ask不带session_id时不产生会话():
    with _client() as c:
        r = c.post("/ask", json={"query": "生成器为什么能省内存？"})
        assert r.json().get("session_id") is None
        assert c.get("/sessions").json() == []


def test_stream带session_id时done事件带回会话信息():
    with _client() as c:
        sid = c.post("/sessions", json={}).json()["id"]
        with c.stream("POST", "/ask/stream",
                      json={"query": "生成器为什么能省内存？", "session_id": sid}) as resp:
            assert resp.status_code == 200
            events = [json.loads(ln.removeprefix("data: ").strip()) for ln in resp.iter_lines()
                      if ln.startswith("data: ") and ln != "data: [DONE]"]
    assert events[0]["kind"] == "retrieved"
    assert events[-1]["kind"] == "done"
    done = events[-1]
    assert done["session_id"] == sid
    assert done["turn_id"]            # 客户端拿到它就能定位这一轮
    turns = c.get(f"/sessions/{sid}").json()["turns"]
    assert len(turns) == 2 and turns[0]["content"] == "生成器为什么能省内存？"
    assert "".join(e["text"] for e in events if e["kind"] == "delta") == done["answer"]


def test_stream用非法session_id直接404():
    with _client() as c:
        with c.stream("POST", "/ask/stream",
                      json={"query": "生成器为什么能省内存？", "session_id": "nope"}) as resp:
            assert resp.status_code == 404


def test_service来自dependency而不是重新装配():
    """注入进 app.state 的 service 就是被测的那个：它认得注入的 LLM 替身。"""
    from rag.pipeline import RAGService

    app = create_app(["data/"])
    with TestClient(app) as c:
        service = c.app.state.service
        assert isinstance(service, RAGService)
        # 15 章起 LLM 外面包了一层计量壳，穿透 .inner 才能看到真正用的是哪个实现
        assert isinstance(getattr(service._llm, "inner", service._llm), FakeLLMClient)
        # 同一进程内多次请求复用同一个 service（否则每次都要重建索引）
        first = c.post("/ask", json={"query": "生成器为什么能省内存？"}).json()
        second = c.post("/ask", json={"query": "生成器为什么能省内存？"}).json()
    assert first["answer"] == second["answer"]
