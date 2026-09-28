"""Milestone 05 —— 循环层面的三件事：重复闸门、工作记忆、草稿纸。

这些不是「多聊几轮」的问题，是**多步骤任务**才会暴露的问题：
  · 步骤一多，模型就容易重复同一个查询 —— 失败闸门看不见（它没报错）
  · 步骤一多，上下文就膨胀 —— 得裁，但裁错了会违反协议
  · 步骤一多，中间结论就得有地方放 —— 草稿纸
"""

from __future__ import annotations

import pytest

from agent.agent import AgentResult, ReActAgent
from agent.errors import AgentError, MaxStepsExceeded, RepeatedToolCall
from agent.llm import FakeLLM, LLMMessage, ScriptedLLM
from agent.memory import Scratchpad, TRIMMED_MARK
from agent.registry import ToolRegistry
from agent.settings import AgentSettings
from agent.tools import ReadNotesTool, ToolCall, WriteNoteTool, default_tools


def _registry(pad: Scratchpad | None = None) -> ToolRegistry:
    return ToolRegistry(default_tools(pad))


def _search(query: str, cid: str = "c1") -> LLMMessage:
    return LLMMessage(
        role="assistant",
        tool_calls=[ToolCall(id=cid, name="rag_search", arguments={"query": query})],
    )


def _answer(text: str = "答案") -> LLMMessage:
    return LLMMessage(role="assistant", content=text)


# ------------------------------------------------------------ 第三道闸门
class TestRepeatGuard:
    def test_identical_call_stops_the_loop(self):
        """同一个查询反复调：失败闸门不会涨，只有重复闸门能拦。"""
        llm = ScriptedLLM(_search("同一个问题"), _search("同一个问题"), _search("同一个问题"))
        with pytest.raises(RepeatedToolCall, match="已被调用 3 次"):
            ReActAgent(llm, _registry(), settings=AgentSettings(max_repeats=2)).run("问题")

    def test_allows_configured_times(self):
        """前 max_repeats 次是允许的 —— 换个参数重试本来就该被 toler待。"""
        llm = ScriptedLLM(_search("同一个问题", "c1"), _search("同一个问题", "c2"), _answer("好了"))
        result = ReActAgent(llm, _registry(), settings=AgentSettings(max_repeats=2)).run("问题")
        assert result.answer == "好了"

    def test_argument_order_does_not_matter(self):
        """{"a":1,"b":2} 和 {"b":2,"a":1} 是同一个签名。

        用 sort_keys=True 序列化就是为这个 —— 否则模型换个键顺序就被算成新调用，
        闸门形同虚设。
        """
        llm = ScriptedLLM(
            LLMMessage(role="assistant", tool_calls=[ToolCall(id="c1", name="rag_search", arguments={"query": "q", "k": 3})]),
            LLMMessage(role="assistant", tool_calls=[ToolCall(id="c2", name="rag_search", arguments={"k": 3, "query": "q"})]),
            LLMMessage(role="assistant", tool_calls=[ToolCall(id="c3", name="rag_search", arguments={"query": "q", "k": 3})]),
        )
        with pytest.raises(RepeatedToolCall, match="已被调用 3 次"):
            ReActAgent(llm, _registry(), settings=AgentSettings(max_repeats=2)).run("问题")

    def test_different_arguments_are_not_repeats(self):
        llm = ScriptedLLM(_search("A", "c1"), _search("B", "c2"), _search("C", "c3"), _answer("汇总完了"))
        result = ReActAgent(llm, _registry(), settings=AgentSettings(max_repeats=2)).run("对比 A B C")
        assert result.answer == "汇总完了"

    def test_repeat_guard_shorter_than_max_steps(self):
        """重复闸门要**先于**步数闸门触发 —— 否则它只是多烧几次钱的装饰品。"""
        def same_call(messages, tools):
            return LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="c", name="rag_search", arguments={"query": "固定"})],
            )

        with pytest.raises(RepeatedToolCall):
            ReActAgent(
                FakeLLM(responder=same_call),
                _registry(),
                settings=AgentSettings(max_steps=8, max_repeats=2),
            ).run("问题")

    def test_is_agent_error_subclass(self):
        assert issubclass(RepeatedToolCall, AgentError)


# ------------------------------------------------------------ 草稿纸在循环里
class TestScratchpadInLoop:
    def test_note_tools_share_one_pad(self):
        """在同一张纸上写和读 —— 两个工具各 new 一张就不通了。"""
        pad = Scratchpad()
        reg = ToolRegistry([WriteNoteTool(pad), ReadNotesTool(pad)])
        reg.call(ToolCall(id="w", name="write_note", arguments={"key": "k", "value": "事实"}))
        result = reg.call(ToolCall(id="r", name="read_notes", arguments={"key": "k"}))
        assert "事实" in result.output

    def test_notes_survive_to_result(self):
        pad = Scratchpad()
        llm = ScriptedLLM(
            LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="w", name="write_note", arguments={"key": "p04", "value": "原子写 mkstemp+fsync+os.replace"})],
            ),
            _answer("记下了"),
        )
        agent = ReActAgent(llm, _registry(pad), scratchpad=pad)
        result = agent.run("问题")
        assert result.notes["p04"] == "原子写 mkstemp+fsync+os.replace"
        assert result.used_scratchpad is True

    def test_notes_are_injected_into_system_prompt(self):
        """笔记要常驻 system —— 省掉一轮 read_notes 的往返就等于省钱。"""
        pad = Scratchpad()
        pad.write("p01", "JSON 文件落盘")
        llm = ScriptedLLM(_answer("答"))
        ReActAgent(llm, _registry(pad), scratchpad=pad).run("问题")
        first_round_system = llm.calls[0][0]
        assert "p01" in first_round_system.content

    def test_empty_pad_does_not_pollute_prompt(self):
        pad = Scratchpad()
        llm = ScriptedLLM(_answer("答"))
        agent = ReActAgent(llm, _registry(pad), scratchpad=pad, system_prompt="工作规则")
        agent.run("问题")
        assert llm.calls[0][0].content == "工作规则"

    def test_build_agent_with_scratchpad_registers_tools(self):
        from agent.agent import build_agent

        agent = build_agent(scratchpad=True)
        assert "write_note" in agent.registry.names()
        assert "read_notes" in agent.registry.names()
        assert agent.scratchpad is not None

    def test_trace_shows_notes(self):
        pad = Scratchpad()
        llm = ScriptedLLM(
            LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="w", name="write_note", arguments={"key": "结论", "value": "值"})],
            ),
            _answer("汇总"),
        )
        result = ReActAgent(llm, _registry(pad), scratchpad=pad).run("多步骤问题")
        assert "草稿纸" in result.trace()
        assert "结论" in result.trace()

    def test_to_dict_carries_notes(self):
        pad = Scratchpad()
        result = AgentResult(answer="a", notes={"k": "v"})
        assert result.to_dict()["notes"] == {"k": "v"}


# ------------------------------------------------------------ 工作记忆裁剪
class TestWorkingMemoryInLoop:
    # 这里故意用一个**很短**的 system_prompt：默认那段工作规则有近 200 token，
    # 会把预算的天平压过去，测试就变成在测 system 提示的长度而不是裁剪逻辑。
    QUESTION = "对比 Project 01 与 Project 04 各自的持久化方式。"
    SHORT_PROMPT = "短规则"
    BUDGET = 250

    def test_history_is_trimmed_before_next_call(self):
        """裁剪必须在「tool 回灌之后、下一次 chat 之前」发生。"""
        agent = ReActAgent(
            ScriptedLLM(_search("Project 04 会话", "c1"), _search("Project 02 服务层", "c2"), _answer("完成")),
            _registry(),
            settings=AgentSettings(context_budget=self.BUDGET, keep_recent_steps=1),
            system_prompt=self.SHORT_PROMPT,
        )
        result = agent.run(self.QUESTION)
        assert result.answer == "完成"
        # 第三轮请求里，最早那步的工具结果应该已经被压成占位符
        third_request = agent._recorder.transcript[2][0]
        tool_texts = [m.content or "" for m in third_request if m.role == "tool"]
        assert any(TRIMMED_MARK in t for t in tool_texts)
        # 最近那步必须留原文 —— 那正是模型马上要引用的内容
        assert TRIMMED_MARK not in tool_texts[-1]

    def test_no_orphan_tool_message_in_requests(self):
        """每一轮真正发出去的消息都必须成对 —— 这是协议的硬要求。"""
        agent = ReActAgent(
            ScriptedLLM(_search("A", "c1"), _search("B", "c2"), _search("C", "c3"), _answer("完成")),
            _registry(),
            settings=AgentSettings(context_budget=100, keep_recent_steps=1),
        )
        agent.run("问题" * 50)
        for messages, _tools, _reply in agent._recorder.transcript:
            pending: set[str] = set()
            for m in messages:
                if m.tool_calls:
                    pending.update(c.id for c in m.tool_calls)
                elif m.role == "tool":
                    assert m.tool_call_id in pending, "产生了孤儿 tool 消息 —— 真发请求会 400"

    def test_system_and_question_survive_trimming(self):
        agent = ReActAgent(
            ScriptedLLM(_search("A", "c1"), _answer("完成")),
            _registry(),
            settings=AgentSettings(context_budget=60, keep_recent_steps=1),
        )
        agent.run("原始提问内容")
        last_request = agent._recorder.transcript[-1][0]
        assert last_request[0].role == "system"
        texts = [m.content or "" for m in last_request]
        assert "原始提问内容" in "".join(texts)

    def test_scratchpad_survives_when_history_trimmed(self):
        """这条是整个 M05 的立论：历史可以被裁，纸上的结论不能丢。"""
        pad = Scratchpad()
        llm = ScriptedLLM(
            LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="w", name="write_note", arguments={"key": "事实", "value": "关键结论不能丢"})],
            ),
            LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="s", name="rag_search", arguments={"query": "再来一轮把历史撑大"})],
            ),
            _answer("汇总完了"),
        )
        agent = ReActAgent(llm, _registry(pad), settings=AgentSettings(context_budget=40, keep_recent_steps=1), scratchpad=pad)
        result = agent.run("很长的问题" * 30)
        assert result.notes["事实"] == "关键结论不能丢"


# ------------------------------------------------------------ 组合：多步骤任务
class TestMultiStep:
    def _multi_step_llm(self) -> ScriptedLLM:
        return ScriptedLLM(
            _search("Project 01 的持久化方式", "c1"),
            LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="w1", name="write_note", arguments={"key": "p01", "value": "P01 用 JSON 文件"})],
            ),
            _search("Project 04 的持久化方式", "c2"),
            LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="w2", name="write_note", arguments={"key": "p04", "value": "P04 用原子写 + Chroma"})],
            ),
            _answer("P01 用 JSON，P04 用原子写 + Chroma"),
        )

    def test_multi_step_collects_two_notes(self):
        pad = Scratchpad()
        llm = self._multi_step_llm()
        result = ReActAgent(llm, _registry(pad), scratchpad=pad).run("对比 P01 与 P04 的持久化")
        assert set(result.notes) == {"p01", "p04"}
        assert len(result.tool_calls) == 4
        assert result.steps_used >= 5

    def test_multi_step_hits_max_steps_when_plan_too_long(self):
        steps = [_search(f"第{i}个方面", f"c{i}") for i in range(1, 6)]
        llm = ScriptedLLM(*steps)
        with pytest.raises(MaxStepsExceeded):
            ReActAgent(llm, _registry(), settings=AgentSettings(max_steps=3)).run("请从五个方面分析")
