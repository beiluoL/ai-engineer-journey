"""工具注册表测试（milestones/08）。"""

from assistant.tools import REGISTRY, describe_calls, dispatch, schemas, tool


def test_builtin_tools_registered():
    assert "add" in REGISTRY and "multiply" in REGISTRY and "get_weather" in REGISTRY


def test_schema_shape():
    add_schema = next(s for s in schemas() if s["function"]["name"] == "add")
    params = add_schema["function"]["parameters"]
    assert params["type"] == "object"
    assert params["properties"]["a"]["type"] == "number"
    assert set(params["required"]) == {"a", "b"}
    assert "description" in add_schema["function"]


def test_dispatch_executes():
    assert dispatch("add", '{"a": 2, "b": 3}') == {"result": 5.0}
    assert dispatch("multiply", '{"a": 4, "b": 5}')["result"] == 20.0


def test_dispatch_unknown_tool_returns_error_not_raise():
    """未知工具要作为结果回灌，让模型自己纠正，而不是崩。"""
    out = dispatch("no_such_tool", "{}")
    assert "error" in out and "no_such_tool" in out["error"]


def test_dispatch_bad_json_returns_error():
    assert "error" in dispatch("add", "这不是 JSON")


def test_dispatch_wrong_args_returns_error():
    assert "error" in dispatch("add", '{"a": 1}')


def test_custom_tool_can_be_registered():
    @tool
    def echo(text: str) -> str:
        """原样返回输入。"""
        return text

    assert dispatch("echo", '{"text": "hi"}') == {"result": "hi"}
    del REGISTRY["echo"]


def test_describe_calls_for_logging():
    calls = [{"id": "1", "function": {"name": "add", "arguments": '{"a":1,"b":2}'}}]
    assert "add" in describe_calls(calls)
