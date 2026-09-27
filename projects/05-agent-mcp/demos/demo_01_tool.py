"""Milestone 01 —— 工具就是「能被模型调用的 Python 函数」。

运行：
    .venv/bin/python demos/demo_01_tool.py

这一版只做离线部分，不发任何网络请求。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.errors import ToolError
from agent.registry import ToolRegistry
from agent.tools import (
    BUILTIN_CORPUS,
    CalculatorTool,
    FunctionTool,
    NowTool,
    RagSearchTool,
    Tool,
    ToolCall,
    ToolResult,
    calculator,
    function_to_schema,
    keyword_search,
)


def head(text: str) -> None:
    print(f"\n{'=' * 74}\n{text}\n{'=' * 74}")


def main() -> int:
    head("① 三个内置工具，都是同一个接口")
    for tool in (RagSearchTool(), CalculatorTool(), NowTool()):
        assert isinstance(tool, Tool)
        print(f"  name = {tool.name!r}")
        print(f"  desc = {tool.description[:46]}…")
    print(f"\n语料共 {len(BUILTIN_CORPUS)} 条，工具返回类型："
          f"{type(RagSearchTool().run(query='rag'))}")

    head("② 检索即工具：Agent 版 RAG 的入场券")
    out = keyword_search("Project 04 会话落盘", k=2)
    for line in out.splitlines():
        print("  " + line)
    print("\n  —— 关键区别：检索不再藏在 pipeline 里，而是被模型当工具决定要不要调。")

    head("③ 工具执行结果永远是 ToolResult，不是「抛异常 / 返回值」二选一")
    reg = ToolRegistry()
    ok = reg.call(ToolCall(id="c1", name="rag_search", arguments={"query": "Project 05 Agent"}))
    bad = reg.call(ToolCall(id="c2", name="不存在", arguments={}))
    print(f"  正常  → ok={ok.ok}  output={ok.output[:46]!r}")
    print(f"  失败  → ok={bad.ok}  error={bad.error!r}")
    print(f"\n  ToolResult.render() 对模型来说没有区别：\n    {bad.render()}")

    head("④ 计算工具：给模型算数，但绝不给它代码执行权")
    for expr in ["(12+8)*3/7", "2**10", "17//5"]:
        print(f"  calculator({expr!r}) = {calculator(expr)}")
    evil = "__import__('os').getcwd()"
    try:
        # 故意展示危险写法：模型输出的任意字符串被 eval 执行时会发生什么
        victim = eval(evil)  # noqa: S307
        print(f"  同一串输入交给 eval → 成功执行，读到了当前目录：{victim}")
    except Exception as exc:  # noqa: BLE001
        print(f"  同一串输入交给 eval → 抛异常：{type(exc).__name__}: {exc}")
    try:
        calculator(evil)
    except ToolError as exc:
        print(f"  同一串输入交给 calculator → 直接拒绝：{exc}")

    head("⑤ 普通 Python 函数 = 工具（改签名不会忘记改 schema）")

    def recall(user_id: int, limit: int = 5) -> str:
        """按 id 查这个人最近的备忘，最多返回 limit 条。"""
        return f"user#{user_id} 最近 {limit} 条"

    schema = function_to_schema(recall)
    print("  函数签名  recall(user_id: int, limit: int = 5)")
    print("  推导出的 schema：")
    print("    " + json.dumps(schema, ensure_ascii=False, indent=2).replace("\n", "\n    ")[:520])

    tool = FunctionTool(recall)
    reg.register(tool)
    print(f"\n  注册进注册表 → names = {reg.names()}")
    print(f"  调用 tool.run(user_id=7) → {tool.run(user_id=7)}")

    head("⑥ 注册表汇总：交给模型的就是这样一个数组")
    print(json.dumps(reg.schemas(), ensure_ascii=False, indent=2)[:680] + "\n  …")

    head("⑦ 一次失败的调用不该打死整轮任务")
    r = reg.call(ToolCall(id="c9", name="rag_search", arguments={"query": ""}))
    print(f"  空 query → ok={r.ok}  error={r.error!r}")
    print(f"  错误会原样回灌给模型（模型可以自己换个参数重试）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
