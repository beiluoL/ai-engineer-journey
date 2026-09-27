"""Milestone 08 实验：Function Calling 的工具循环。

用 FakeClient 编排「先要调工具、再给答案」的两轮脚本，真跑 run_agent()，
看四件事：
1. 模型返回的是 tool_calls 而不是 content；
2. 本地函数真的被执行（不是模型自己算）；
3. 结果以 role="tool" 回灌（带 tool_call_id）后才会有第二轮；
4. 超出轮数上限会抛 ToolLoopError，而不是死循环。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from assistant.agent import run_agent  # noqa: E402
from assistant.client import FakeClient  # noqa: E402
from assistant.errors import ToolLoopError  # noqa: E402
from assistant.tools import dispatch, schemas  # noqa: E402


def call(name: str, args: dict, cid: str = "call_1") -> dict:
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


def main() -> None:
    print("===== 1. 发给模型的工具清单（JSON Schema）=====")
    for s in schemas():
        fn = s["function"]
        print(f"  {fn['name']:<10} {fn['description']}")
        print(f"             参数: {list(fn['parameters'].get('properties', {}))}")

    print("\n===== 2. 本地执行：模型说要调，其实是你自己在算 =====")
    for name, args in (("add", {"a": 3, "b": 4}), ("multiply", {"a": 6, "b": 7}),
                       ("get_weather", {"city": "深圳"})):
        print(f"  dispatch({name}, {args}) → {dispatch(name, json.dumps(args))}")
    print("  dispatch(不存在, ...) →", dispatch("no_such_tool", "{}"))
    print("  → 工具出错也要作为 {'error': ...} 返回，让模型自己纠正，而不是崩掉")

    print("\n===== 3. 完整两轮循环：tool_calls → 执行 → 回灌 → 最终回答 =====")
    client = FakeClient(script=[
        {"role": "assistant", "content": "", "tool_calls": [call("add", {"a": 3, "b": 4})]},
        {"role": "assistant", "content": "3 + 4 = 7"},
    ])
    answer, trace = asyncio.run(run_agent(
        client, [{"role": "user", "content": "3 加 4 等于几？"}]))
    print("  最终回答:", answer)
    print("  轨迹共", len(trace), "条：")
    for i, m in enumerate(trace):
        extra = ""
        if m.get("tool_calls"):
            extra = f"  tool_calls={[c['function']['name'] for c in m['tool_calls']]}"
        if m.get("role") == "tool":
            extra = f"  tool_call_id={m.get('tool_call_id')}"
        print(f"    [{i}] {m.get('role'):<9} {str(m.get('content'))[:44]!r}{extra}")
    print("  → 少了第 4 步（role=tool 回灌），模型就会凭空编一个结果")

    print("\n===== 4. 一轮就答完的情况（不需要工具）=====")
    client2 = FakeClient(script=[{"role": "assistant", "content": "深圳今天晴。"}])
    ans2, trace2 = asyncio.run(run_agent(
        client2, [{"role": "user", "content": "深圳天气？"}]))
    print("  最终回答:", ans2, "｜轨迹条数:", len(trace2), "（没有调用过工具）")

    print("\n===== 5. 一直要调工具 → 轮数上限抛错，不死循环 =====")
    loop_client = FakeClient(script=[
        {"role": "assistant", "content": "", "tool_calls": [call("add", {"a": i, "b": 1})]}
        for i in range(6)
    ])
    try:
        asyncio.run(run_agent(loop_client, [{"role": "user", "content": "一直加"}]))
    except ToolLoopError as exc:
        print("  ToolLoopError:", exc)
    print("  → 必须有上限：模型陷入循环时，没有上限就是无限烧钱")


if __name__ == "__main__":
    main()
