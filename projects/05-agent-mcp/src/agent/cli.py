"""Project 05 —— 命令行入口。

    python -m agent.cli "Project 05 的检索工具叫什么？"

设计取舍：**没有 API Key 时不报错退出，而是自动降级到离线剧本**，
并在 stderr 打印醒目提示。理由是这一章的目标是讲清链路，
第一次运行不该被环境变量卡住；等到写真实链路的 demo 时才会走到真 Key。
"""

from __future__ import annotations

import argparse
import os
import sys

from .agent import ReActAgent
from .errors import AgentError
from .llm import DeepSeekLLM, FakeLLM, LLM, LLMMessage, RecordingLLM
from .memory import Scratchpad
from .registry import ToolRegistry
from .settings import AgentSettings
from .tools import ToolCall, default_tools

__all__ = ["main", "build_llm", "mock_responder"]

ROLE_ASSISTANT = "assistant"


def mock_responder() -> object:
    """离线剧本：先检索，再拿检索结果当唯一事实来源回答。

    写成"看消息里有没有工具结果"的确定性规则，而不是随机或固定轮数，
    这样剧本跑多少次轨迹都一致，截图才对得上。
    """
    counter = {"n": 0}

    def _respond(messages: list[LLMMessage], tool_specs) -> LLMMessage:  # noqa: ANN001
        tool_text = _last_tool_text(messages)
        if tool_text is None:
            counter["n"] += 1
            return LLMMessage(
                role=ROLE_ASSISTANT,
                content="这个问题需要外部资料，我先查一下知识库。",
                tool_calls=[
                    ToolCall(
                        id=f"call_mock_{counter['n']}",
                        name="rag_search",
                        arguments={"query": _user_question(messages), "k": 2},
                    )
                ],
            )
        first = tool_text.splitlines()[0] if tool_text.splitlines() else tool_text
        return LLMMessage(
            role=ROLE_ASSISTANT,
            content=f"查到了：{first}。这就是知识库里唯一的依据，我没有补充任何额外的说法。",
        )

    return _respond


def _user_question(messages: list[LLMMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user" and m.content:
            return m.content
    return ""


def _last_tool_text(messages: list[LLMMessage]) -> str | None:
    for m in reversed(messages):
        if m.role == "tool" and m.content:
            return m.content
    return None


def build_llm(settings: AgentSettings, *, mock: bool) -> tuple[LLM, bool]:
    """返回 (llm, 是否真的走了真实模型)。"""
    if not mock:
        try:
            return DeepSeekLLM(settings), True
        except AgentError as exc:
            if "为空" not in str(exc):
                raise
            print(f"[warn] {exc} → 自动降级到离线剧本", file=sys.stderr)
    return FakeLLM(responder=mock_responder()), False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent", description="Project 05 Research Agent")
    parser.add_argument("question", nargs="?", help="要问 Agent 的问题")
    parser.add_argument("--max-steps", type=int, default=None, help="最多循环几步")
    parser.add_argument("--mock", action="store_true", help="强制使用离线剧本")
    parser.add_argument("--trace", default="", help="把完整轨迹写成 JSON")
    parser.add_argument("--list-tools", action="store_true", help="只打印工具清单")
    parser.add_argument(
        "--notes",
        action="store_true",
        help="打开草稿纸：额外挂载 write_note / read_notes 两个工具（Milestone 05，多步骤任务用）",
    )
    args = parser.parse_args(argv)

    settings = AgentSettings.from_env()
    if args.trace:
        settings = settings.replace(trace_dir=args.trace)
    # Milestone 05：草稿纸必须**一张纸给一对工具共用**，所以在这里建一次再往下分发；
    # 让 WriteNoteTool / ReadNotesTool 各自 new 一张就互相不通了。
    pad = Scratchpad() if args.notes else None
    registry = ToolRegistry(default_tools(pad) if pad is not None else None)

    if args.list_tools:
        # schemas() 返回的是完整工具对象（{"type":"function","function":{...}}），
        # 内层才是 name/description/parameters —— 这里要拆一层再读，别搞反。
        for item in registry.schemas():
            function = item["function"]
            params = function["parameters"]
            props = ", ".join(params.get("properties", {})) or "无参数"
            print(f"{function['name']}（{props}）")
            print(f"   说明：{function['description']}")
            print(f"   必填：{', '.join(params.get('required', [])) or '无'}")
        return 0

    if not args.question:
        parser.print_help()
        return 2

    llm, real = build_llm(settings, mock=args.mock)
    agent = ReActAgent(llm, registry, settings=settings, scratchpad=pad)

    print(f"# 模型：{llm.name}   工具：{', '.join(registry.names())}   {'（真实模型）' if real else '（离线剧本）'}")
    result = agent.run(args.question, max_steps=args.max_steps)
    print()
    print(result.trace())
    if args.notes:
        pad_notes = result.notes
        print()
        print(f"草稿纸：{len(pad_notes)} 条")
        for key, value in pad_notes.items():
            print(f"  · {key}：{value}")
    return 0


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


if __name__ == "__main__":
    raise SystemExit(main())
