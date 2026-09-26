"""Agent 工具循环测试（milestones/08）。

重点验证「执行完必须回灌」——这是本章最容易漏的一步。
"""

import json

import pytest

from assistant.agent import run_agent
from assistant.client import FakeClient
from assistant.errors import ToolLoopError


def _call(name: str, args: dict, call_id: str = "c1") -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        }],
    }


async def test_agent_executes_tool_and_answers():
    client = FakeClient(script=[
        _call("add", {"a": 128, "b": 37}),
        {"role": "assistant", "content": "128 + 37 = 165"},
    ])
    answer, trace = await run_agent(client, [{"role": "user", "content": "128 加 37 是多少"}])

    assert "165" in answer
    # 轨迹里必须有 tool 消息，且带正确的 tool_call_id
    tool_msgs = [m for m in trace if m.get("role") == "tool"]
    assert tool_msgs and tool_msgs[0]["tool_call_id"] == "c1"
    assert json.loads(tool_msgs[0]["content"])["result"] == 165.0


async def test_result_is_fed_back_to_model():
    """第二次请求必须带上工具结果——只执行不回灌，模型就会瞎编。"""
    client = FakeClient(script=[
        _call("get_weather", {"city": "北京"}),
        {"role": "assistant", "content": "北京今天是晴，26 度"},
    ])
    await run_agent(client, [{"role": "user", "content": "北京天气"}])

    second_call = client.calls[1]["messages"]
    assert any(m.get("role") == "tool" for m in second_call)
    assert "26" in str(second_call)


async def test_unknown_tool_is_reported_back():
    """模型调了不存在的工具：作为错误回灌，模型通常能自我纠正。"""
    client = FakeClient(script=[
        _call("no_such", {}),
        {"role": "assistant", "content": "抱歉，没有这个工具"},
    ])
    answer, trace = await run_agent(client, [{"role": "user", "content": "x"}])
    assert "抱歉" in answer
    assert "error" in [m for m in trace if m.get("role") == "tool"][0]["content"]


async def test_loop_has_hard_limit():
    """没有上限的工具循环 = 没有上限的账单。"""
    client = FakeClient(script=[_call("add", {"a": 1, "b": 2}) for _ in range(10)])
    with pytest.raises(ToolLoopError):
        await run_agent(client, [{"role": "user", "content": "x"}], max_iterations=3)
    assert len(client.calls) == 3


async def test_no_tool_call_returns_directly():
    client = FakeClient(script=[{"role": "assistant", "content": "不需要工具"}])
    answer, trace = await run_agent(client, [{"role": "user", "content": "你好"}])
    assert answer == "不需要工具"
    assert len(trace) == 2


async def test_tools_are_sent_in_request():
    client = FakeClient(script=[{"role": "assistant", "content": "ok"}])
    await run_agent(client, [{"role": "user", "content": "北京天气"}])
    assert client.calls[0]["tools"], "请求里必须带上工具 schema"
