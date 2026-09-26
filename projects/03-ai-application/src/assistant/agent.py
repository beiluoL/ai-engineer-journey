"""Agent：工具循环（对应 milestones/08-function-calling.md）。

六步循环，最容易漏的是第 ④ ⑤ 步：

    ① 发请求（messages + tools）
    ② 模型返回 tool_calls（而不是直接回答）
    ③ 你执行本地函数
    ④ 把结果作为 role="tool" 消息追加（带 tool_call_id）   ← 容易漏
    ⑤ 再次请求模型                                        ← 容易漏
    ⑥ 模型基于真实结果生成最终回答

只执行不回灌，模型就会凭空编一个结果。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from assistant.errors import ToolLoopError
from assistant.memory import Message
from assistant.tools import describe_calls, dispatch, schemas

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 4


async def run_agent(
    client,
    messages: list[Message],
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> tuple[str, list[Message]]:
    """跑完整个工具循环。

    返回：(最终回答, 完整消息轨迹) —— 轨迹给调用方回灌进会话历史。

    client 需要实现 `chat_message(messages, tools=?) -> dict`（完整 assistant 消息）。
    """
    trace: list[Message] = list(messages)
    tools = schemas() or None

    for iteration in range(1, max_iterations + 1):
        msg = await client.chat_message(trace, tools=tools)
        trace.append(msg)

        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or "", trace

        logger.info("第 %d 轮工具调用：%s", iteration, describe_calls(calls))
        for call in calls:
            fn = call.get("function", {})
            outcome = dispatch(fn.get("name", ""), fn.get("arguments", ""))
            trace.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": json.dumps(outcome, ensure_ascii=False),
            })

    raise ToolLoopError(f"工具调用轮数达到上限 {max_iterations}，仍未产出最终回答")


async def run_agent_stream(
    client,
    messages: list[Message],
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AsyncIterator[str]:
    """跑工具循环，最后一步用流式输出（先报进度，再流式给答案）。"""
    trace: list[Message] = list(messages)
    tools = schemas() or None

    for iteration in range(1, max_iterations + 1):
        msg = await client.chat_message(trace, tools=tools)
        trace.append(msg)

        calls = msg.get("tool_calls") or []
        if not calls:
            async for delta in client.stream(trace[:-1]):
                yield delta
            return

        yield f"\n[调用工具] {describe_calls(calls)}\n"
        for call in calls:
            fn = call.get("function", {})
            outcome = dispatch(fn.get("name", ""), fn.get("arguments", ""))
            trace.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": json.dumps(outcome, ensure_ascii=False),
            })

    raise ToolLoopError(f"工具调用轮数达到上限 {max_iterations}")
