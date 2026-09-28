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

Milestone 05 在这上面补了三件事（详见 `memory.py`）：

④ **重复调用检测**：空转不一定报错。模型反复用完全相同的参数调同一个工具、
   拿回完全相同的结果，失败闸门一次都没涨，只能等步数烧完 ——
   所以要按「工具名 + 参数」的签名单独计数。

⑤ **工作记忆裁剪**：多步骤任务里历史膨胀很快，按 token 预算裁剪早期工具结果。
   裁剪时 assistant(tool_calls) 与它的 tool 消息必须**同进同出**，
   留下孤儿 tool 消息会直接 400。

⑥ **草稿纸（Scratchpad）**：中间结论不能只活在对话流里 —— 那个流是要被裁的。
   把它显式写进循环之外的便签，Plan → Act → Observe 才真的闭环。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from .errors import (
    InvalidToolCallError,
    MaxStepsExceeded,
    RepeatedToolCall,
    TooManyToolFailures,
)
from .llm import (
    LLM,
    FakeLLM,
    LLMMessage,
    RecordingLLM,
    ROLE_ASSISTANT,
    ROLE_SYSTEM,
    ROLE_TOOL,
    ROLE_USER,
)
from .memory import Scratchpad, estimate_messages_tokens, trim_history
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
    notes: dict[str, str] = field(default_factory=dict)
    """任务结束时草稿纸上留下的笔记（Milestone 05）。

    它和 ``steps`` 是两个维度的证据：轨迹告诉你「做了什么动作」，
    笔记告诉你「留下了什么结论」—— 后者才是多步骤任务真正想要的东西。
    """

    @property
    def used_scratchpad(self) -> bool:
        return bool(self.notes)

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
        if self.notes:
            lines.append("草稿纸：")
            for key, value in self.notes.items():
                lines.append(f"  · {key}：{value[:120]}{'…' if len(value) > 120 else ''}")
        lines.append(f"答案：{self.answer}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "notes": dict(self.notes),
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
        scratchpad: Scratchpad | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.settings = settings or AgentSettings()
        self.system_prompt = system_prompt or AGENT_SYSTEM_PROMPT
        self.scratchpad = scratchpad
        self._recorder = RecordingLLM(llm)

    # ------------------------------------------------------------------ 运行
    def run(self, question: str, *, max_steps: int | None = None, verbose: bool = False) -> AgentResult:
        limit = max_steps if max_steps is not None else self.settings.max_steps
        steps: list[Step] = []
        pad = self.scratchpad

        messages: list[LLMMessage] = [
            LLMMessage(role=ROLE_SYSTEM, content=self._system_text()),
            LLMMessage(role=ROLE_USER, content=question),
        ]

        consecutive_failures = 0
        last_error: str | None = None
        call_signatures: dict[str, int] = {}
        trimmed_rounds = 0

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
                _maybe_dump_trace(self.settings, self._recorder, steps, question, answer, pad)
                return AgentResult(
                    answer=answer,
                    steps=tuple(steps),
                    question=question,
                    notes=pad.to_dict() if pad is not None else {},
                )

            # ② 逐个执行
            batch: list[Step] = []
            for call in reply.tool_calls:
                # ④ 重复调用闸门：同一个「工具名 + 参数」再调一次，说明它在原地打转。
                #    注意要用 sort_keys=True 序列化——模型可能把 {"a":1,"b":2} 写成
                #    {"b":2,"a":1}，那是同一次调用，不该被算成两个签名。
                signature = call.name + ":" + json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)
                seen = call_signatures.get(signature, 0) + 1
                call_signatures[signature] = seen
                if seen > self.settings.max_repeats:
                    raise RepeatedToolCall(
                        f"{call.name}({signature.split(':', 1)[1]}) 已被调用 {seen} 次"
                        f"（上限 {self.settings.max_repeats}），模型在原地打转，主动终止。"
                    )

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

            # ⑤ 工作记忆裁剪：发出去之前压进预算。
            #    这一步必须在 tool 回灌之后、下一次 chat 之前做；
            #    而且 trim 返回的是新列表，Recorder 里那份快照不会被污染。
            before = estimate_messages_tokens(messages)
            if before > self.settings.context_budget:
                messages = trim_history(
                    messages,
                    budget=self.settings.context_budget,
                    keep_recent=self.settings.keep_recent_steps,
                )
                trimmed_rounds += 1
                if verbose:
                    after = estimate_messages_tokens(messages)
                    print(f"[trim] {before} → {after} tokens（{self.settings.context_budget} 预算）")
            # system 里带着草稿纸，每轮要重建：笔记可能刚被更新过
            if pad is not None:
                messages[0] = LLMMessage(role=ROLE_SYSTEM, content=self._system_text())

            if verbose:
                print(self._render_step(batch))

        raise MaxStepsExceeded(
            f"用了 {limit} 步仍未给出最终答案（期间裁剪 {trimmed_rounds} 次）。"
            f"最后一步工具返回：{last_error or '（无）'}"
        )

    def _system_text(self) -> str:
        """system 提示 = 工作规则 + 草稿纸上的笔记。

        把笔记常驻在提示里是刻意的：模型不必额外调一次 read_notes 就能看见它们，
        多步骤任务里省下的就是实打实的一轮往返。
        """
        if self.scratchpad is None:
            return self.system_prompt
        notes = self.scratchpad.render()
        return f"{self.system_prompt}\n\n{notes}" if notes else self.system_prompt

    def _render_step(self, batch: list[Step]) -> str:
        return "\n".join(f"[step] {s.result.render()[:200]}" for s in batch if s.result)


def _maybe_dump_trace(
    settings: AgentSettings,
    recorder: RecordingLLM,
    steps: list[Step],
    question: str,
    answer: str,
    pad: Scratchpad | None = None,
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
        "notes": pad.to_dict() if pad is not None else {},
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
    scratchpad: Scratchpad | None = None,
) -> ReActAgent:
    """装配一个 Agent。默认工具集是「检索 + 计算 + 时间」。

    给 ``scratchpad`` 传一个对象（或 ``True`` 表示「帮我建一张」）时，
    会额外注册草稿纸工具 —— **两个 note 工具共享同一张纸**，
    这一点由这里保证，而不是由工具自己 new（那样会得到两张互不相通的纸）。
    """
    if scratchpad is True:  # type: ignore[comparison-overlap]
        scratchpad = Scratchpad()
    if registry is None:
        # 注意这里必须是 ``is not None``：Scratchpad 实现了 __len__，
        # 空草稿纸在布尔判断里是**假值** —— 写成 ``if scratchpad:`` 会让刚建好的
        # 空纸被当成"没传"，草稿纸工具一个都注册不上（这个坑真踩过）。
        registry = ToolRegistry(default_tools(scratchpad) if scratchpad is not None else (list(tools) if tools else None))
    return ReActAgent(
        llm or FakeLLM(),
        registry,
        settings=settings,
        system_prompt=system_prompt,
        scratchpad=scratchpad,
    )


_ = ROLE_USER  # 保持导入可见
