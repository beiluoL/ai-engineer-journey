"""错误层级：Project 01 的异常体系（对应 milestones/06-exception.md）。

设计原则：
- 调用方只需要捕获 LLMError 基类；
- 需要区分处理时再细分（如 429 限流可以重试，401 不可以）。
"""


class LLMError(Exception):
    """LLM 调用相关错误的基类。"""


class LLMConfigError(LLMError):
    """配置错误：例如 API Key 未设置。"""


class LLMAuthError(LLMError):
    """认证失败（HTTP 401/403）：Key 无效或过期，不应重试。"""


class LLMRateLimitError(LLMError):
    """触发限流（HTTP 429）：可等待后重试。"""


class LLMResponseError(LLMError):
    """响应不符合预期：HTTP 状态异常或 JSON 解析失败。"""
