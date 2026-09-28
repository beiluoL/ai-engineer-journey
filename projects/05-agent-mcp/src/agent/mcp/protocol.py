"""Project 05 —— MCP 协议层（Milestone 07）。

到这里之前，工具都是**写在进程里的类**：Agent 和工具同一个 Python 进程，
调用就是一次函数调用。这带来一个很实际的限制：

    工具换个项目就要复制一份代码；想用别人写的工具就得把他的源码搬进来。

MCP（Model Context Protocol）解决的就是这件事：
把「工具在哪、用什么语言写的」和「谁能调用它」彻底分开。

    Agent ──（MCP over stdio / HTTP）──> MCP Server（工具真正所在的地方）

这一章只做**协议层**：把 JSON-RPC 2.0 的消息编解码、三个核心方法、
以及 stdio 的帧格式写清楚并实现。Server（Milestone 08）和 Client（09）
都建立在这一层之上。

## 为什么是 JSON-RPC 2.0

自己发明一套 `{cmd: "search", args: [...]}` 也能跑，但会遇到三个本来
不用自己解决的问题：

1. **响应配对** —— 并发发出多个请求，回来的时候怎么知道哪个回答对应哪个？
   JSON-RPC 的 ``id`` 就是干这个的（而且它规定必须是字符串或数字，不能是 null）。
2. **错误语义** —— 是「方法不存在」还是「参数不对」还是「服务端炸了」？
   JSON-RPC 给了标准错误码，不用自己拍脑袋。
3. **单向消息** —— 有些消息不需要回应（比如"我初始化完了"）。
   JSON-RPC 叫它 *notification*，规则是**不带 id**。

## stdio 传输的帧格式

一行一个 JSON 对象，用换行分隔。为什么不用 HTTP 那套：
Server 是客户端**自己拉起来的子进程**，用 stdin/stdout 最省事 ——
不用挑端口、不用处理防火墙、进程退出连接自然就没了。

代价只有一个：**消息内部不能有裸换行**。JSON 序列化会把 ``\\n`` 转义成
``\\\\n``，所以只要走 ``json.dumps`` 就是安全的 —— 但如果你手拼字符串，
一条带换行的工具输出就会把协议帧打断。这是本章最容易踩的坑。
"""

from __future__ import annotations

import json
from typing import Any

__all__ = [
    "JSONRPC_VERSION",
    "PROTOCOL_VERSION",
    "SUPPORTED_VERSIONS",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "ERROR_MESSAGES",
    "METHOD_INITIALIZE",
    "METHOD_TOOLS_LIST",
    "METHOD_TOOLS_CALL",
    "NOTIFY_INITIALIZED",
    "MCPError",
    "ProtocolError",
    "make_request",
    "make_notification",
    "make_response",
    "make_error",
    "is_notification",
    "is_response",
    "encode_frame",
    "decode_frame",
    "parse_message",
]

JSONRPC_VERSION = "2.0"

#: MCP 协议版本。initialize 握手时双方要对齐它。
#: 2024-11-05 是第一个被广泛实现的版本，2025-06-18 起加入了 streamable HTTP。
PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_VERSIONS = ("2024-11-05", "2025-03-26")

# JSON-RPC 2.0 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

ERROR_MESSAGES = {
    PARSE_ERROR: "解析失败：不是合法 JSON",
    INVALID_REQUEST: "请求不合法",
    METHOD_NOT_FOUND: "方法不存在",
    INVALID_PARAMS: "参数不合法",
    INTERNAL_ERROR: "服务端内部错误",
}

# MCP 的三个核心方法
METHOD_INITIALIZE = "initialize"
METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"
#: 客户端初始化完成后发的单向通知（没有 id，服务端不回）
NOTIFY_INITIALIZED = "notifications/initialized"


class MCPError(Exception):
    """MCP 层面的错误基类。"""


class ProtocolError(MCPError):
    """消息不符合 JSON-RPC 2.0 / MCP 的形状。"""


# --------------------------------------------------------------------------- 构造
def make_request(req_id: int | str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造一条请求。

    ``id`` 是必须的：没有它就变成了 notification，收不到响应 ——
    而 initialize / tools/list / tools/call 三个方法全都要等结果。
    """
    payload: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def make_notification(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造一条通知：**不带 id**，按协议规定对方不回应。"""
    payload: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def make_response(req_id: int | str, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}


def make_error(
    req_id: int | str | None,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    """构造一条错误响应。

    ``req_id`` 可以是 None —— 解析失败时我们根本不知道对方想问什么，
    协议允许这种时候回 ``"id": null``。
    """
    error: dict[str, Any] = {"code": code, "message": message or ERROR_MESSAGES.get(code, "")}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "error": error}


# --------------------------------------------------------------------------- 判别
def is_notification(msg: dict[str, Any]) -> bool:
    """有没有 id 是区分「请求」和「通知」的唯一依据。"""
    return "id" not in msg


def is_response(msg: dict[str, Any]) -> bool:
    return "result" in msg or "error" in msg


# --------------------------------------------------------------------------- 帧
def encode_frame(message: dict[str, Any]) -> str:
    """把一个消息对象编码成一帧（一行 JSON + 换行）。

    必须用 ``json.dumps`` 而不是手工拼字符串：工具输出里含有换行是很常见的事，
    只有序列化才会把它们转义掉。手拼的话一帧会被换行切成两帧，
    对端解析到第二半时直接 PARSE_ERROR —— 而且很难从日志看出为什么。
    """
    return json.dumps(message, ensure_ascii=False) + "\n"


def decode_frame(line: str) -> dict[str, Any]:
    """把一行解码成消息对象。非法 JSON 抛 ``ProtocolError``。"""
    text = line.strip()
    if not text:
        raise ProtocolError("空行不是一帧")
    try:
        msg = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"不是合法 JSON：{exc}") from exc
    if not isinstance(msg, dict):
        raise ProtocolError(f"消息必须是 JSON 对象，收到的是 {type(msg).__name__}")
    return msg


def parse_message(msg: dict[str, Any]) -> None:
    """校验一条消息是否符合 JSON-RPC 2.0，不合法就抛 ``ProtocolError``。

    校验要做在**处理之前**：不然一个缺 method 的消息会一路走到
    dispatch，抛出的就是 KeyError 而不是「请求不合法」，排查方向完全错了。
    """
    if msg.get("jsonrpc") != JSONRPC_VERSION:
        raise ProtocolError(f"jsonrpc 必须是 '{JSONRPC_VERSION}'，收到 {msg.get('jsonrpc')!r}")
    if "id" not in msg:
        # notification：只要求有 method
        if "method" not in msg:
            raise ProtocolError("消息既没有 id 也没有 method")
        return
    if is_response(msg):
        if "result" in msg and "error" in msg:
            raise ProtocolError("响应不能同时有 result 和 error")
        return
    if "method" not in msg:
        raise ProtocolError("请求缺少 method")
    if not isinstance(msg.get("method"), str):
        raise ProtocolError(f"method 必须是字符串，收到 {type(msg.get('method')).__name__!r}")
