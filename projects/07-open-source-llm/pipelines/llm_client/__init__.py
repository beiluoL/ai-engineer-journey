"""Open Source LLM 最小客户端。

对外只暴露 client.py 里的核心符号，方便 demo 直接
``from llm_client import call_chat, call_chat_stream``。
"""

from .client import (
    API_BASE,
    DEFAULT_MODEL,
    ChatResult,
    LLMError,
    StreamResult,
    Usage,
    call_chat,
    call_chat_stream,
    estimate_tokens,
    load_api_key,
    redacted,
)

__all__ = [
    "API_BASE",
    "DEFAULT_MODEL",
    "ChatResult",
    "LLMError",
    "StreamResult",
    "Usage",
    "call_chat",
    "call_chat_stream",
    "estimate_tokens",
    "load_api_key",
    "redacted",
]
