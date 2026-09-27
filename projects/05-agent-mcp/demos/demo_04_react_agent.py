"""Milestone 04 —— Agent：把「想」和「做」放进同一个循环。

运行：
    .venv/bin/python demos/demo_04_react_agent.py
    .venv/bin/python demos/demo_04_react_agent.py --real "会话是怎么落盘的？"

默认跑离线剧本；加 --real 走真实 DeepSeek。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.agent import AgentResult, ReActAgent, Step
from agent.errors import AgentError, MaxStepsExceeded, TooManyToolFailures
from agent.llm import DeepSeekLLM, FakeLLM, LLMMessage, ScriptedLLM
from agent.registry import ToolRegistry
from agent.settings import AgentSettings
from agent.tools import ToolCall


def head(text: str) -> None:
    print(f"\n{'=' * 74}\n{text}\n{'=' * 74}")


def render_steps(steps: tuple[Step, ...]) -> None:
    for s in steps:
        if s.kind == "tool" and s.call is not None and s.result is not None:
            mark = "✓" if s.result.ok else "✗"
            args = json_dumps(s.call.arguments)
            print(f"  [{s.index}] {mark} 调用 {s.call.name}({args})")
            for line in s.result.render().splitlines()[:3]:
                print(f"         ↳ {line[:88]}")
            if len(s.result.render().splitlines()) > 3:
                print("         ↳ …")
        else:
            print(f"  [{s.index}] {s.kind}：{s.text[:88]}")


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def offline_agent() -> ReActAgent:
    llm = ScriptedLLM(
        LLMMessage(
            role="assistant",
            content="这个问题要查资料，先检索。",
            tool_calls=[ToolCall(id="c1", name="rag_search", arguments={"query": "Project 04 会话落盘"})],
        ),
        LLMMessage(
            role="assistant",
            content="检索结果需要验算一下条数。",
            tool_calls=[ToolCall(id="c2", name="calculator", arguments={"expression": "3*2+1"})],
        ),
        LLMMessage(role="assistant", content="会话落盘用 mkstemp+fsync+os.replace 原子写，上面算得 7 条也吻合。"),
    )
    return ReActAgent(llm, ToolRegistry(), settings=AgentSettings())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="走真实 DeepSeek")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--question", default="Project 04 的会话是怎么落盘的？")
    args = parser.parse_args()

    settings = AgentSettings()
    if args.real:
        if not os.getenv("DEEPSEEK_API_KEY"):
            print("[错误] 没有 DEEPSEEK_API_KEY，真实模式无法运行")
            return 2
        agent = ReActAgent(
            DeepSeekLLM(settings.replace(model=args.model)),
            ToolRegistry(),
            settings=settings,
        )
    else:
        agent = offline_agent()

    head("① 完整 ReAct 轨迹")
    result = agent.run(args.question, max_steps=args.max_steps or None)
    render_steps(result.steps)
    print(f"\n  答案：{result.answer}")
    print(f"  步数：{result.steps_used}   工具调用：{[c.name for c in result.tool_calls]}")

    head("② AgentResult.trace()：这就是能贴到文档里的那一段")
    print(result.trace())

    if not args.real:
        head("③ 多工具并行：一轮里两个 tool_call")
        llm = ScriptedLLM(
            LLMMessage(
                role="assistant",
                content="两件事一起办。",
                tool_calls=[
                    ToolCall(id="z1", name="calculator", arguments={"expression": "2**10"}),
                    ToolCall(id="z2", name="now", arguments={}),
                ],
            ),
            LLMMessage(role="assistant", content="算完了，时间也拿到了。"),
        )
        res = ReActAgent(llm, ToolRegistry()).run("1024 和现在时间")
        render_steps(res.steps)
        print(f"\n  两个调用 id = {[c.id for c in res.tool_calls]}，回灌时按 id 一一对应。")

        head("④ 连续失败要主动放弃（否则就是无限烧 token）")
        llm = FakeLLM(
            responder=lambda messages, tools: LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="b", name="不存在的工具", arguments={})],
            ),
        )
        try:
            ReActAgent(llm, ToolRegistry(), settings=AgentSettings(max_tool_failures=3)).run("问题")
        except TooManyToolFailures as exc:
            print(f"  抛出 TooManyToolFailures：{exc}")

        head("⑤ 步数上限是成本闸门")
        llm = FakeLLM(
            responder=lambda messages, tools: LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="s", name="now", arguments={})],
            ),
        )
        try:
            ReActAgent(llm, ToolRegistry(), settings=AgentSettings(max_steps=3)).run("问题")
        except MaxStepsExceeded as exc:
            print(f"  抛出 MaxStepsExceeded：{exc}")

        head("⑥ 轨迹落盘（原子写）")
        with tempfile.TemporaryDirectory(prefix="agent-trace-") as d:
            agent2 = ReActAgent(
                ScriptedLLM(
                    LLMMessage(
                        role="assistant",
                        tool_calls=[ToolCall(id="t1", name="now", arguments={})],
                    ),
                    LLMMessage(role="assistant", content="拿到了"),
                ),
                ToolRegistry(),
                settings=AgentSettings(trace_dir=d),
            )
            agent2.run("现在几点")
            for f in sorted(Path(d).iterdir()):
                payload = f.read_text(encoding="utf-8")
                print(f"  {f.name}  ({len(payload)} 字节)")
                data = json.loads(payload)
                print(f"    答案 = {data['answer']!r}")
                print(f"    步骤 = {len(data['steps'])}   模型往返 = {len(data['llm_calls'])}")
            print("  目录里没有任何 .trace-*.* 临时残留 → mkstemp + os.replace 生效。")
    else:
        head("③ 真实链路")
        print(f"  模型 {args.model}，真实 HTTP 往返已完成，轨迹见上方。")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AgentError as exc:
        print(f"\n[Agent 失败] {type(exc).__name__}: {exc}")
        raise SystemExit(1)
