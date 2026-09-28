"""Milestone 07/08/09 —— MCP 协议、Server、Client 的测试。

分三层，重点各不同：

- 协议层：**形状对不对**（id 配对、通知无 id、错误码、换行转义）
- Server：**错误分类对不对**（协议错误 vs 工具执行失败，这是最容易写混的）
- Client：真的拉起子进程跑一遍 —— 协议测试用 mock 是没意义的，
  因为 stdio 传输的所有坑（缓冲、flush、EOF）都只在真进程上出现。
"""

from __future__ import annotations

import json

import pytest

from agent.mcp import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_INITIALIZE,
    METHOD_NOT_FOUND,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    NOTIFY_INITIALIZED,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    ProtocolError,
    decode_frame,
    encode_frame,
    is_notification,
    is_response,
    make_error,
    make_notification,
    make_request,
    make_response,
    parse_message,
)
from agent.mcp.client import MCPClient, MCPClientError, MCPTool, mcp_tools, spawn_default_server
from agent.mcp.server import MCPServer, MCPToolSpec


def _echo_spec() -> MCPToolSpec:
    return MCPToolSpec(
        name="echo",
        description="回声",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        handler=lambda text: "你说了：" + text,
    )


# ─────────────────────────────────────────────────────── Milestone 07 协议层
class TestProtocolMessages:
    def test_request_has_id_and_method(self):
        msg = make_request(1, "tools/list", {"a": 1})
        assert msg == {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"a": 1}}

    def test_notification_has_no_id(self):
        """有没有 id 是区分请求与通知的**唯一**依据。"""
        msg = make_notification(NOTIFY_INITIALIZED)
        assert "id" not in msg
        assert is_notification(msg)

    def test_response_and_error_shapes(self):
        assert make_response(7, {"ok": True}) == {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}
        err = make_error(7, METHOD_NOT_FOUND, "nope")
        assert err["error"] == {"code": -32601, "message": "nope"}
        assert is_response(err)

    def test_error_without_id_is_allowed(self):
        """解析失败时我们不知道对方想问什么，协议允许 id 为 null。"""
        assert make_error(None, PARSE_ERROR, "bad")["id"] is None

    def test_error_data_attached(self):
        assert make_error(1, INTERNAL_ERROR, "x", data={"trace": "..."})["error"]["data"] == {"trace": "..."}


class TestFrames:
    def test_roundtrip(self):
        msg = make_request(1, "initialize")
        assert decode_frame(encode_frame(msg)) == msg

    def test_frame_is_single_line(self):
        """一帧必须只有一行 —— 否则 stdio 传输会把它切成两帧。"""
        frame = encode_frame(make_response(1, {"text": "a\nb"}))
        assert frame.count("\n") == 1
        assert frame.endswith("\n")

    def test_newline_in_content_is_escaped(self):
        """这是 stdio 传输最容易踩的坑：内容里的裸换行会打断帧。"""
        frame = encode_frame(make_response(1, {"text": "第一行\n第二行"}))
        assert "\\n" in frame  # 被序列化成转义序列
        assert "\n第一行" not in frame

    def test_decode_rejects_garbage(self):
        with pytest.raises(ProtocolError, match="不是合法 JSON"):
            decode_frame("{not json")

    def test_decode_rejects_non_object(self):
        with pytest.raises(ProtocolError, match="必须是 JSON 对象"):
            decode_frame("[1,2,3]")

    def test_decode_rejects_empty_line(self):
        with pytest.raises(ProtocolError, match="空行"):
            decode_frame("   ")


class TestValidation:
    def test_accepts_valid_request(self):
        parse_message(make_request(1, "tools/list"))

    def test_rejects_wrong_jsonrpc_version(self):
        with pytest.raises(ProtocolError, match="jsonrpc 必须是"):
            parse_message({"jsonrpc": "1.0", "id": 1, "method": "x"})

    def test_rejects_request_without_method(self):
        with pytest.raises(ProtocolError, match="缺少 method"):
            parse_message({"jsonrpc": "2.0", "id": 1})

    def test_rejects_both_result_and_error(self):
        with pytest.raises(ProtocolError, match="同时有 result 和 error"):
            parse_message({"jsonrpc": "2.0", "id": 1, "result": 1, "error": {"code": -1}})

    def test_notification_only_needs_method(self):
        parse_message(make_notification("notifications/initialized"))

    def test_rejects_message_with_neither(self):
        with pytest.raises(ProtocolError, match="既没有 id 也没有 method"):
            parse_message({"jsonrpc": "2.0"})


# ─────────────────────────────────────────────────────── Milestone 08 Server
class TestServerHandshake:
    def test_initialize_returns_version_and_info(self):
        result = MCPServer().handle(make_request(1, METHOD_INITIALIZE, {}))["result"]
        assert result["protocolVersion"] == PROTOCOL_VERSION
        assert result["serverInfo"]["name"]

    def test_unknown_version_falls_back(self):
        """版本不一致不报错，回服务端支持的 —— 客户端自己决定要不要继续。"""
        result = MCPServer().handle(make_request(1, METHOD_INITIALIZE, {"protocolVersion": "1999-01-01"}))["result"]
        assert result["protocolVersion"] == PROTOCOL_VERSION

    def test_calls_before_handshake_rejected(self):
        srv = MCPServer()
        resp = srv.handle(make_request(1, METHOD_TOOLS_LIST))
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        assert "尚未完成 initialize" in resp["error"]["message"]

    def test_notification_returns_none(self):
        """通知按协议不回应 —— 返回 None，主循环就不写任何东西。"""
        srv = MCPServer()
        assert srv.handle(make_notification(NOTIFY_INITIALIZED)) is None
        assert srv.initialized is True


class TestServerTools:
    def _ready(self) -> MCPServer:
        srv = MCPServer()
        srv.handle(make_request(0, METHOD_INITIALIZE, {}))
        srv.handle(make_notification(NOTIFY_INITIALIZED))
        srv.register(_echo_spec())
        return srv

    def test_tools_list_shape(self):
        tools = self._ready().handle(make_request(1, METHOD_TOOLS_LIST))["result"]["tools"]
        assert tools[0]["name"] == "echo"
        assert tools[0]["inputSchema"]["type"] == "object"
        # MCP 的形状里**没有** {"type":"function"} 外壳，那是客户端的事
        assert "type" not in tools[0] or tools[0]["type"] != "function"

    def test_tools_call_returns_content(self):
        result = self._ready().handle(make_request(1, METHOD_TOOLS_CALL, {"name": "echo", "arguments": {"text": "hi"}}))["result"]
        assert result["content"][0]["text"] == "你说了：hi"
        assert result["isError"] is False

    def test_tool_failure_is_iserror_not_jsonrpc_error(self):
        """最关键的一条：工具执行失败要包成 isError 的 content 返回，
        让调用方能看见并换个参数重试，而不是整轮被打死。"""
        srv = self._ready()
        srv.register(
            MCPToolSpec(name="boom", description="会炸", input_schema={"type": "object", "properties": {}},
                        handler=lambda: (_ for _ in ()).throw(RuntimeError("查不到")))
        )
        resp = srv.handle(make_request(1, METHOD_TOOLS_CALL, {"name": "boom"}))
        assert "error" not in resp  # 不是 JSON-RPC error
        assert resp["result"]["isError"] is True

    def test_unknown_tool_is_invalid_params(self):
        """工具名不存在是调用方的错（-32602），不是服务端内部错误（-32603）。
        选错码会让客户端以为是服务端崩了从而白重试。"""
        resp = self._ready().handle(make_request(1, METHOD_TOOLS_CALL, {"name": "nope"}))
        assert resp["error"]["code"] == INVALID_PARAMS

    def test_unknown_method_is_method_not_found(self):
        resp = self._ready().handle(make_request(1, "resources/list"))
        assert resp["error"]["code"] == METHOD_NOT_FOUND

    def test_bad_message_shape_returns_error(self):
        resp = MCPServer().handle({"jsonrpc": "1.0", "id": 1, "method": "x"})
        assert resp["error"]["code"] == INVALID_PARAMS

    def test_spec_rejects_non_object_schema(self):
        with pytest.raises(ValueError, match="必须是 object"):
            MCPToolSpec(name="x", description="", input_schema={"type": "array"}, handler=lambda: "")


class TestServerStdio:
    def test_run_stdio_processes_until_eof(self):
        """逐行读、逐条回。用 StringIO 模拟，不做真实进程（真进程在 Client 测试里）。"""
        import io

        srv = MCPServer()
        srv.register(_echo_spec())
        stdin = io.StringIO(
            encode_frame(make_request(1, METHOD_INITIALIZE, {}))
            + encode_frame(make_notification(NOTIFY_INITIALIZED))
            + encode_frame(make_request(2, METHOD_TOOLS_CALL, {"name": "echo", "arguments": {"text": "hi"}}))
        )
        stdout = io.StringIO()
        srv.run_stdio(stdin=stdin, stdout=stdout)
        lines = [json.loads(l) for l in stdout.getvalue().splitlines()]
        # 通知不产生响应，所以只有两条
        assert len(lines) == 2
        assert lines[0]["result"]["protocolVersion"] == PROTOCOL_VERSION
        assert lines[1]["result"]["content"][0]["text"] == "你说了：hi"

    def test_run_stdio_reports_parse_error(self):
        import io

        stdout = io.StringIO()
        MCPServer().run_stdio(stdin=io.StringIO("{bad\n"), stdout=stdout)
        resp = json.loads(stdout.getvalue())
        assert resp["error"]["code"] == PARSE_ERROR


# ─────────────────────────────────────────────────────── Milestone 09 Client
@pytest.fixture(scope="module")
def live_client():
    """真的拉起一个 server 子进程。

    这是整个 MCP 三章里最值钱的测试：stdio 的缓冲、flush、EOF、握手顺序，
    全都只在真进程上暴露，用 mock 一片绿。
    """
    client = spawn_default_server()
    client.start()
    client.initialize()  # 握手必须在 fixture 里完成：后续测试直接用
    yield client
    client.close()


class TestClientAgainstRealServer:
    def test_initialize(self, live_client):
        assert live_client.protocol_version == PROTOCOL_VERSION
        assert live_client.server_info["name"] == "agent-mcp-server"

    def test_list_tools(self, live_client):
        names = {t["name"] for t in live_client.list_tools()}
        assert names == {"rag_search", "calculator", "now"}

    def test_call_tool(self, live_client):
        assert live_client.call_tool("calculator", {"expression": "6*7"}).strip() == "42"

    def test_call_search_tool(self, live_client):
        text = live_client.call_tool("rag_search", {"query": "Project 04 会话落盘"})
        assert "p04-session" in text

    def test_unknown_tool_raises(self, live_client):
        with pytest.raises(MCPClientError, match="没有名为"):
            live_client.call_tool("does_not_exist")

    def test_multiple_calls_keep_id_in_sync(self, live_client):
        """id 错位说明请求和响应配不上 —— 连续调用是对这条的最基本验证。"""
        for i in range(3):
            assert live_client.call_tool("calculator", {"expression": f"{i}+1"}).strip() == str(i + 1)

    def test_alive_and_reusable(self, live_client):
        assert live_client.alive


class TestBridge:
    def test_mcp_tool_wraps_into_llm_schema(self, live_client):
        tools = mcp_tools(live_client)
        echo = next(t for t in tools if t.name == "calculator")
        schema = echo.llm_schema()
        # 客户端负责补上这层外壳 —— 服务端不知道 LLM 的存在
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculator"
        assert schema["function"]["parameters"]["type"] == "object"

    def test_mcp_tool_run_calls_server(self, live_client):
        tool = MCPTool(live_client, {"name": "calculator", "description": "", "inputSchema": {"type": "object", "properties": {}}})
        assert tool.run(expression="2**10").strip() == "1024"

    def test_bridged_tools_register_into_registry(self, live_client):
        from agent.registry import ToolRegistry

        reg = ToolRegistry(mcp_tools(live_client))
        assert {"rag_search", "calculator", "now"} <= set(reg.names())
        result = reg.names() and None  # 占位，下面真正验证调用路径
        from agent.tools import ToolCall

        out = reg.call(ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"}))
        assert out.ok and out.output.strip() == "2"

    def test_missing_name_rejected(self, live_client):
        from agent.mcp.client import MCPClientError as Err

        with pytest.raises(Err, match="缺少 name"):
            MCPTool(live_client, {"description": "x"})


class TestClientLifecycle:
    def test_use_before_start_raises(self):
        client = MCPClient(["echo"])
        with pytest.raises(MCPClientError, match="还没 start"):
            client.request("initialize")

    def test_context_manager_closes(self):
        with spawn_default_server() as client:
            client.initialize()
            assert client.alive
        assert not client.alive
