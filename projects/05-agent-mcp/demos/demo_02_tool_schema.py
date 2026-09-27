"""Milestone 02 —— JSON Schema：告诉模型「工具长什么样、参数怎么填」。

运行：
    .venv/bin/python demos/demo_02_tool_schema.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.errors import ToolSchemaError
from agent.registry import ToolRegistry, _coerce
from agent.tools import CalculatorTool, ToolCall, function_to_schema


def head(text: str) -> None:
    print(f"\n{'=' * 74}\n{text}\n{'=' * 74}")


def show(payload, width: int = 700) -> None:
    """把 payload 当 JSON 打出来，缩进对齐。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print("  " + text[:width].replace("\n", "\n  ") + ("…" if len(text) > width else ""))


def main() -> int:
    head("① 完整的一段工具声明：模型真正看到的东西")
    schema = CalculatorTool().schema()
    show(schema)

    head("② 手写 schema 容易写的两种错，框架直接拦")
    try:
        function_to_schema  # noqa: B018
        from agent.tools import function_schema

        function_schema("broken", "描述", {"type": "string"})
    except ToolSchemaError as exc:
        print(f"  parameters.type 不是 object → ToolSchemaError: {exc}")
    try:
        function_schema("broken2", "描述", {"type": "object", "properties": {}, "required": ["nope"]})
    except ToolSchemaError as exc:
        print(f"  required 里的字段没有对应属性 → ToolSchemaError: {exc}")

    head("③ 签名推导：改了参数忘记改 schema 是最经典的线上事故")
    def search_old(k: int) -> str:
        return str(k)

    def search_new(k: int, mode: str = "fast") -> str:
        return f"{k}/{mode}"

    print("  改前 schema：required =", function_to_schema(search_old)["parameters"]["required"])
    print("  改后 schema：required =", function_to_schema(search_new)["parameters"]["required"])
    print("  → 自动推导跟着代码一起变，不存在「改了代码忘了改 schema」这种事故。")
    show(function_to_schema(search_new)["parameters"])

    head("④ 参数纠偏：模型给的类型不总是对的（小模型高频失误）")
    cases = [("3", "integer"), (3.0, "integer"), ("12", "number"), ("true", "boolean"), (1, "boolean"), ("x", "integer")]
    for raw, hint in cases:
        value, err = _coerce(raw, hint)
        flag = "✓" if err is None else "✗"
        print(f"  [{flag}] {raw!r:>7} + type={hint:<8} → {value!r:<12} {err or ''}")

    head("⑤ 真实派发：字符串 '4' 被纠偏成整数后才进 run()")
    reg = ToolRegistry()
    from agent.tools import Tool

    class Adder(Tool):
        name = "add"
        description = "两数相加"
        parameters = {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }

        def schema(self):
            from agent.tools import function_schema

            return function_schema(self.name, self.description, self.parameters)

        def run(self, **kwargs):
            a, b = kwargs["a"], kwargs["b"]
            print(f"       ↳ run() 拿到的类型：a={type(a).__name__}, b={type(b).__name__}")
            return str(a + b)

    reg.register(Adder())
    for arguments in [{"a": "4", "b": 6}, {"a": 1}, {"a": 1, "b": 2, "c": 3}]:
        r = reg.call(ToolCall(id="c", name="add", arguments=arguments))
        mark = "✓" if r.ok else "✗"
        print(f"  [{mark}] {json.dumps(arguments, ensure_ascii=False):<32} → ok={r.ok} {r.error or r.output}")

    head("⑥ 声明里没有的参数，模型编出来也要被挡住")
    r = reg.call(ToolCall(id="c", name="add", arguments={"a": 1, "b": 2, "c": 3}))
    print(f"  error = {r.error!r}")
    print(f"  回灌文本 = {r.render()!r}")

    head("⑦ 一个合格的 schema 的最小形态")
    from agent.registry import assert_valid_schema

    for s in ToolRegistry().schemas():
        assert_valid_schema(s)
        print(f"  ✓ {s['name']:<12} properties={list(s['parameters']['properties'])}"
              f"  required={s['parameters']['required']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
