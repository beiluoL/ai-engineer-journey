"""异常层级（沿用 Project 02 的设计，按 Project 03 的新场景扩展）。

为什么要有自己的异常层级：
   上层只想写 `except LLMError`，不需要知道是 HTTP 429 还是 JSON 解析失败。
   把「外部世界的不确定性」翻译成「本项目自己的语言」，是分层的意义。

层级：
    LLMError
    ├── LLMConfigError        配置缺失（启动即失败，exit 2）
    ├── LLMAuthError          401/403 —— 不重试
    ├── LLMRateLimitError     429 —— 可重试
    ├── LLMResponseError      响应结构不符合预期
    ├── ContextWindowError    上下文超窗口（Chapter 07）
    ├── StructuredOutputError 结构化输出校验失败且重试耗尽（Chapter 03）
    └── ToolError             工具层错误（Chapter 08）
        ├── ToolNotFoundError     模型调用了不存在的工具
        └── ToolLoopError         工具循环超过轮数上限
"""

from __future__ import annotations


class LLMError(Exception):
    """所有本项目异常的基类。"""


class LLMConfigError(LLMError):
    """配置错误：缺 Key、参数类型不对。重试没用。"""


class LLMAuthError(LLMError):
    """认证失败：HTTP 401 / 403。不重试。"""


class LLMRateLimitError(LLMError):
    """触发限流：HTTP 429。可退避后重试。"""


class LLMResponseError(LLMError):
    """响应异常：非预期状态码、非 JSON、结构不对。"""


class ContextWindowError(LLMError):
    """上下文超出窗口：裁剪后仍然太长（Chapter 07）。"""


class StructuredOutputError(LLMError):
    """结构化输出解析/校验失败，且重试次数已耗尽（Chapter 03）。"""


class ToolError(LLMError):
    """工具层错误基类（Chapter 08）。"""


class ToolNotFoundError(ToolError):
    """模型调用了不存在的工具——应作为结果回灌，而不是让程序崩。"""


class ToolLoopError(ToolError):
    """工具循环超过 max_iterations（Chapter 08）。"""
