"""Project 05 —— MCP Server（Milestone 08）。

协议层（Milestone 07）只管消息长什么样。这一章是**真的把工具提供出去**：

    python -m agent.mcp.server        # 它就挂在 stdio 上等人来问

## 一个必须想清楚的设计：错误分两类

MCP 把错误分成两路，混用会让客户端完全没法处理：

    JSON-RPC error  —— 协议/调用层面的问题：方法不存在、参数不合法、工具名没注册
    result.isError  —— **工具本身执行了但失败了**：查不到、算式非法、超时

第二条很容易被写成第一条。区别在哪：

    工具名不存在 → 调用方该改代码（是 bug），走 JSON-RPC error
    查不到内容   → 这是工具的一次**正常结果**，模型看到后应该换个词再查

所以 `tools/call` 的实现里，工具抛异常要**包成 isError=True 的 content 返回**，
而不是往外抛 JSON-RPC error。否则就退化成 Milestone 01 讲过的那件事：
把「一次失败」变成「整轮任务被打死」。

## stdio 主循环的坑

读 stdin 要用**逐行迭代**，不能一次 read() 全读再处理 ——
客户端是「发一条、等一条」，你等 EOF 就等于永远等不到（它的 stdin 还开着）。

退出时机：stdin 关闭（EOF）就该退出。客户端进程没了，服务端留着没意义。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

from .protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_INITIALIZE,
    METHOD_NOT_FOUND,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    NOTIFY_INITIALIZED,
    PROTOCOL_VERSION,
    SUPPORTED_VERSIONS,
    is_notification,
    make_error,
    make_response,
    parse_message,
)

__all__ = ["MCPToolSpec", "MCPServer", "default_server", "main", "CallError"]


class CallError(Exception):
    """带 JSON-RPC 错误码的调用错误。

    为什么要有它：``ValueError`` 只能统一落到 INTERNAL_ERROR(-32603)，
    但「工具名不存在」是**调用方的问题**（-32602），不是服务端内部错误。
    错误码选错会误导客户端 —— 它看到 -32603 会以为是服务端崩了从而重试，
    而 -32602 正确地告诉它「改你的参数」。
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code

SERVER_NAME = "agent-mcp-server"
SERVER_VERSION = "0.1.0"


@dataclass(frozen=True)
class MCPToolSpec:
    """一个对外暴露的工具。

    ``input_schema`` 是**纯 JSON Schema**（不带外层 ``{"type":"function",...}``）。
    MCP 的 tools/list 返回的就是它；客户端要塞给 LLM 时才需要再包一层 ——
    那是客户端的事（Milestone 09），服务端不该知道 LLM 的存在。
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("工具名不能为空")
        if self.input_schema.get("type") != "object":
            raise ValueError(f"工具 {self.name} 的 inputSchema.type 必须是 object")

    def to_mcp(self) -> dict[str, Any]:
        """MCP 的 tools/list 里一项的形状。"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPServer:
    """一个最小可用的 MCP Server。

    刻意不做的事：并发、多协议版本协商的细节、resources/prompts 能力。
    这一章只想把「工具跨进程提供出去」这件事讲透。
    """

    name: str = SERVER_NAME
    version: str = SERVER_VERSION
    tools: dict[str, MCPToolSpec] = field(default_factory=dict)
    #: 握手完成之前，除 initialize 外一律拒绝 —— 协议要求这个顺序
    initialized: bool = False

    # ---------------------------------------------------------------- 注册
    def register(self, spec: MCPToolSpec) -> MCPToolSpec:
        self.tools[spec.name] = spec
        return spec

    def register_function(
        self,
        fn: Callable[..., str],
        *,
        name: str | None = None,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> MCPToolSpec:
        """把一个普通函数暴露成 MCP 工具，schema 从签名推导。"""
        from ..tools import function_to_schema  # 局部导入避免循环依赖

        tool_name = name or fn.__name__
        schema = function_to_schema(fn, name=tool_name, description=description)
        if input_schema is not None:
            schema = {"type": "object", **input_schema}
        return self.register(
            MCPToolSpec(
                name=tool_name,
                description=schema.get("description", description),
                input_schema=schema.get("parameters", {"type": "object", "properties": {}, "required": []}),
                handler=fn,
            )
        )

    # ---------------------------------------------------------------- 分发
    def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """处理一条消息，返回响应；通知返回 None（协议规定不回应）。"""
        req_id = msg.get("id")
        try:
            parse_message(msg)
        except Exception as exc:  # 协议错误也要按 JSON-RPC 的形状回
            return make_error(req_id, INVALID_PARAMS, str(exc))

        if is_notification(msg):
            if msg.get("method") == NOTIFY_INITIALIZED:
                self.initialized = True
            return None

        method = msg.get("method", "")
        params = msg.get("params") or {}

        # 握手前只认 initialize —— 这是协议规定的顺序
        if method != METHOD_INITIALIZE and not self.initialized:
            return make_error(req_id, METHOD_NOT_FOUND, f"尚未完成 initialize，不能调用 {method}")

        try:
            if method == METHOD_INITIALIZE:
                return make_response(req_id, self._initialize(params))
            if method == METHOD_TOOLS_LIST:
                return make_response(req_id, self._tools_list())
            if method == METHOD_TOOLS_CALL:
                return make_response(req_id, self._tools_call(params))
        except CallError as exc:
            return make_error(req_id, exc.code, str(exc))
        except KeyError as exc:
            return make_error(req_id, INVALID_PARAMS, f"缺少参数：{exc}")
        except Exception as exc:
            return make_error(req_id, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")

        return make_error(req_id, METHOD_NOT_FOUND, f"不支持的方法：{method}")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """握手。客户端声明它能用哪个版本，服务端回自己选的版本。

        版本不一致时不报错而是**取服务端支持的**——客户端自己决定要不要继续。
        真要拒绝应该回 error，但对一个教学实现来说，协商比拒绝有用。
        """
        requested = str(params.get("protocolVersion", PROTOCOL_VERSION))
        chosen = requested if requested in SUPPORTED_VERSIONS else PROTOCOL_VERSION
        return {
            "protocolVersion": chosen,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": self.name, "version": self.version},
        }

    def _tools_list(self) -> dict[str, Any]:
        return {"tools": [spec.to_mcp() for spec in self.tools.values()]}

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise CallError(INVALID_PARAMS, "tools/call 需要 params.name")
        spec = self.tools.get(name)
        if spec is None:
            # **工具名不存在是协议级错误**：调用方写错了，该改代码。
            # 走 -32602（参数不合法）而不是 -32603（内部错误）——
            # 后者会让客户端以为是服务端崩了从而发起重试。
            raise CallError(
                INVALID_PARAMS,
                f"没有名为 {name!r} 的工具。已注册：{', '.join(self.tools) or '（空）'}",
            )
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("params.arguments 必须是对象")
        try:
            text = spec.handler(**arguments)
        except Exception as exc:
            # **工具执行失败是工具的正常结果**：包成 isError 的 content 返回，
            # 让调用方（模型）看到后换个参数重试，而不是整轮被打死。
            return {
                "content": [{"type": "text", "text": f"[工具执行失败] {name}: {exc}"}],
                "isError": True,
            }
        return {"content": [{"type": "text", "text": str(text)}], "isError": False}

    # ---------------------------------------------------------------- 主循环
    def run_stdio(self, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
        """挂在 stdio 上一直服务，直到 stdin 关闭。

        必须**逐行**读：客户端是「发一条等一条」，等 EOF 就永远等不到。
        """
        from .protocol import decode_frame, encode_frame, make_error, PARSE_ERROR

        inp = stdin if stdin is not None else sys.stdin
        out = stdout if stdout is not None else sys.stdout

        for line in inp:
            if not line.strip():
                continue
            try:
                msg = decode_frame(line)
            except Exception as exc:
                # 解析失败时我们不知道 id，按协议回 null
                out.write(encode_frame(make_error(None, PARSE_ERROR, str(exc))))
            else:
                response = self.handle(msg)
                if response is not None:
                    out.write(encode_frame(response))
            out.flush()  # 不 flush 客户端会一直等 —— stdio 是块缓冲的


def default_server() -> MCPServer:
    """把 Project 05 的内置工具全部通过 MCP 暴露出去。

    这一步的意义：这些工具**不再只能被同一个进程里的 Agent 调用**了。
    """
    from ..tools import CalculatorTool, NowTool, RagSearchTool

    server = MCPServer()
    for tool in (RagSearchTool(), CalculatorTool(), NowTool()):
        outer = tool.schema()
        inner = outer.get("function", outer)  # 同上：剥掉 function 外壳
        server.register(
            MCPToolSpec(
                name=tool.name,
                description=inner.get("description", ""),
                input_schema=inner.get(
                    "parameters", {"type": "object", "properties": {}, "required": []}
                ),
                handler=lambda _t=tool, **kw: _t.run(**kw),
            )
        )
    return server


def main() -> int:
    default_server().run_stdio()
    return 0


if __name__ == "__main__":
    sys.exit(main())
