"""Milestone 10 —— Workflow 的测试。

这一章最核心的主张是**上下文隔离**：每个 Worker 只看自己需要的那一点。
所以最值钱的测试不是「能不能跑完」，而是：

    「第二个 Worker 发给模型的消息里，到底有没有第一个 Worker 的检索原文？」

没有这个断言，'隔离' 就只是一句口号。
"""

from __future__ import annotations

import pytest

from agent.llm import FakeLLM, LLMMessage
from agent.memory import Scratchpad
from agent.plan import DONE, FAILED, PENDING, SKIPPED, Plan
from agent.registry import ToolRegistry
from agent.settings import AgentSettings
from agent.tools import ToolCall, default_tools
from agent.workflow import Workflow, WorkflowResult, build_workflow

TASKS = (
    '[{"id":"t1","title":"查 Project 01 怎么落盘"},'
    '{"id":"t2","title":"查 Project 04 怎么落盘"},'
    '{"id":"t3","title":"汇总两者差异","depends_on":["t1","t2"]}]'
)

ANSWERS = {
    "t1": "P01 是单轮 CLI，不落盘（无状态）。",
    "t2": "P04 会话用 mkstemp+fsync+os.replace 原子写落盘。",
    "t3": "P01 无状态不落盘；P04 有状态，原子写落盘。",
}

#: 检索工具会返回的原文。用它来验证「隔离」—— 下游不该看到它。
RAW_OUTPUT_MARK = "Project 04 会话与多轮（p04-session）"


def _responder(messages, tools=None):
    """先查一次工具，再给出结论。

    这样每个 Worker 都有 2 步，能顺带验证「工具结果真的回灌了」。
    """
    if not any(m.role == "tool" for m in messages):
        return LLMMessage(
            role="assistant",
            tool_calls=[ToolCall(id="c1", name="rag_search", arguments={"query": "落盘"})],
        )
    text = ""
    for m in messages:
        if m.role == "user":
            text = m.content or ""
    for key, answer in ANSWERS.items():
        if f"（{key}）" in text:
            return LLMMessage(role="assistant", content=answer)
    if "请据此给出一段完整的回答" in text:
        # 汇总者的提问格式和子任务不同，这里单独认
        return LLMMessage(role="assistant", content=ANSWERS["t3"])
    return LLMMessage(role="assistant", content="（兜底答案）")


def _workflow(llm=None, **kw) -> Workflow:
    pad = Scratchpad()
    plan = Plan()
    return Workflow(
        llm or FakeLLM(responder=_responder),
        ToolRegistry(default_tools(pad, plan)),
        settings=AgentSettings(max_steps=4),
        scratchpad=pad,
        plan=plan,
        **kw,
    )


class TestWorkflowRuns:
    def test_all_tasks_done(self):
        wf = _workflow()
        result = wf.run("对比 P01 与 P04 的落盘方式", tasks=TASKS)
        assert {t["status"] for t in result.workers} == {DONE}
        assert result.plan["goal"] == "对比 P01 与 P04 的落盘方式"

    def test_worker_stats_recorded(self):
        """每个子任务花了多少步、调了几次工具 —— 排查时最想知道的。"""
        result = _workflow().run("目标", tasks=TASKS)
        for w in result.workers:
            assert w["tool_calls"] >= 1
            assert w["steps"] >= 1

    def test_summary_uses_conclusions(self):
        result = _workflow().run("目标", tasks=TASKS)
        assert "P01" in result.answer and "P04" in result.answer

    def test_render_contains_tasks_and_answer(self):
        text = _workflow().run("目标", tasks=TASKS).render()
        assert "✓ t1" in text
        assert "汇总：" in text

    def test_to_dict_is_serializable(self):
        import json

        payload = _workflow().run("目标", tasks=TASKS).to_dict()
        json.dumps(payload, ensure_ascii=False)  # 能序列化即可
        assert set(payload) == {"goal", "answer", "plan", "notes", "workers"}


class TestContextIsolation:
    """这一章的核心主张，必须有证据。"""

    def _capturing_workflow(self) -> tuple[Workflow, list[list[LLMMessage]]]:
        seen: list[list[LLMMessage]] = []

        def responder(messages, tools=None):
            seen.append([LLMMessage(role=m.role, content=m.content) for m in messages])
            return _responder(messages, tools)

        return _workflow(FakeLLM(responder=responder)), seen

    def test_downstream_does_not_see_upstream_raw_output(self):
        """汇总 Worker 的请求里不该出现别的 Worker 的检索原文。"""
        wf, seen = self._capturing_workflow()
        wf.run("目标", tasks=TASKS)
        # 最后一个 Worker 的第一次请求（它还没做自己的检索）
        requests = seen
        raw_hits = [
            i
            for i, req in enumerate(requests)
            if any(RAW_OUTPUT_MARK in (m.content or "") for m in req)
        ]
        # 每个 Worker 只在「回灌自己结果之后」的那次请求里看到原文
        # 关键断言：t3 的**第一次**请求（序号在它自己的回合里）不含别的 Worker 的原文
        assert raw_hits, "工具结果应该真的回灌过，否则这个测试没意义"
        # 找 t3 的第一次请求：它含有"（t3）"
        first_t3 = next(
            (req for req in requests if any("（t3）" in (m.content or "") for m in req)), None
        )
        assert first_t3 is not None
        joined = "".join(m.content or "" for m in first_t3)
        assert RAW_OUTPUT_MARK not in joined, "汇总 Worker 看到了检索原文 —— 隔离失效"

    def test_downstream_sees_upstream_conclusions(self):
        """但结论必须能传下去 —— 否则依赖就没意义了。"""
        wf, seen = self._capturing_workflow()
        wf.run("目标", tasks=TASKS)
        first_t3 = next(
            (req for req in seen if any("（t3）" in (m.content or "") for m in req)), None
        )
        joined = "".join(m.content or "" for m in first_t3)
        assert "单轮 CLI" in joined or "原子写" in joined

    def test_workers_have_own_message_lists(self):
        """每个 Worker 是独立的 ReActAgent，消息不共用。"""
        wf, seen = self._capturing_workflow()
        wf.run("目标", tasks=TASKS)
        # 3 个子任务 + 1 次汇总，每个至少一次请求
        assert len(seen) >= 4


class TestFailureHandling:
    def _flaky(self, fail_for: str):
        def responder(messages, tools=None):
            text = ""
            for m in messages:
                if m.role == "user":
                    text = m.content or ""
            if f"（{fail_for}）" in text:
                raise RuntimeError("这个子任务炸了")
            return _responder(messages, tools)

        return responder

    def test_failed_task_skips_downstream(self):
        wf = _workflow(FakeLLM(responder=self._flaky("t1")))
        result = wf.run("目标", tasks=TASKS)
        status = {w["id"]: w["status"] for w in result.workers}
        assert status["t1"] == FAILED
        assert status["t3"] == SKIPPED
        assert status["t2"] == DONE  # 不依赖 t1，不受影响

    def test_all_failed_has_no_summary(self):
        def always_fail(messages, tools=None):
            raise RuntimeError("全炸")

        wf = _workflow(FakeLLM(responder=always_fail))
        result = wf.run("目标", tasks=TASKS)
        assert "未能完成" in result.answer

    def test_failure_reason_is_recorded(self):
        wf = _workflow(FakeLLM(responder=self._flaky("t1")))
        result = wf.run("目标", tasks=TASKS)
        failed = next(w for w in result.workers if w["id"] == "t1")
        assert "RuntimeError" in failed["result"]


class TestBuildWorkflow:
    def test_build_without_llm(self):
        wf = build_workflow()
        assert isinstance(wf, Workflow)

    def test_build_with_mcp_tools(self):
        """Worker 用的工具全部来自 MCP 子进程 —— Milestone 09 成果的延续。"""
        wf = build_workflow(FakeLLM(responder=_responder), use_mcp=True)
        assert "rag_search" in wf.registry.names()

    def test_make_plan_uses_planner(self):
        """不给 tasks 时，让模型自己拆。"""
        plan = Plan()
        wf = Workflow(
            FakeLLM(responder=_responder),
            ToolRegistry(default_tools(Scratchpad(), plan)),
            plan=plan,
        )
        with pytest.raises(RuntimeError, match="没有产出任何子任务"):
            # 这个假 LLM 不会产出计划，正好验证兜底行为
            wf.run("目标")
