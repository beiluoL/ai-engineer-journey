"""Project 05 —— MCP（Model Context Protocol）子包（Milestone 07-09）。

    protocol.py   消息层：JSON-RPC 2.0 编解码、三个核心方法、stdio 帧格式（M07）
    server.py     服务端：把工具暴露给外部调用者（M08）
    client.py     客户端：拉起 server 子进程并桥接进 ToolRegistry（M09）

三章的顺序是刻意的：**先把协议写对，再写两端**。
直接照着某篇博客写 server/client，一旦消息形状不对，排查时会分不清
是「我写错了」还是「协议规定就是这样」。
"""

from .protocol import (
    ERROR_MESSAGES,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    JSONRPC_VERSION,
    METHOD_INITIALIZE,
    METHOD_NOT_FOUND,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    NOTIFY_INITIALIZED,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    SUPPORTED_VERSIONS,
    MCPError,
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
