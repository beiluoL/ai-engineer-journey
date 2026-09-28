"""Project 05 —— MCP Client（Milestone 09）。

Milestone 08 把工具提供出去了，这一章是**真正去用它**：

    client = MCPClient([sys.executable, "-m", "agent.mcp.server"])
    client.start()
    client.initialize()          # 握手
    for tool in mcp_tools(client):
        registry.register(tool)  # 桥接进 Agent 的工具表

做完这三步，Agent 调用 MCP 工具和调用本地工具**没有任何区别** ——
它甚至不知道工具在另一个进程里。这就是 MCP 要的效果。

## 两个形状不一样：客户端负责转换

MCP 的 tools/list 返回的是**纯 JSON Schema**：

    {"name": "rag_search", "description": "...", "inputSchema": {...}}

而 LLM 的 function calling 要的是**两层外壳**：

    {"type": "function", "function": {"name": ..., "parameters": {...}}}

转换只能由客户端做：服务端不该知道 LLM 的存在（它可能同时服务于别的客户端），
而 LLM 也不该知道 MCP 的存在。这个转换层是 MCP 能接进任意模型的关键。

顺带一提，Milestone 03 真机踩过的那个 422（``tools[0]: missing field 'type'``）
就是漏了这层转换 —— 当时是手写 schema 漏了，这里是协议形状不同。道理一样。

## 握手顺序不能省

    initialize  →  notifications/initialized  →  其它方法

本项目服务端会在握手前拒绝一切其它调用。这不是刁难：服务端需要知道
客户端的能力（支持哪些协议版本、要不要资源订阅）才能正确工作。
跳过 notify 那一步，表现是「tools/list 返回 method not found」——
错误信息看起来像服务端没实现这个方法，非常误导。
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Sequence

from ..errors import AgentError
from ..tools import Tool
from .protocol import (
    METHOD_INITIALIZE,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    NOTIFY_INITIALIZED,
    PROTOCOL_VERSION,
    decode_frame,
    encode_frame,
    make_notification,
    make_request,
)

__all__ = ["MCPClientError", "MCPClient", "MCPTool", "mcp_tools", "spawn_default_server"]


class MCPClientError(AgentError):
    """MCP 客户端层面的错误：进程没起来、响应对不上、服务端报错。"""


class MCPClient:
    """一个 stdio 传输的 MCP 客户端。

    用**子进程**而不是 socket：不用挑端口、不用管防火墙、
    客户端进程退出时连接自然就没了 —— 代价是只能本机调用。
    """

    def __init__(self, command: Sequence[str], *, timeout: float = 30.0) -> None:
        self.command = list(command)
        self.timeout = timeout
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self.server_info: dict[str, Any] = {}
        self.protocol_version: str = ""

    # ---------------------------------------------------------------- 生命周期
    def start(self) -> "MCPClient":
        if self._proc is not None:
            return self
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,  # 行缓冲：否则服务端写完我们读不到
        )
        return self

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin and not self._proc.stdin.closed:
                self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None

    def __enter__(self) -> "MCPClient":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ---------------------------------------------------------------- 收发
    def _send(self, message: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise MCPClientError("客户端还没 start()")
        if not self.alive:
            raise MCPClientError("服务端进程已经退出")
        self._proc.stdin.write(encode_frame(message))
        self._proc.stdin.flush()  # 不 flush，服务端会一直等

    def _recv(self) -> dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise MCPClientError("客户端还没 start()")
        line = self._proc.stdout.readline()
        if not line:
            # 读到空 = 服务端关了 stdout。把 stderr 带上，否则只能看到「连接断了」
            err = ""
            if self._proc.stderr is not None:
                try:
                    err = self._proc.stderr.read() or ""
                except Exception:
                    err = ""
            raise MCPClientError(f"服务端关闭了连接。stderr：{err.strip()[:500]}")
        return decode_frame(line)

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """发一条请求并等它的响应。

        ``id`` 自增是必须的：并发时靠它配对。这里只用``读一行``的简单策略，
        因为本项目服务端是串行处理的 —— 真要并发得维护一个 id → future 的表。
        """
        req_id = self._next_id
        self._next_id += 1
        self._send(make_request(req_id, method, params))
        response = self._recv()

        if "error" in response:
            err = response["error"]
            raise MCPClientError(
                f"{method} 失败（code={err.get('code')}）：{err.get('message', '')}"
            )
        if response.get("id") != req_id:
            raise MCPClientError(
                f"响应 id 对不上：发出 {req_id}、收到 {response.get('id')}。"
                f"这说明请求与响应错位了（服务端并发处理时会这样）。"
            )
        return response.get("result")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """发一条通知。协议规定**不等响应**，所以这里也不读。"""
        self._send(make_notification(method, params))

    # ---------------------------------------------------------------- 三步走
    def initialize(self) -> dict[str, Any]:
        result = self.request(
            METHOD_INITIALIZE,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "agent-mcp-client", "version": "0.1.0"},
            },
        )
        self.protocol_version = str(result.get("protocolVersion", ""))
        self.server_info = dict(result.get("serverInfo") or {})
        # 这一步很多人会忘 —— 忘了的话后面所有调用都会被服务端拒
        self.notify(NOTIFY_INITIALIZED)
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        """返回 MCP 形状的原始工具定义（不转换）。"""
        result = self.request(METHOD_TOOLS_LIST)
        return list(result.get("tools", []))

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """调用一个工具，返回文本内容。

        工具执行失败（isError=True）时**抛异常**：MCP 把它放在 result 里，
        但对调用方来说它确实失败了 —— 由 ``MCPTool.run`` 决定怎么兜住。
        """
        result = self.request(METHOD_TOOLS_CALL, {"name": name, "arguments": arguments or {}})
        parts = result.get("content") or []
        text = "\n".join(
            part.get("text", "") for part in parts if isinstance(part, dict) and part.get("type") == "text"
        )
        if result.get("isError"):
            raise MCPClientError(text or f"工具 {name} 执行失败（没有返回内容）")
        return text


class MCPTool(Tool):
    """把一个远程 MCP 工具包装成本项目的 ``Tool``。

    桥接层存在的意义：Agent 和 ToolRegistry 完全不需要知道 MCP 的存在。
    """

    def __init__(self, client: MCPClient, spec: dict[str, Any]) -> None:
        self.client = client
        self.name = str(spec.get("name", ""))
        self.description = str(spec.get("description", ""))
        self.input_schema = dict(spec.get("inputSchema") or {"type": "object", "properties": {}, "required": []})
        if not self.name:
            raise MCPClientError("MCP 工具定义缺少 name")

    def schema(self) -> dict[str, Any]:
        """转成 LLM 要的两层外壳 —— 这层转换是客户端的职责。

        必须返回**完整外壳**而不是内层：``ToolRegistry.schema_of()`` 取的是
        ``tool.schema()["function"]``，少一层会 KeyError。
        服务端给的是纯 JSON Schema，客户端负责补壳，两边都不越界。
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def llm_schema(self) -> dict[str, Any]:
        """同 ``schema()``：本项目的 Tool 约定就是返回完整外壳。"""
        return self.schema()

    def run(self, **kwargs: Any) -> str:
        return self.client.call_tool(self.name, kwargs)


def mcp_tools(client: MCPClient) -> list[MCPTool]:
    """把服务端的所有工具都桥接过来。"""
    return [MCPTool(client, spec) for spec in client.list_tools()]


def spawn_default_server() -> MCPClient:
    """拉起本项目自带的 MCP Server。

    用 ``sys.executable`` 而不是硬编码 "python3"：客户端可能跑在 venv 里，
    写死解释器名字会拉起一个没装依赖的解释器，然后子进程秒退。
    """
    return MCPClient([sys.executable, "-m", "agent.mcp.server"])
