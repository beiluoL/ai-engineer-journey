"""Milestone 03 —— Function Calling：模型提出调用，宿主决定执行。

运行：
    .venv/bin/python demos/demo_03_function_calling.py
    .venv/bin/python demos/demo_03_function_calling.py --real

默认跑离线剧本（不发网络请求）；加 --real 走真实 DeepSeek。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.errors import LLMError
from agent.llm import DeepSeekLLM, LLMMessage, RecordingLLM, ROLE_TOOL, ScriptedLLM
from agent.registry import ToolRegistry
from agent.tools import ToolCall


def head(text: str) -> None:
    print(f"\n{'=' * 74}\n{text}\n{'=' * 74}")


def brief(messages) -> None:
    """把一轮请求的 messages 压缩成一行行看。"""
    for i, m in enumerate(messages):
        extra = ""
        if m.tool_calls:
            extra = "  tool_calls=" + ",".join(f"{c.name}" for c in m.tool_calls)
        elif m.tool_call_id:
            extra = f"  tool_call_id={m.tool_call_id}"
        content = (m.content or "").replace("\n", " ")
        print(f"  [{i}] role={m.role:<10} {content[:58]!r}{extra}")


def fake_script() -> ScriptedLLM:
    """剧本：先检索，再回答。"""
    return ScriptedLLM(
        LLMMessage(
            role="assistant",
            content="我需要先查一下知识库。",
            tool_calls=[ToolCall(id="call_1", name="rag_search", arguments={"query": "Project 04 会话落盘"})],
        ),
        LLMMessage(role="assistant", content="根据检索到的笔记：会话落盘用了 mkstemp+fsync+os.replace。"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="走真实 DeepSeek")
    parser.add_argument("--model", default="deepseek-chat")
    args = parser.parse_args()

    reg = ToolRegistry()

    head("① 第一回合：模型只是「想」调用，什么都没执行")
    llm = RecordingLLM(fake_script() if not args.real else DeepSeekLLM(
        __import__("agent.settings", fromlist=["AgentSettings"]).AgentSettings(model=args.model)
    ))

    messages: list[LLMMessage] = [LLMMessage(role="user", content="Project 04 的会话是怎么落盘的？")]
    reply = llm.chat(messages, tools=reg.schemas())
    messages.append(reply)
    brief(messages)
    assert reply.tool_calls is not None
    call = reply.tool_calls[0]
    print(f"\n  解析出调用：id={call.id!r} name={call.name!r} arguments={json.dumps(call.arguments, ensure_ascii=False)}")

    head("② 宿主执行，并把结果装成一条 tool 消息")
    result = reg.call(call)
    messages.append(LLMMessage(role=ROLE_TOOL, content=result.render(), tool_call_id=call.id, name=call.name))
    print(f"  ToolResult.ok = {result.ok}")
    print("  这条消息有三个字段缺一不可：role=tool / tool_call_id / name")
    brief(messages)

    head("③ 第二回合：模型看到工具结果，给出最终回答")
    reply2 = llm.chat(messages, tools=reg.schemas())
    messages.append(reply2)
    brief(messages)
    print(f"\n  最终答案：{reply2.content}")

    if not args.real:
        head("④ 关键顺序：assistant 必须在 tool 之前")
        roles = [m.role for m in messages]
        print(f"  role 序列 = {roles}")
        idx_call = roles.index("assistant", 1)
        idx_tool = roles.index("tool")
        print(f"  assistant 在索引 {idx_call}，tool 在索引 {idx_tool} → {'顺序正确 ✓' if idx_call < idx_tool else '顺序错误 ✗'}")
        print("  这条规则服务端会校验，离线 mock 里永远复现不出来。")
    else:
        head("④ 真实链路信息")
        print(f"  模型：{args.model}   真实 HTTP 往返 {len(llm.transcript)} 次")
        print(f"  环境变量 DEEPSEEK_API_KEY 已读取（长度 {len(os.getenv('DEEPSEEK_API_KEY', ''))}）")

    head("⑤ 一次失败：模型编了个不存在的工具")
    bad = ToolCall(id="call_x", name="search_online", arguments={"q": "x"})
    failed = reg.call(bad)
    print(f"  ok = {failed.ok}")
    print(f"  回灌给模型 → {failed.render()}")
    print("  模型下一轮可以自己改成 rag_search —— 一次工具失败不该打死整轮任务。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LLMError as exc:
        print(f"\n[真实链路失败] {exc}")
        raise SystemExit(1)
