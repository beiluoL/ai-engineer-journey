"""Project 03 练习 03 参考答案：Memory、Token、Tools 与架构（纯离线）。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient

from assistant.agent import run_agent
from assistant.api import create_app, get_service
from assistant.client import FakeClient
from assistant.errors import ToolLoopError
from assistant.memory import Conversation, SessionStore
from assistant.service import build_service
from assistant.settings import Settings
from assistant.tokens import Budget, cost_cny, estimate_messages_tokens, estimate_tokens
from assistant.tools import REGISTRY, dispatch, schemas, tool


def _pass(qid: str, note: str) -> None:
    print(f"[PASS] {qid} {note}")


def a1() -> None:
    qid = "A1"
    store = SessionStore(system_prompt="离线助手")
    a = store.get("A")
    b = store.get("B")
    a.add_user("喜欢 Java")
    b.add_user("喜欢 Go")
    assert store.get("A") is a and store.get("B") is b
    assert "Java" in str(a.to_messages()) and "Java" not in str(b.to_messages())
    assert "Go" in str(b.to_messages()) and "Go" not in str(a.to_messages())
    store.reset("A")
    new_a = store.get("A")
    assert new_a is not a and new_a.turns == []
    assert "Go" in str(store.get("B").to_messages())
    _pass(qid, f"会话数={len(store.ids())}，reset 后 A 有 {len(new_a.turns)} 条、B 有 {len(b.turns)} 条")


def a2() -> None:
    qid = "A2"
    conv = Conversation(system_prompt="固定人设")
    for index in range(12):
        conv.add_user(f"第 {index} 轮问题：" + "上下文" * 12)
        conv.add_assistant(f"第 {index} 轮回答：" + "细节" * 12)
    final_user = "必须保留的最后问题"
    conv.add_user(final_user)
    before_tokens = conv.tokens()
    before_count = len(conv.turns)
    dropped = conv.trim_to_budget(120)
    after_messages = conv.to_messages()
    after_tokens = conv.tokens()
    assert dropped > 0 and len(conv.turns) < before_count
    assert after_messages[0] == {"role": "system", "content": "固定人设"}
    assert after_messages[-1] == {"role": "user", "content": final_user}
    assert after_tokens < before_tokens
    _pass(qid, f"裁剪 {dropped} 条，token 估值从 {before_tokens} 降到 {after_tokens}")


def a3() -> None:
    qid = "A3"
    conv = Conversation(system_prompt="固定 system")
    conv.add_user("你好")
    conv.add_assistant("你好，有什么可以帮你？")
    from_conv = conv.tokens()
    from_function = estimate_messages_tokens(conv.to_messages())
    assert from_conv == from_function
    conv.clear()
    messages = conv.to_messages()
    assert conv.turns == []
    assert messages == [{"role": "system", "content": "固定 system"}]
    _pass(qid, f"两条路径估值同为 {from_conv}，clear 后仍保留 {len(messages)} 条 system 消息")


def _manual_estimate(text: str) -> int:
    if not text:
        return 0
    cjk = sum(
        1
        for char in text
        if "\u4e00" <= char <= "\u9fff"
        or "\u3040" <= char <= "\u30ff"
        or "\uac00" <= char <= "\ud7af"
    )
    other = len(text) - cjk
    return int(cjk * 0.9 + other / 3.5) + 1


def b1() -> None:
    qid = "B1"
    samples = ["", "你好世界", "hello world", "AI 应用 v3"]
    actual = {text: estimate_tokens(text) for text in samples}
    expected = {text: _manual_estimate(text) for text in samples}
    assert actual == expected
    assert actual[""] == 0
    _pass(qid, f"四组真实估值为 {[actual[text] for text in samples]}")


def b2() -> None:
    qid = "B2"
    messages = [{"role": "user", "content": "你好"}]
    message_tokens = estimate_messages_tokens(messages)
    content_tokens = estimate_tokens("你好")
    assert message_tokens > content_tokens
    budget = Budget(context_window=1000, reserved_output=200, history_ratio=0.5)
    assert budget.history_budget == 400
    assert budget.check(400) == "ok"
    assert budget.check(401) == "trim"
    assert budget.check(801) == "overflow"
    _pass(qid, f"content={content_tokens}、完整消息={message_tokens}；历史预算={budget.history_budget}")


def b3() -> None:
    qid = "B3"
    tokens = 250_000
    input_cost = cost_cny("deepseek-chat", tokens, 0)
    output_cost = cost_cny("deepseek-chat", 0, tokens)
    fallback_cost = cost_cny("unknown-model", tokens, tokens)
    assert output_cost > input_cost > 0
    assert fallback_cost == input_cost + output_cost
    _pass(qid, f"{tokens} tokens：输入 ¥{input_cost:.4f}、输出 ¥{output_cost:.4f}、默认合计 ¥{fallback_cost:.4f}")


def c1() -> None:
    qid = "C1"
    add_schema = next(schema for schema in schemas() if schema["function"]["name"] == "add")
    parameters = add_schema["function"]["parameters"]
    assert parameters["properties"]["a"]["type"] == "number"
    assert parameters["properties"]["b"]["type"] == "number"
    assert set(parameters["required"]) == {"a", "b"}

    @tool
    def greet(name: str, punctuation: str = "!") -> str:
        """生成一句问候。"""
        return f"你好，{name}{punctuation}"

    try:
        custom = next(schema for schema in schemas() if schema["function"]["name"] == "greet")
        required = custom["function"]["parameters"]["required"]
        assert required == ["name"]
        assert custom["function"]["parameters"]["properties"]["punctuation"]["type"] == "string"
    finally:
        REGISTRY.pop("greet", None)
    _pass(qid, f"add 有 {len(parameters['properties'])} 个 number 参数；临时工具 required={required}")


def c2() -> None:
    qid = "C2"
    added = dispatch("add", '{"a": 2, "b": 3}')
    multiplied = dispatch("multiply", '{"a": 4, "b": 5}')
    failures = [
        dispatch("add", "不是 JSON"),
        dispatch("add", '{"a": 1}'),
        dispatch("no_such_tool", "{}"),
    ]
    assert added["result"] == 5.0
    assert multiplied["result"] == 20.0
    assert all("error" in failure for failure in failures)
    _pass(qid, f"成功结果={added['result']}/{multiplied['result']}，{len(failures)} 类失败均返回 error")


def _tool_call(name: str, arguments: dict, call_id: str = "call-1") -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        }],
    }


def c3() -> None:
    qid = "C3"
    client = FakeClient(script=[
        _tool_call("add", {"a": 128, "b": 37}, "sum-7"),
        {"role": "assistant", "content": "结果是 165"},
    ])
    answer, trace = asyncio.run(run_agent(client, [{"role": "user", "content": "128 加 37"}]))
    tool_messages = [message for message in trace if message.get("role") == "tool"]
    second_request = client.calls[1]["messages"]
    assert answer == "结果是 165"
    assert len(client.calls) == 2 and len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "sum-7"
    assert json.loads(tool_messages[0]["content"])["result"] == 165.0
    assert any(message.get("role") == "tool" for message in second_request)
    _pass(qid, f"工具循环请求 {len(client.calls)} 次，回灌 id={tool_messages[0]['tool_call_id']}")


def c4() -> None:
    qid = "C4"
    limit = 3
    client = FakeClient(script=[_tool_call("add", {"a": 1, "b": 2}, f"call-{i}") for i in range(10)])
    try:
        asyncio.run(run_agent(client, [{"role": "user", "content": "一直调用"}], max_iterations=limit))
    except ToolLoopError as exc:
        assert str(limit) in str(exc)
    else:
        raise AssertionError("超过工具循环上限时应抛 ToolLoopError")
    assert len(client.calls) == limit
    _pass(qid, f"达到上限 {limit} 后抛 ToolLoopError，实际调用次数={len(client.calls)}")


def d1() -> None:
    qid = "D1"
    fake = FakeClient(reply="离线固定回答")
    service = build_service(Settings(api_key="offline-test"), fake)

    async def scenario() -> tuple[str, str]:
        first = await service.ask("第一问")
        second = await service.ask("第二问")
        return first, second

    first, second = asyncio.run(scenario())
    second_messages = fake.calls[1]["messages"]
    assert first == second == "离线固定回答"
    assert service.client is fake
    assert service.usage.calls == 2
    assert [message["content"] for message in second_messages[-3:]] == ["第一问", "离线固定回答", "第二问"]
    _pass(qid, f"注入 FakeClient 后调用 {service.usage.calls} 次，第二次请求带 {len(second_messages)} 条消息")


def d2() -> None:
    qid = "D2"
    service = build_service(Settings(api_key="offline-test"), FakeClient(reply="HTTP 离线回答"))
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    try:
        health = client.get("/health")
        chat = client.post("/chat", json={"message": "你好", "session_id": "S"})
        empty = client.post("/chat", json={"message": "", "session_id": "S"})
        reset = client.post("/reset", params={"session_id": "S"})
        assert health.status_code == 200 and health.json() == {"status": "ok"}
        assert chat.status_code == 200 and chat.json()["reply"] == "HTTP 离线回答"
        assert empty.status_code == 422
        assert reset.status_code == 200 and reset.json() == {"reset": "S"}
        assert service.sessions.get("S").turns == []
    finally:
        client.close()
        app.dependency_overrides.clear()
    _pass(qid, f"HTTP 状态为 health={health.status_code}、chat={chat.status_code}、empty={empty.status_code}、reset={reset.status_code}")


def main() -> None:
    for answer in (a1, a2, a3, b1, b2, b3, c1, c2, c3, c4, d1, d2):
        answer()


if __name__ == "__main__":
    main()
