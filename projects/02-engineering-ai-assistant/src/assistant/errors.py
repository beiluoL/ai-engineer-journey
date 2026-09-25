"""异常层级（对应 milestones/00-classes-and-oop.md 的分层设计）。

设计原则：

- 调用方只需要捕获 LLMError 基类；
- 需要区分处理时再细分：
  - LLMConfigError    —— 配置问题，重试也没用
  - LLMAuthError      —— 401/403，Key 有问题，不应重试
  - LLMRateLimitError —— 429，可以退避后重试
  - LLMResponseError  —— 响应不符合预期 / 网络错误
"""


class LLMError(Exception):
    """LLM 调用相关错误的基类。"""


class LLMConfigError(LLMError):
    """配置错误：例如 API Key 未设置、base_url 不合法。"""


class LLMAuthError(LLMError):
    """认证失败（HTTP 401/403）：Key 无效或过期，不应重试。"""


class LLMRateLimitError(LLMError):
    """触发限流（HTTP 429）：可退避后重试。"""


class LLMResponseError(LLMError):
    """响应不符合预期：HTTP 状态异常、JSON 解析失败、字段缺失。"""
