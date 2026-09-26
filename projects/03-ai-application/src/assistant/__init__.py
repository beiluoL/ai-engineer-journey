"""Project 03 — AI Application：Prompt / 结构化输出 / 流式 / 工具调用。"""

from assistant.client import BaseLLMClient, DeepSeekClient, FakeClient
from assistant.errors import (
    ContextWindowError,
    LLMAuthError,
    LLMConfigError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    StructuredOutputError,
    ToolError,
    ToolLoopError,
    ToolNotFoundError,
)
from assistant.memory import Conversation, SessionStore, validate_messages
from assistant.prompts import PromptTemplate
from assistant.service import ChatService, build_service
from assistant.settings import Settings
from assistant.tools import dispatch, schemas, tool

__all__ = [
    "BaseLLMClient", "DeepSeekClient", "FakeClient",
    "LLMError", "LLMConfigError", "LLMAuthError", "LLMRateLimitError",
    "LLMResponseError", "ContextWindowError", "StructuredOutputError",
    "ToolError", "ToolLoopError", "ToolNotFoundError",
    "Conversation", "SessionStore", "validate_messages",
    "PromptTemplate", "ChatService", "build_service", "Settings",
    "tool", "schemas", "dispatch",
]
