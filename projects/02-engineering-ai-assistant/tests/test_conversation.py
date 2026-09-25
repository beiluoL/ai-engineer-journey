"""Conversation 的单元测试（对应 milestones/00 与挑战 2）。"""

from assistant.conversation import Conversation


def test_initial_messages_contains_only_system():
    conv = Conversation(system_prompt="你是助手")
    assert conv.messages == [{"role": "system", "content": "你是助手"}]
    assert len(conv) == 0


def test_add_user_and_assistant():
    conv = Conversation(system_prompt="sys")
    conv.add_user("问题")
    conv.add_assistant("回答")
    assert conv.messages == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "回答"},
    ]
    assert len(conv) == 2


def test_messages_returns_copy_not_reference():
    """关键：外部改返回值不能影响内部状态（封装）。"""
    conv = Conversation(system_prompt="sys")
    snapshot = conv.messages
    snapshot.append({"role": "user", "content": "偷偷加的"})
    assert len(conv.messages) == 1          # 内部没被污染
    assert len(snapshot) == 2               # 只有副本变了


def test_clear_keeps_system_prompt():
    conv = Conversation(system_prompt="sys")
    conv.add_user("a")
    conv.clear()
    assert conv.messages == [{"role": "system", "content": "sys"}]


def test_token_estimate_grows_with_content():
    conv = Conversation(system_prompt="sys")
    before = conv.token_estimate()
    conv.add_user("一" * 100)
    assert conv.token_estimate() > before


def test_trim_drops_oldest_and_keeps_system():
    conv = Conversation(system_prompt="sys")
    for i in range(10):
        conv.add_user("用户消息" * 50 + str(i))
        conv.add_assistant("助手回复" * 50 + str(i))

    dropped = conv.trim(max_tokens=200)

    assert dropped > 0
    assert conv.messages[0]["role"] == "system"      # system 永远保留
    assert len(conv.messages) < 21                    # 确实被裁剪了


def test_each_instance_has_own_state():
    """坑 2 的回归测试：类属性不能被所有实例共享。"""
    a, b = Conversation(system_prompt="a"), Conversation(system_prompt="b")
    a.add_user("只给 a")
    assert len(a.messages) == 2
    assert len(b.messages) == 1
