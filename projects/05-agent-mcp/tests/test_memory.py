"""memory 模块 —— 工作记忆与草稿纸。

重点验证三件事：

1. ``trim_history`` 不会产出「孤儿 tool 消息」—— 这是最容易写错、
   而且**只有真发请求才会暴露**（本地 mock 不校验协议）的一类 bug。
2. system 与首条 user 问题永不裁剪。
3. Scratchpad 写在循环之外：历史被裁没了，笔记还在。
"""

from __future__ import annotations

import pytest

from agent.llm import LLMMessage
from agent.memory import (
    TRIMMED_MARK,
    Scratchpad,
    estimate_messages_tokens,
    estimate_tokens,
    trim_history,
)
from agent.tools import ToolCall


# --------------------------------------------------------------------- 估算
class TestEstimate:
    def test_empty_is_zero(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0  # type: ignore[arg-type]

    def test_chinese_costs_more_than_ascii(self):
        """这条是这个估算函数存在的理由：按字符数会严重低估中文。"""
        ascii_text = "a" * 100
        chinese = "中" * 100
        assert estimate_tokens(chinese) > estimate_tokens(ascii_text) * 3

    def test_messages_count_roles(self):
        msgs = [
            LLMMessage(role="system", content="s"),
            LLMMessage(role="user", content="你好"),
        ]
        total = estimate_messages_tokens(msgs)
        assert total >= estimate_tokens("s") + estimate_tokens("你好")

    def test_tool_calls_are_counted(self):
        call = ToolCall(id="c1", name="rag_search", arguments={"query": "Project 04 会话"})
        with_call = [LLMMessage(role="assistant", content="", tool_calls=[call])]
        without = [LLMMessage(role="assistant", content="")]
        assert estimate_messages_tokens(with_call) > estimate_messages_tokens(without)


# --------------------------------------------------------------------- 裁剪
def _long(text: str, times: int = 1) -> str:
    return text * times


def _three_rounds() -> list[LLMMessage]:
    """system + user + 三轮 assistant/tool。

    每轮工具结果做成约 120 字的中文本（约 120+ token）—— 用真实量级的数据，
    否则「压缩成占位」省下的那点 token 还不如每条消息 4 token 的固有开销，
    测试就测不到想测的分支。
    """
    msgs: list[LLMMessage] = [
        LLMMessage(role="system", content="工作规则"),
        LLMMessage(role="user", content="原始问题是什么"),
    ]
    for i in range(1, 4):
        call = ToolCall(id=f"c{i}", name="rag_search", arguments={"query": f"q{i}"})
        msgs.append(LLMMessage(role="assistant", content=f"第{i}步思考", tool_calls=[call]))
        msgs.append(
            LLMMessage(
                role="tool",
                content=_long(f"第{i}步的工具结果", 15),
                tool_call_id=f"c{i}",
                name="rag_search",
            )
        )
    return msgs


class TestTrimHistory:
    def test_under_budget_returns_copy_unchanged(self):
        msgs = _three_rounds()
        out = trim_history(msgs, budget=10**9)
        assert [m.content for m in out] == [m.content for m in msgs]
        # 必须是副本：原地返回同一个 list 会让调用方的后续 append 踩到共享状态
        assert out is not msgs

    def test_system_and_first_user_survive(self):
        out = trim_history(_three_rounds(), budget=10)
        roles = [m.role for m in out]
        assert roles[0] == "system"
        assert roles[1] == "user"
        assert out[1].content == "原始问题是什么"

    def test_no_orphan_tool_messages(self):
        """孤儿 tool 消息 = 服务端 400。

        协议要求的是**配对**：每条 tool 消息前面必须有带着对应 tool_call id 的
        assistant 消息。裁剪一旦只砍一半就炸 —— 而且这个错本地 mock 复现不出来。
        """
        out = trim_history(_three_rounds(), budget=300, keep_recent=1)
        pending_ids: set[str] = set()
        for m in out:
            if m.role == "assistant" and m.tool_calls:
                pending_ids.update(c.id for c in m.tool_calls)
            elif m.role == "tool":
                assert m.tool_call_id in pending_ids, (
                    f"tool 消息 {m.tool_call_id} 找不到前面的 assistant tool_call —— 这是孤儿消息"
                )
                pending_ids.discard(m.tool_call_id)

    def test_old_results_become_placeholder(self):
        out = trim_history(_three_rounds(), budget=350, keep_recent=2)
        placeholders = [m.content for m in out if m.role == "tool" and TRIMMED_MARK in (m.content or "")]
        assert len(placeholders) >= 1
        # 占位里要写明被省略了多少字符，模型才知道「有过但读不到」
        assert any("字符" in p for p in placeholders)

    def test_recent_steps_keep_full_text(self):
        """最近 keep_recent 步必须留原文 —— 那正是模型马上要引用的内容。"""
        out = trim_history(_three_rounds(), budget=300, keep_recent=1)
        tool_msgs = [m for m in out if m.role == "tool"]
        assert TRIMMED_MARK not in (tool_msgs[-1].content or "")

    def test_source_not_mutated(self):
        """裁剪不能改写原对象；Recorder 的 transcript 存的是同一批对象的引用。"""
        msgs = _three_rounds()
        snapshot = [m.content for m in msgs]
        trim_history(msgs, budget=300, keep_recent=1)
        assert [m.content for m in msgs] == snapshot

    def test_budget_zero_short_circuits(self):
        msgs = _three_rounds()
        assert trim_history(msgs, budget=0) == msgs

    def test_tiny_budget_drops_whole_rounds(self):
        """预算实在放不下时整轮丢弃 —— 但绝不能留孤儿 tool 消息。"""
        out = trim_history(_three_rounds(), budget=10)
        assert [m.role for m in out] == ["system", "user"]

    def test_respects_budget_when_possible(self):
        msgs = _three_rounds()
        out = trim_history(msgs, budget=300, keep_recent=1)
        assert estimate_messages_tokens(out) <= estimate_messages_tokens(msgs)


# --------------------------------------------------------------------- 草稿纸
class TestScratchpad:
    def test_write_then_read(self):
        pad = Scratchpad()
        pad.write("a", "内容A")
        assert pad.read("a") == "「a」：内容A"
        assert len(pad) == 1

    def test_read_all(self):
        pad = Scratchpad()
        pad.write("a", "1")
        pad.write("b", "2")
        text = pad.read()
        assert "a：1" in text and "b：2" in text

    def test_read_missing_key_lists_existing(self):
        pad = Scratchpad()
        pad.write("a", "1")
        msg = pad.read("没有的")
        assert "没有名为「没有的」的笔记" in msg and "a" in msg

    def test_empty_pad(self):
        assert "空的" in Scratchpad().read()

    def test_overwrite_reports_update(self):
        pad = Scratchpad()
        assert "已记下" in pad.write("a", "旧")
        assert "已更新" in pad.write("a", "新")
        assert pad.read("a") == "「a」：新"

    def test_empty_key_rejected(self):
        from agent.errors import ToolError

        pad = Scratchpad()
        with pytest.raises(ToolError, match="key 不能为空"):
            pad.write("  ", "值")

    def test_render_empty_returns_blank(self):
        """render 返回空串时 system 提示不该多出一段空行。"""
        assert Scratchpad().render() == ""

    def test_render_lists_notes(self):
        pad = Scratchpad()
        pad.write("p04", "原子写")
        rendered = pad.render()
        assert "草稿纸" in rendered and "p04" in rendered

    def test_empty_pad_is_falsy(self):
        """一个必须记住的 Python 坑。

        类里定义了 ``__len__`` 之后，空实例在布尔判断里就是**假值**。
        ``build_agent`` 里那句 ``if scratchpad:`` 曾经因此把刚建好的空草稿纸
        当成"没传"，草稿纸工具一个都没注册上。所以调用点一律写
        ``is not None`` —— 这条测试把这个约定钉住。
        """
        pad = Scratchpad()
        assert bool(pad) is False
        pad.write("a", "1")
        assert bool(pad) is True

    def test_clear_and_to_dict(self):
        pad = Scratchpad()
        pad.write("a", "1")
        assert pad.to_dict() == {"a": "1"}
        pad.clear()
        assert len(pad) == 0
        assert "a" not in pad

    def test_survives_history_trim(self):
        """这条是 Scratchpad 存在的理由：

        历史被裁到只剩占位之后，写在纸上的结论依然完整可读。
        """
        pad = Scratchpad()
        pad.write("p01_persistence", "Project 01 用 JSON 文件落盘")
        msgs = _three_rounds()
        trim_history(msgs, budget=300, keep_recent=1)
        assert pad.read("p01_persistence") == "「p01_persistence」：Project 01 用 JSON 文件落盘"
