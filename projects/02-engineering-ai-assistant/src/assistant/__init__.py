"""engineering-ai-assistant —— 工程化的 Python AI 助手。

分层（对应 milestones/00-classes-and-oop.md）：

    settings     —— 集中式配置（frozen dataclass，依赖注入）
    logging_setup—— 日志配置（唯一配置点）
    errors       —— 异常层级
    conversation —— 对话历史（封装状态）
    client       —— BaseLLMClient 抽象 + DeepSeekClient(httpx async) + FakeClient
    service      —— 业务流程（只依赖抽象，不依赖具体厂商）
    cli          —— 命令行入口
    api          —— FastAPI 入口（可选依赖 fastapi / uvicorn）

上层只依赖抽象，所以 CLI / FastAPI / 测试可以共用同一套业务逻辑。
"""

from assistant.client import BaseLLMClient, DeepSeekClient, FakeClient
from assistant.conversation import Conversation
from assistant.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
)
from assistant.service import AssistantService
from assistant.settings import Settings

__all__ = [
    "BaseLLMClient",
    "DeepSeekClient",
    "FakeClient",
    "Conversation",
    "AssistantService",
    "Settings",
    "LLMError",
    "LLMConfigError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMResponseError",
]
