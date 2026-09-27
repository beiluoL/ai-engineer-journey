"""Project 05 —— Agent 循环测试。

这里断言的不是"答案对不对"，而是**链路对不对**：
工具结果有没有真的回灌、消息顺序是否符合协议、失败会不会被打断。
答案对不对应该在真实模型上验证（见 demos/）。
"""

from __future__ import annotations

import json

import pytest

from agent.agent import AgentResult, ReActAgent, Step, build_agent
from agent.errors import InvalidToolCallError, MaxStepsExceeded, TooManyToolFailures
from agent.llm import FakeLLM, LLMMessage, RecordingLLM, ScriptedLLM
from agent.registry import ToolRegistry
from agent.settings import AgentSettings
from agent.tools import Tool, ToolCall


def _search_call(call_id: str = "c1", query: str = "落盘") -> LLMMessage:
    return LLMMessage(
        role="assistant",
        content="先查一下",
        tool_calls=[ToolCall(id=call_id, name="rag_search", arguments={"query": query})],
    )


def _reg() -> ToolRegistry:
    return ToolRegistry()


# --------------------------------------------------------------------------
# 正常链路
# --------------------------------------------------------------------------
def test_full_react_trajectory() -> None:
    llm = ScriptedLLM(
        _search_call(),
        LLMMessage(role="assistant", content="答案：用 mkstemp+fsync+os.replace 原子写。"),
    )
    result = ReActAgent(llm, _reg(), settings=AgentSettings()).run("会话怎么落盘")

    assert isinstance(result, AgentResult)
    assert result.answer.startswith("答案：")
    assert [c.name for c in result.tool_calls] == ["rag_search"]
    assert result.steps_used == 4  # thought + tool + thought + answer


def test_tool_result_is_fed_back_to_llm() -> None:
    """接口通 ≠ 链路对。不记录就永远证明不了工具结果真回去了。"""
    llm = ScriptedLLM(_search_call(), LLMMessage(role="assistant", content="done"))
    ReActAgent(llm, _reg()).run("会话怎么落盘")

    second_round = llm.calls[1]
    assert second_round[-1].role == "tool"
    assert second_round[-1].tool_call_id == "c1"
    assert "p04-session" in second_round[-1].content, "回灌的必须是工具真实输出"


def test_assistant_message_precedes_tool_messages() -> None:
    """协议硬要求：tool 消息必须跟在带 tool_calls 的 assistant 之后。

    ``calls[i]`` 是**那一轮发请求时的快照**，所以第 1 轮只有两条；
    第 2 轮快照里 assistant 和 tool 已经在列（它们在第 1 轮返回后就追加了）。
    """
    llm = ScriptedLLM(_search_call(), LLMMessage(role="assistant", content="done"))
    ReActAgent(llm, _reg()).run("问题")

    first = [m.role for m in llm.calls[0]]
    assert first == ["system", "user"], "发请求时 assistant 还没追加"
    second = [m.role for m in llm.calls[1]]
    assert second == ["system", "user", "assistant", "tool"]


def test_assistant_tool_calls_are_preserved_in_messages() -> None:
    llm = ScriptedLLM(_search_call(), LLMMessage(role="assistant", content="done"))
    ReActAgent(llm, _reg()).run("问题")
    assistant = llm.calls[1][2]
    assert assistant.role == "assistant"
    assert assistant.tool_calls and [c.id for c in assistant.tool_calls] == ["c1"]


def test_tools_are_declared_every_round() -> None:
    """每一轮都带全量工具声明：第 2 轮要基于工具结果继续决定，
    模型不能"忘了"自己有哪些能力。"""
    llm = ScriptedLLM(
        _search_call(),
        LLMMessage(role="assistant", content="done"),
        LLMMessage(role="assistant", content="done2"),
    )
    ReActAgent(llm, _reg()).run("问题", max_steps=2)
    assert len(llm.tool_lists) == 2
    assert all(
        t is not None and [f["function"]["name"] for f in t] == ["calculator", "now", "rag_search"]
        for t in llm.tool_lists
    )


def test_trace_text_is_human_readable() -> None:
    llm = ScriptedLLM(_search_call(), LLMMessage(role="assistant", content="最终答案"))
    result = ReActAgent(llm, _reg()).run("会话怎么落盘")
    trace = result.trace()
    assert "问题：" in trace and "调用 rag_search" in trace and "答案：最终答案" in trace


def test_result_to_dict_is_serializable() -> None:
    llm = ScriptedLLM(_search_call(), LLMMessage(role="assistant", content="最终答案"))
    result = ReActAgent(llm, _reg()).run("会话怎么落盘")
    payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert payload["answer"] == "最终答案"
    tool_steps = [s for s in payload["steps"] if s["call"]]
    assert tool_steps[0]["call"]["name"] == "rag_search"
    assert tool_steps[0]["call"]["arguments"] == {"query": "落盘"}
    assert tool_steps[0]["result"], "工具步骤必须带着执行结果"


# --------------------------------------------------------------------------
# 多工具并行
# --------------------------------------------------------------------------
def test_parallel_tool_calls_both_execute() -> None:
    llm = ScriptedLLM(
        LLMMessage(
            role="assistant",
            content="两个都查",
            tool_calls=[
                ToolCall(id="c1", name="calculator", arguments={"expression": "2**10"}),
                ToolCall(id="c2", name="now", arguments={}),
            ],
        ),
        LLMMessage(role="assistant", content="算完和时间都拿到了"),
    )
    result = ReActAgent(llm, _reg()).run("现在？")
    assert [c.id for c in result.tool_calls] == ["c1", "c2"]
    second = llm.calls[1]
    assert [m.tool_call_id for m in second if m.role == "tool"] == ["c1", "c2"]


# --------------------------------------------------------------------------
# 失败路径
# --------------------------------------------------------------------------
def test_max_steps_exceeded() -> None:
    def always_search(messages, tools):
        return LLMMessage(role="assistant", tool_calls=[ToolCall(id="c", name="rag_search", arguments={"query": "q"})])

    with pytest.raises(MaxStepsExceeded, match="用了 3 步仍未给出最终答案"):
        ReActAgent(FakeLLM(responder=always_search), _reg(), settings=AgentSettings(max_steps=3)).run("问题")


def test_too_many_tool_failures_stops() -> None:
    """连续失败要主动放弃，否则就是无限烧钱的空转。"""
    llm = ScriptedLLM(
        LLMMessage(role="assistant", tool_calls=[ToolCall(id="c1", name="不存在", arguments={})]),
        LLMMessage(role="assistant", tool_calls=[ToolCall(id="c2", name="也不存在", arguments={})]),
        LLMMessage(role="assistant", tool_calls=[ToolCall(id="c3", name="还不是这个", arguments={})]),
    )
    with pytest.raises(TooManyToolFailures, match="连续 3 次工具失败"):
        ReActAgent(llm, _reg(), settings=AgentSettings(max_tool_failures=3)).run("问题")


def test_successful_call_resets_failure_counter() -> None:
    llm = ScriptedLLM(
        _search_call(),
        LLMMessage(role="assistant", tool_calls=[ToolCall(id="c2", name="不存在", arguments={})]),
        LLMMessage(role="assistant", content="好了"),
    )
    result = ReActAgent(llm, _reg(), settings=AgentSettings(max_tool_failures=3)).run("问题")
    assert result.answer == "好了", "成功一次就应该把失败计数清零"


def test_empty_answer_without_tools_raises() -> None:
    """既不给工具也不给内容，等于什么都没做 —— 当成协议错误而不是返回空字符串。"""
    # strict=False 表示"允许这条消息不合规"，用来复现真实模型偶尔返回空的现象
    llm = FakeLLM(responder=lambda m, t: LLMMessage(role="assistant"), strict=False)
    with pytest.raises(InvalidToolCallError, match="空内容"):
        ReActAgent(llm, _reg()).run("问题")


def test_failed_tool_still_appends_step() -> None:
    llm = ScriptedLLM(
        LLMMessage(role="assistant", tool_calls=[ToolCall(id="c1", name="不存在", arguments={})]),
        LLMMessage(role="assistant", content="换个方式"),
    )
    result = ReActAgent(llm, _reg(), settings=AgentSettings(max_tool_failures=5)).run("问题")
    failed = [s for s in result.steps if s.result is not None and not s.result.ok]
    assert failed and failed[0].kind == "tool"


# --------------------------------------------------------------------------
# 轨迹落盘（原子写）
# --------------------------------------------------------------------------
def test_trace_is_written_atomically(workdir) -> None:
    llm = ScriptedLLM(_search_call(), LLMMessage(role="assistant", content="最终答案"))
    settings = AgentSettings(trace_dir=str(workdir))
    ReActAgent(llm, _reg(), settings=settings).run("会话怎么落盘")

    files = list(workdir.iterdir())
    assert [f.name for f in files] == ["trace-会话怎么落盘.json"]
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["answer"] == "最终答案"
    assert len(payload["llm_calls"]) == 2


def test_trace_not_written_when_dir_empty(workdir) -> None:
    llm = ScriptedLLM(LLMMessage(role="assistant", content="直接回答"))
    ReActAgent(llm, _reg(), settings=AgentSettings(trace_dir="")).run("问题")
    assert list(workdir.iterdir()) == []


# --------------------------------------------------------------------------
# 装配
# --------------------------------------------------------------------------
def test_build_agent_has_default_tools() -> None:
    agent = build_agent(FakeLLM(responder=lambda m, t: LLMMessage(role="assistant", content="ok")))
    assert agent.registry.names() == ["calculator", "now", "rag_search"]
    assert isinstance(agent, ReActAgent)


def test_custom_registry_is_respected() -> None:
    class _Dup(Tool):
        """自定义实现。参数声明必须齐全，否则 registry 会按 schema 拒绝 query。"""
        name = "rag_search"
        description = "同名覆盖"
        parameters = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

        def schema(self):  # type: ignore[override]
            from agent.tools import function_schema

            return function_schema(self.name, self.description, self.parameters)

        def run(self, **kwargs) -> str:
            return "custom"

    reg = ToolRegistry(tools=[])
    reg.register(_Dup())
    llm = ScriptedLLM(
        LLMMessage(
            role="assistant",
            tool_calls=[ToolCall(id="c1", name="rag_search", arguments={"query": "任意"})],
        ),
        LLMMessage(role="assistant", content="用了自定义实现"),
    )
    result = ReActAgent(llm, reg).run("问题")
    assert result.answer == "用了自定义实现"
    assert llm.calls[1][-1].content == "custom", "同名工具应该被后注册的实现覆盖"


def test_step_is_frozen() -> None:
    step = Step(index=1, kind="thought", text="t")
    with pytest.raises(Exception):
        step.index = 2  # type: ignore[misc]
