"""Project 05 —— LLM 抽象层测试。

``DeepSeekLLM`` 的用例全部用**假 client 注入**跑：真实 HTTP 那一条留给
demos/ 里的真实链路，单测不联网，这是本项目一直坚持的原则。
"""

from __future__ import annotations

import json

import pytest

from agent.errors import LLMError, LLMResponseError
from agent.llm import DeepSeekLLM, FakeLLM, LLMMessage, RecordingLLM, ScriptedLLM
from agent.settings import AgentSettings
from agent.tools import ToolCall


class _Resp:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self) -> dict:
        return self._payload


class _Client:
    """假 httpx client，只记录请求并把预设响应返回。"""

    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: list[dict] = []

    def post(self, url, json=None, headers=None, **kw):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        return _Resp(self.payload, self.status)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _message(**kw) -> dict:
    return {"role": "assistant", "content": "hi", **kw}


# --------------------------------------------------------------------------
# FakeLLM
# --------------------------------------------------------------------------
def test_fake_llm_records_every_roundtrip() -> None:
    fake = FakeLLM(responder=lambda messages, tools: LLMMessage(role="assistant", content="ok"))
    fake.chat([LLMMessage(role="user", content="问"), LLMMessage(role="tool", content="结果", tool_call_id="c1")])
    fake.chat([LLMMessage(role="user", content="再问")])
    assert fake.call_count == 2
    assert [m.role for m in fake.calls[0]] == ["user", "tool"]


def test_fake_llm_script_exhausted_raises() -> None:
    fake = ScriptedLLM(LLMMessage(role="assistant", content="只有一条"))
    fake.chat([LLMMessage(role="user", content="问")])
    with pytest.raises(LLMError, match="脚本已耗尽"):
        fake.chat([LLMMessage(role="user", content="再来一次")])


def test_fake_llm_rejects_empty_reply_when_tools_declared() -> None:
    """声明了工具却返回空消息，是剧本写错，要当场拦住而不是等到真机。"""
    fake = ScriptedLLM(LLMMessage(role="assistant"))
    with pytest.raises(LLMError, match="既没有 content 也没有 tool_calls"):
        fake.chat([LLMMessage(role="user", content="问")], tools=[{"name": "add"}])


def test_recording_llm_wraps_inner() -> None:
    inner = FakeLLM(responder=lambda m, t: LLMMessage(role="assistant", content="ok"))
    rec = RecordingLLM(inner)
    rec.chat([LLMMessage(role="user", content="问")], tools=None)
    assert rec.inner is inner
    assert len(rec.transcript) == 1
    assert rec.transcript[0][2].content == "ok"


# --------------------------------------------------------------------------
# 消息序列化
# --------------------------------------------------------------------------
def test_message_to_dict_serializes_arguments_as_string() -> None:
    """协议要求 arguments 是 JSON 字符串，不是对象 —— 这条最容易记错。"""
    msg = LLMMessage(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="c1", name="add", arguments={"a": 1})],
    )
    payload = msg.to_dict()
    assert payload["role"] == "assistant"
    assert "content" not in payload, "要调工具时 content 必须省略（不是空字符串）"
    assert payload["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'


def test_tool_message_carries_call_id() -> None:
    msg = LLMMessage(role="tool", content="1024", tool_call_id="c1", name="calculator")
    payload = msg.to_dict()
    assert payload == {"role": "tool", "content": "1024", "tool_call_id": "c1", "name": "calculator"}


# --------------------------------------------------------------------------
# DeepSeekLLM
# --------------------------------------------------------------------------
def test_deepseek_llm_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_TEST_KEY", raising=False)
    with pytest.raises(LLMError, match="AGENT_TEST_KEY.*为空"):
        DeepSeekLLM(AgentSettings(api_key_env="AGENT_TEST_KEY"))


def test_deepseek_llm_parses_tool_calls(keyed_settings) -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
                        }
                    ],
                }
            }
        ]
    }
    client = _Client(payload)
    llm = DeepSeekLLM(keyed_settings, http_client=client)

    reply = llm.chat(
        [LLMMessage(role="user", content={"a": 1, "b": 2})],
        tools=[{"type": "function", "function": {"name": "add"}}],
    )

    assert reply.tool_calls is not None and reply.tool_calls[0].name == "add"
    assert reply.tool_calls[0].arguments == {"a": 1, "b": 2}
    sent = client.calls[0]["json"]
    assert sent["tools"] == [{"type": "function", "function": {"name": "add"}}]
    # 鉴权头曾经漏过一次，服务端只回 401，离线 mock 完全看不出来
    assert client.calls[0]["headers"].get("Authorization", "").startswith("Bearer sk-test")
    assert sent["tool_choice"] == "auto"
    assert sent["messages"][0]["role"] == "user"


def test_deepseek_llm_keeps_function_wrapper(keyed_settings) -> None:
    """拆掉 "type": "function" 外层会触发 422，这里钉死行为。"""
    payload = {"choices": [{"message": _message(content="done")}]}
    client = _Client(payload)
    DeepSeekLLM(keyed_settings, http_client=client).chat(
        [LLMMessage(role="user", content="hi")],
        tools=[{"type": "function", "function": {"name": "add", "description": "", "parameters": {}}}],
    )
    # 声明必须原样透传，外层 "type": "function" 不能丢（丢了服务端 422）
    assert client.calls[0]["json"]["tools"] == [
        {"type": "function", "function": {"name": "add", "description": "", "parameters": {}}}
    ]


def test_deepseek_llm_rejects_empty_response(keyed_settings) -> None:
    client = _Client({"choices": [{"message": {"role": "assistant", "content": None}}]})
    with pytest.raises(LLMResponseError, match="既无内容也无工具调用"):
        DeepSeekLLM(keyed_settings, http_client=client).chat([LLMMessage(role="user", content="hi")])


def test_deepseek_llm_propagates_non_200(keyed_settings) -> None:
    client = _Client({"error": "bad"}, status=400)
    with pytest.raises(LLMError, match="HTTP 400"):
        DeepSeekLLM(keyed_settings, http_client=client).chat([LLMMessage(role="user", content="hi")])


def test_tool_call_without_id_is_rejected(keyed_settings) -> None:
    """缺 id 就无法把结果对应回去，必须在解析阶段拦住。"""
    payload = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"function": {"name": "add", "arguments": "{}"}}]}}]}
    with pytest.raises(LLMResponseError, match="缺少 id"):
        DeepSeekLLM(keyed_settings, http_client=_Client(payload)).chat([LLMMessage(role="user", content="hi")])


def test_tool_call_without_name_is_rejected(keyed_settings) -> None:
    payload = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "function": {"arguments": "{}"}}]}}]}
    with pytest.raises(LLMResponseError, match="缺少 function.name"):
        DeepSeekLLM(keyed_settings, http_client=_Client(payload)).chat([LLMMessage(role="user", content="hi")])


def test_malformed_arguments_json_is_rejected(keyed_settings) -> None:
    payload = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "function": {"name": "add", "arguments": "{oops"}}]}}]}
    with pytest.raises(LLMResponseError, match="不是合法 JSON"):
        DeepSeekLLM(keyed_settings, http_client=_Client(payload)).chat([LLMMessage(role="user", content="hi")])
