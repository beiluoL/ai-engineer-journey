"""Project 05 —— Agent 循环（ReAct）。

整个 Agent 只有这一个循环，但它值得每一行为什么这么写都写清楚：:

    messages = [system, 用户问题]
    repeat until max_steps:
        reply = llm.chat(messages, tools=schemas)
        messages.append(reply)                     # ①  assistant（可能带 tool_calls）
        if reply 没有 tool_calls:
            return 最终答案
        for call in reply.tool_calls:
            result = registry.call(call)          # ②  执行（永不通抛出错）
            messages.append(tool 消息)             # ③  结果文本回灌

三个容易写错的地方：

① **assistant 消息必须在工具结果之前追加**。OpenAI 协议对 tool 消息的
   前置条件是有对应的 assistant tool_calls，缺了直接 400。离线 mock 完全
   复现不出这个错，只能真调才会暴露 —— 项目 04 里 SSE 挂载把 API 全吃掉
   是同一类坑：**错误只在"真实路径"上出现**。

② **工具异常不往上抛**。一次工具失败不等于任务失败，把
   ``[工具执行失败] ...`` 当文本回灌，模型大概率会换个参数重试；
   直接抛异常等于把整轮任务打死。

③ **必须有步数上限**。模型偶尔会进入"换个思路—再调用—再换个思路"的
   空转，没有上限就会一直烧 token。步数上限是 Agent 的成本闸门。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

from .errors import InvalidToolCallError, MaxStepsExceeded, TooManyToolFailures
from .llm import LLM, LLMMessage, RecordingLLM, ROLE_ASSISTANT, ROLE_SYSTEM, ROLE_TOOL, ROLE_USER
from .registry import ToolRegistry
from .settings import AGENT_SYSTEM_PROMPT, AgentSettings
from .tools import Tool, ToolCall, ToolResult, default_tools

__all__ = ["Step", "AgentResult", "ReActAgent", "build_agent"]


@dataclass(frozen=True)
class Step:
    """轨迹里的一步。trace 文本就是靠它拼出来的，截图直接来自这里。"""

    index: int
    kind: str  # thought / tool / answer
    text: str
    call: ToolCall | None = None
    result: ToolResult | None = None

    @property
    def ok(self) -> bool:
        return self.result is None or self.result.ok


@dataclass
class AgentResult:
    """一轮任务的完整结果：答案 + 轨迹。"""

    answer: str
    steps: tuple[Step, ...] = ()
    question: str = ""

    @property
    def steps_used(self) -> int:
        return len(self.steps)

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [s.call for s in self.steps if s.call is not None]

    def trace(self) -> str:
        """人类可读的完整轨迹，真实运行截图就靠它。"""
        lines = [f"问题：{self.question}"]
        for s in self.steps:
            if s.kind == "tool" and s.call is not None and s.result is not None:
                args = json.dumps(s.call.arguments, ensure_ascii=False)
                flag = " ✓" if s.result.ok else " ✗"
                lines.append(f"  [{s.index}] 调用 {s.call.name}({args})")
                body = s.result.render().splitlines()
                for i, line in enumerate(body[:6]):
                    lines.append(f"        → {line}")
                if len(body) > 6:
                    lines.append(f"        → ...（共 {len(body)} 行）")
            else:
                lines.append(f"  [{s.index}] {s.kind}：{s.text}")
        lines.append(f"答案：{self.answer}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "steps": [
                {
                    "index": s.index,
                    "kind": s.kind,
                    "text": s.text,
                    "call": {"name": s.call.name, "arguments": s.call.arguments} if s.call else None,
                    "result": s.result.output if s.result else None,
                    "error": s.result.error if s.result else None,
                }
                for s in self.steps
            ],
        }


class ReActAgent:
    """ReAct = Reason + Act：把"想"和"做"放进同一个循环里。"""

    def __init__(
        self,
        llm: LLM,
        registry: ToolRegistry,
        *,
        settings: AgentSettings | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.settings = settings or AgentSettings()
        self.system_prompt = system_prompt or AGENT_SYSTEM_PROMPT
        self._recorder = RecordingLLM(llm)

    # ------------------------------------------------------------------ 运行
    def run(self, question: str, *, max_steps: int | None = None, verbose: bool = False) -> AgentResult:
        limit = max_steps if max_steps is not None else self.settings.max_steps
        steps: list[Step] = []

        messages: list[LLMMessage] = [
            LLMMessage(role=ROLE_SYSTEM, content=self.system_prompt),
            LLMMessage(role=ROLE_USER, content=question),
        ]

        consecutive_failures = 0
        last_error: str | None = None

        for index in range(1, limit + 1):
            reply = self._recorder.chat(messages, tools=self.registry.schemas())

            # ① assistant 先入列（它决定后面接什么 tool 消息）
            messages.append(
                LLMMessage(
                    role=ROLE_ASSISTANT,
                    content=reply.content,
                    tool_calls=reply.tool_calls,
                )
            )
            if reply.content:
                steps.append(Step(index=index, kind="thought", text=reply.content.strip()))

            if not reply.tool_calls:
                answer = (reply.content or "").strip()
                if not answer:
                    raise InvalidToolCallError("模型在没有工具调用的情况下返回了空内容")
                steps.append(Step(index=index, kind="answer", text=answer))
                _maybe_dump_trace(self.settings, self._recorder, steps, question, answer)
                return AgentResult(answer=answer, steps=tuple(steps), question=question)

            # ② 逐个执行
            batch: list[Step] = []
            for call in reply.tool_calls:
                # 这里不再校验 call.id：ToolCall 构造时就已经保证 id/name 非空，
                # 缺 id 会被 LLM 层（_load_tool_calls）当成协议错误拦下。
                # 与其写一段永远走不到的防御代码，不如把校验放在唯一该管它的地方。
                result = self.registry.call(call)
                batch.append(Step(index=index, kind="tool", text=result.render(), call=call, result=result))
                # ③ 结果文本回灌
                messages.append(
                    LLMMessage(
                        role=ROLE_TOOL,
                        content=result.render(),
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

            steps.extend(batch)

            if all(s.result is not None and not s.result.ok for s in batch):
                consecutive_failures += 1
                last_error = next((s.result.error for s in batch if s.result), "未知错误")
                if consecutive_failures >= self.settings.max_tool_failures:
                    raise TooManyToolFailures(
                        f"连续 {consecutive_failures} 次工具失败（最后一次：{last_error}），"
                        f"已达上限 {self.settings.max_tool_failures}，主动终止。"
                    )
            else:
                consecutive_failures = 0

            if verbose:
                print(self._render_step(batch))

        raise MaxStepsExceeded(
            f"用了 {limit} 步仍未给出最终答案。最后一步工具返回：{last_error or '（无）'}"
        )

    def _render_step(self, batch: list[Step]) -> str:
        return "\n".join(f"[step] {s.result.render()[:200]}" for s in batch if s.result)


def _maybe_dump_trace(
    settings: AgentSettings,
    recorder: RecordingLLM,
    steps: list[Step],
    question: str,
    answer: str,
) -> None:
    """轨迹落盘。默认关闭（trace_dir 为空），开了就必须是原子写。"""
    if not settings.trace_dir:
        return
    import os
    import tempfile
    from pathlib import Path

    outdir = Path(settings.trace_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in question)[:40] or "question"
    path = outdir / f"trace-{safe}.json"
    payload = {
        "question": question,
        "answer": answer,
        "steps": [{"kind": s.kind, "text": s.text} for s in steps],
        "llm_calls": [
            {"input": [m.to_dict() for m in msgs], "tools": tools, "reply": reply.to_dict()}
            for msgs, tools, reply in recorder.transcript
        ],
    }
    fd, tmp = tempfile.mkstemp(dir=str(outdir), prefix=".trace-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def build_agent(
    llm: LLM | None = None,
    *,
    registry: ToolRegistry | None = None,
    settings: AgentSettings | None = None,
    tools: Sequence[Tool] | None = None,
    system_prompt: str | None = None,
) -> ReActAgent:
    """装配一个 Agent。默认工具集是「检索 + 计算 + 时间」。"""
    return ReActAgent(
        llm or FakeLLM(),
        registry if registry is not None else ToolRegistry(default_tools()),
        settings=settings,
        system_prompt=system_prompt,
    )


_ = ROLE_USER  # 保持导入可见
