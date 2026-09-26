"""会话记忆测试（milestones/02、05）。"""

import pytest

from assistant.memory import Conversation, SessionStore, validate_messages


def test_to_messages_puts_system_first_and_only_once():
    conv = Conversation(system_prompt="你是助手")
    conv.add_user("你好")
    msgs = conv.to_messages()
    assert msgs[0]["role"] == "system"
    assert sum(1 for m in msgs if m["role"] == "system") == 1


def test_assistant_reply_is_fed_back():
    """多轮对话的记忆来自「把 assistant 回复也发回去」。"""
    conv = Conversation(system_prompt="")
    conv.add_user("我叫小明")
    conv.add_assistant("你好小明")
    conv.add_user("我叫什么？")

    msgs = conv.to_messages()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert "小明" in msgs[1]["content"]


def test_to_messages_returns_copy():
    conv = Conversation(system_prompt="")
    conv.add_user("原文")
    msgs = conv.to_messages()
    msgs[0]["content"] = "被改了"
    assert conv.turns[0]["content"] == "原文"


def test_add_tool_requires_call_id():
    conv = Conversation()
    conv.add_assistant("", tool_calls=[{"id": "c1", "function": {"name": "add"}}])
    conv.add_tool("c1", '{"result": 3}')
    msg = conv.to_messages()[-1]
    assert msg["role"] == "tool" and msg["tool_call_id"] == "c1"


def test_validate_messages_rejects_bad_role():
    with pytest.raises(ValueError, match="role 非法"):
        validate_messages([{"role": "AI", "content": "hi"}])


def test_validate_messages_requires_tool_call_id():
    with pytest.raises(ValueError, match="tool_call_id"):
        validate_messages([{"role": "tool", "content": "结果"}])


def test_trim_keeps_system_and_last_user_input():
    conv = Conversation(system_prompt="人设" * 20)
    for i in range(30):
        conv.add_user(f"第{i}轮的问题" * 10)
        conv.add_assistant(f"第{i}轮的回答" * 10)

    dropped = conv.trim_to_budget(300)

    assert dropped > 0
    msgs = conv.to_messages()
    assert msgs[0]["role"] == "system"
    assert msgs[-1] == conv.turns[-1]      # 最后一轮保留
    assert len(conv.turns) < 60


def test_trim_is_noop_when_within_budget():
    conv = Conversation(system_prompt="人设")
    conv.add_user("你好")
    assert conv.trim_to_budget(10_000) == 0
    assert len(conv.turns) == 1


def test_sessions_are_isolated():
    """两个会话不能串味——共享会话是数据泄漏级 bug（Chapter 05 坑 3）。"""
    store = SessionStore(system_prompt="你是助手")
    a, b = store.get("A"), store.get("B")

    a.add_user("我是 A，喜欢 Java")
    b.add_user("我是 B，喜欢 Go")

    assert "Java" in str(a.to_messages())
    assert "Java" not in str(b.to_messages())
    assert "Go" in str(b.to_messages())
    assert "Go" not in str(a.to_messages())


def test_session_reset():
    store = SessionStore()
    store.get("A").add_user("x")
    store.reset("A")
    assert store.get("A").turns == []
