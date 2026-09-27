"""Project 05 —— 注册表测试。

每个用例都对应一个"真机上才会暴露"的问题：
参数类型纠偏、必填缺失、多余参数、工具抛异常、tool 消息格式。
"""

from __future__ import annotations

import pytest

from agent.errors import InvalidToolCallError, ToolError
from agent.registry import ToolRegistry, _coerce, assert_valid_schema
from agent.tools import Tool, ToolCall, ToolResult


class _Add(Tool):
    name = "add"
    description = "两数相加"

    def run(self, **kwargs) -> str:                    # type: ignore[override]
        a, b = kwargs["a"], kwargs["b"]
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise ToolError(f"add 只接受数字，收到 {type(a).__name__}/{type(b).__name__}")
        return str(a + b)


def _boom() -> str:
    raise RuntimeError("工具内部炸了")
    # noqa: unreachable


def _need(x: int) -> str:
    """必须给 x。"""
    return f"got {x}"


# --------------------------------------------------------------------------
# 注册与 schema
# --------------------------------------------------------------------------
def test_registry_defaults_to_builtin_tools() -> None:
    names = ToolRegistry().names()
    assert names == ["calculator", "now", "rag_search"]


def test_register_and_names_sorted() -> None:
    reg = ToolRegistry()
    reg.register(_Add())
    assert reg.names() == ["add", "calculator", "now", "rag_search"]


def test_all_schemas_are_valid() -> None:
    for schema in ToolRegistry().schemas():
        assert_valid_schema(schema)


def test_schemas_are_function_objects_not_inner_dicts() -> None:
    """曾经这里返回的是内层 function 对象，服务端一直 422 missing field `type`。"""
    tools = ToolRegistry().schemas()
    assert all(t["type"] == "function" for t in tools), "最外层必须有 type"
    assert all("function" in t and "name" in t["function"] for t in tools), "必须有 function 外壳"


def test_required_refers_to_real_properties() -> None:
    schema = ToolRegistry().schema_of("rag_search")
    assert schema["parameters"]["required"] == ["query"]
    assert "query" in schema["parameters"]["properties"]


# --------------------------------------------------------------------------
# 参数校验与纠偏
# --------------------------------------------------------------------------
def test_coerce_string_to_integer() -> None:
    """小模型最常见的失误：把整数写成字符串。"""
    assert _coerce("3", "integer") == (3, None)


def test_coerce_float_to_integer() -> None:
    assert _coerce(3.0, "integer") == (3, None)


def test_coerce_bad_value_reports_error() -> None:
    value, err = _coerce("abc", "integer")
    assert value is None and err and "期望整数" in err


def test_coerce_bool_is_not_integer() -> None:
    """布尔是 int 的子类，不纠偏会导致 True 被当成 1。"""
    assert _coerce(True, "integer") == (None, "期望整数，收到布尔值")


def test_registry_coerces_arguments(reg: ToolRegistry) -> None:
    result = reg.call(ToolCall(id="c1", name="add", arguments={"a": "4", "b": 6}))
    assert result.ok and result.output == "10", "字符串 '4' 必须被纠偏成整数 4"


def test_registry_reports_missing_required(reg: ToolRegistry) -> None:
    result = reg.call(ToolCall(id="c1", name="_need", arguments={}))
    assert not result.ok and "缺少必填参数「x」" in result.error


def test_registry_reports_unknown_parameter(reg: ToolRegistry) -> None:
    result = reg.call(ToolCall(id="c1", name="add", arguments={"a": 1, "b": 2, "c": 3}))
    assert not result.ok and "参数「c」不存在" in result.error


def test_registry_unknown_tool_returns_error_not_exception() -> None:
    """一次调用失败不该打死整轮任务。"""
    result = ToolRegistry().call(ToolCall(id="c9", name="不存在的工具", arguments={}))
    assert isinstance(result, ToolResult)
    assert not result.ok
    assert "当前可用" in result.error


# --------------------------------------------------------------------------
# 异常兜底
# --------------------------------------------------------------------------
def test_tool_exception_becomes_tool_result(reg: ToolRegistry) -> None:
    class _Boom(Tool):
        name = "boom"
        description = "永远失败"

        def run(self, **kwargs) -> str:                 # type: ignore[override]
            raise RuntimeError("工具内部炸了")

    reg.register(_Boom())
    result = reg.call(ToolCall(id="c1", name="boom", arguments={}))
    assert not result.ok
    assert "RuntimeError" in result.error


def test_registry_call_rejects_non_toolcall() -> None:
    with pytest.raises(InvalidToolCallError):
        ToolRegistry(tools=[]).call({"name": "add"})  # type: ignore[arg-type]


def test_call_many_records_results(reg: ToolRegistry) -> None:
    results = reg.call_many([
        ToolCall(id="1", name="add", arguments={"a": 1, "b": 2}),
        ToolCall(id="2", name="nope", arguments={}),
    ])
    assert [r.ok for r in results] == [True, False]
    assert len(reg.last_results) == 2


# --------------------------------------------------------------------------
# 回灌格式
# --------------------------------------------------------------------------
def test_dispatch_produces_protocol_tool_message(reg: ToolRegistry) -> None:
    result = reg.call(ToolCall(id="call_1", name="add", arguments={"a": 1, "b": 2}))
    message = reg.dispatch([], result)
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call_1"
    assert message["name"] == "add"
    assert "content" in message


def test_failed_result_is_rendered_as_text() -> None:
    result = ToolResult(call_id="c1", name="nope", error="未知工具")
    assert result.render().startswith("[工具执行失败]")


def test_register_function_uses_docstring(reg: ToolRegistry) -> None:
    assert reg.schema_of("_need")["description"] == "必须给 x。"
