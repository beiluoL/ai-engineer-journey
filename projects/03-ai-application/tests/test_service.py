"""编排层测试（milestones/09）：四条路径 + 预算 + 会话隔离。"""

import json

import pytest
from pydantic import BaseModel

from assistant.client import FakeClient
from assistant.errors import ContextWindowError
from assistant.models import SkillExtraction
from assistant.service import build_service
from assistant.settings import Settings
from assistant.tokens import Budget


class Point(BaseModel):
    x: int
    y: int


async def test_ask_records_history(service):
    await service.ask("我叫小明")
    await service.ask("我叫什么？")

    # 第二轮请求里必须能看到第一轮的问答 —— 记忆是「发」出来的
    second = service.client.calls[1]["messages"]
    assert "小明" in str(second)
    assert service.usage.calls == 2


async def test_astream_feeds_back_full_reply(service):
    """流式结束后必须回灌完整内容，否则下一轮失忆。"""
    service.client.reply = "你好"
    chunks = [c async for c in service.astream("你好")]

    assert "".join(chunks) == "你好"
    assert service.sessions.get("default").turns[-1]["content"] == "你好"


async def test_ask_structured_returns_model(service):
    service.client.script = [
        {"role": "assistant", "content": '{"x": 1, "y": 2}'},
    ]
    point = await service.ask_structured("抽取坐标", Point)
    assert point.x == 1 and point.y == 2


async def test_context_window_error_when_too_long():
    """超出窗口必须明确报错，不能静默失败。"""
    settings = Settings(api_key="k", context_window=200)
    service = build_service(settings, FakeClient(reply="ok"))
    service.budget = Budget(context_window=200, reserved_output=50, history_ratio=0.5)

    conv = service.sessions.get("default")
    for i in range(50):
        conv.add_user("问题内容" * 40)

    with pytest.raises(ContextWindowError):
        await service.ask("再来一个问题")


async def test_sessions_do_not_leak(service):
    await service.ask("我是 A，喜欢 Java", session_id="A")
    await service.ask("我是 B，喜欢 Go", session_id="B")

    a = str(service.sessions.get("A").to_messages())
    b = str(service.sessions.get("B").to_messages())
    assert "Java" in a and "Go" not in a
    assert "Go" in b and "Java" not in b


async def test_run_agent_path(service):
    service.client.script = [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "c1", "type": "function",
            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
        }]},
        {"role": "assistant", "content": "答案是 3"},
    ]
    assert "3" in await service.run_agent("1 加 2")


async def test_usage_accumulates(service):
    class FakeWithUsage(FakeClient):
        last_usage = {"prompt_tokens": 10, "completion_tokens": 5}

    service.client = FakeWithUsage(reply="ok")
    await service.ask("一")
    await service.ask("二")
    assert service.usage.prompt_tokens == 20
    assert service.usage.completion_tokens == 10
    assert service.cost_so_far() > 0


def test_build_service_with_fake():
    service = build_service(Settings(api_key="k"), FakeClient())
    assert service.client is not None
