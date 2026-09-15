"""assistant —— Project 01 的核心包。

模块划分（对应 00-python-foundation/10-module.md）：
- config:  读取配置与 API Key（对应 15-env）
- errors:  异常层级（对应 12-exception）
- client:  LLMClient 类，封装对 DeepSeek API 的调用（对应 11-class / 14-json）
"""

from assistant.client import LLMClient
from assistant.config import Config, load_config
from assistant.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
)

__all__ = [
    "Config",
    "load_config",
    "LLMClient",
    "LLMError",
    "LLMConfigError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMResponseError",
]
