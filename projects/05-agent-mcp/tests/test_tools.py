"""Project 05 —— 工具层测试。

这里的重点是：**每个断言背后都是一个真实踩过的坑**。
比如"字符串 "3" 必须能被纠偏成整数"，是因为小模型经常这么返回。
"""

from __future__ import annotations

import json

import pytest

from agent.errors import ToolError, ToolSchemaError
from agent.tools import (
    BUILTIN_CORPUS,
    CalculatorTool,
    FunctionTool,
    NowTool,
    RagSearchTool,
    Tool,
    ToolCall,
    calculator,
    function_to_schema,
    keyword_search,
    make_http_search_tool,
    now_utc,
)


# --------------------------------------------------------------------------
# rag_search —— 检索即工具
# --------------------------------------------------------------------------
def test_keyword_search_returns_hits() -> None:
    out = keyword_search("Project 04 会话落盘", k=2)
    assert out.splitlines()[0].startswith("[1]") and "p04-session" in out
    assert len(out.splitlines()) == 2, "k=2 应该正好两行"


def test_keyword_search_top_k_is_respected() -> None:
    out = keyword_search("project", k=5)
    assert len(out.splitlines()) == 5, "命中 10 条时 k=5 只能返回 5 行"


def test_keyword_search_k_larger_than_corpus() -> None:
    assert len(keyword_search("project", k=99).splitlines()) == len(BUILTIN_CORPUS)


def test_keyword_search_miss_returns_hint() -> None:
    """英文噪声查询不该命中任何中文语料 —— 之前用「字符级重叠」兜底时这里会误命中。"""
    out = keyword_search("zzzz not in corpus")
    assert "没有" in out


def test_keyword_search_handles_chinese_without_segmentation() -> None:
    """中文没空格，靠二元组切分才能命中「会话与多轮」。"""
    out = keyword_search("会话怎么落盘")
    assert "p04-session" in out


def test_keyword_search_terms_helper() -> None:
    from agent.tools import _terms

    assert "会话" in _terms("会话怎么落盘")
    assert _terms("Project 04 会话怎么落盘") == [
        "会话怎么落盘", "会话", "话怎", "怎么", "么落", "落盘",
        "Project", "04",
    ]


def test_keyword_search_rejects_empty_query() -> None:
    with pytest.raises(ToolError):
        keyword_search("   ")


def test_keyword_search_rejects_non_positive_k() -> None:
    with pytest.raises(ToolError):
        keyword_search("rag", k=0)


def test_corpus_is_prefixed_by_project() -> None:
    tags = " ".join(d["tags"] for d in BUILTIN_CORPUS)
    assert "project04" in tags and "project05" in tags


def test_rag_search_tool_is_swappable_backend() -> None:
    tool = RagSearchTool(backend=lambda query, k: f"({query},{k})")
    assert tool.run(query="x", k=4) == "(x,4)"


def test_http_search_tool_uses_injected_client(monkeypatch) -> None:
    """同一个工具名、另一个后端：证明「工具」只是能力描述，实现可插拔。"""
    import agent.tools as tools_mod

    seen: dict[str, object] = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"context": [{"text": "来自 Project 04 服务的上下文"}]}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None):
            seen["url"] = url
            seen["payload"] = json
            return FakeResp()

    monkeypatch.setattr(tools_mod.httpx, "Client", lambda **_: FakeClient())

    tool = make_http_search_tool("http://127.0.0.1:8123", k=2)
    assert tool.run(query="project04") == "- 来自 Project 04 服务的上下文"
    assert seen["url"] == "http://127.0.0.1:8123/ask"
    assert seen["payload"] == {"query": "project04", "top_k": 2}


# --------------------------------------------------------------------------
# calculator —— 安全沙箱
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("expr", "expected"),
    [("1+2", "3"), ("(12+8)*3/7", "8.571428571428571"), ("2**10", "1024"), ("7//2", "3"), ("-5+1", "-4")],
)
def test_calculator_arithmetic(expr: str, expected: str) -> None:
    assert calculator(expr) == expected


@pytest.mark.parametrize("evil", ['__import__("os")', "open('/etc/passwd')", "__loader__", "eval('1')"])
def test_calculator_rejects_not_just_arithmetic(evil: str) -> None:
    """这是整章最重要的一条断言：工具绝不能给模型任意代码执行权。"""
    with pytest.raises(ToolError):
        calculator(evil)


def test_calculator_sandbox_error_mentions_whitelist() -> None:
    with pytest.raises(ToolError, match="不允许的表达式成分"):
        calculator("int(1)")


def test_calculator_rejects_empty() -> None:
    with pytest.raises(ToolError):
        calculator("   ")


def test_calculator_division_by_zero() -> None:
    with pytest.raises(ToolError, match="求值失败"):
        calculator("1/0")


# --------------------------------------------------------------------------
# schema 推导
# --------------------------------------------------------------------------
def _add(a: int, b: int = 2) -> int:
    """两数相加。"""
    return a + b


def test_function_to_schema_from_signature() -> None:
    fn = function_to_schema(_add)
    assert fn["name"] == "_add"
    assert fn["parameters"]["properties"]["a"]["type"] == "integer"
    assert fn["parameters"]["required"] == ["a"], "有默认值的 b 不该进 required"


def test_function_to_schema_documented() -> None:
    fn = function_to_schema(_add)
    assert "两数相加" in fn["description"]


def test_function_tool_schema_is_valid_json() -> None:
    tool = FunctionTool(_add, name="add")
    schema = tool.schema()
    assert schema["type"] == "function"
    payload = json.dumps(schema, ensure_ascii=False)
    assert json.loads(payload) == schema


def test_function_tool_run_returns_str() -> None:
    assert FunctionTool(_add, name="add").run(a=1) == "3"


def test_builtin_tools_are_tool_subclasses() -> None:
    for tool in (CalculatorTool(), NowTool(), RagSearchTool()):
        assert isinstance(tool, Tool)
        assert tool.name and tool.description


def test_now_tool_returns_timestamp() -> None:
    assert "UTC" in now_utc()


# --------------------------------------------------------------------------
# ToolCall 自身校验
# --------------------------------------------------------------------------
def test_toolcall_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        ToolCall(id="", name="x")


def test_toolcall_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        ToolCall(id="1", name="")


def test_toolcall_rejects_non_dict_arguments() -> None:
    with pytest.raises(ToolSchemaError):
        ToolCall(id="1", name="x", arguments="query=abc")  # type: ignore[arg-type]


def test_toolcall_normalizes_none_arguments() -> None:
    call = ToolCall(id="1", name="x", arguments=None)  # type: ignore[arg-type]
    assert call.arguments == {}
