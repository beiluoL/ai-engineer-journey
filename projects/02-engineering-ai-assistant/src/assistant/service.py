"""业务流程层（对应 milestones/00-classes-and-oop.md 3.6 组合优先于继承）。

职责：

    记住对话历史 → 调 client → 把回答记回历史 → 返回

它**只依赖 BaseLLMClient 抽象**，不关心底层是 DeepSeek 还是 Fake。
因此 CLI / FastAPI / pytest 可以共用同一份业务逻辑。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from assistant.client import BaseLLMClient
from assistant.conversation import Conversation
from assistant.settings import Settings

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = "你是一个简洁、耐心的中文 AI 助手。"


class AssistantService:
    """AI 助手的业务流程。"""

    def __init__(
        self,
        client: BaseLLMClient,
        system_prompt: str | None = None,
        max_history_tokens: int = 2000,
    ) -> None:
        self._client = client
        self._max_history_tokens = max_history_tokens

        # 没显式给 system_prompt 时，尝试从 client 的配置里取（FakeClient 没有 settings）
        if system_prompt is None:
            settings = getattr(client, "settings", None)
            system_prompt = getattr(settings, "system_prompt", "") or DEFAULT_SYSTEM_PROMPT

        self._conversation = Conversation(system_prompt=system_prompt)

    # ---- 对外接口 ----

    async def ask(self, text: str) -> str:
        """一轮问答：记历史 → 调模型 → 记回答。"""
        if not text or not text.strip():
            raise ValueError("问题不能为空")

        self._conversation.add_user(text)
        dropped = self._conversation.trim(self._max_history_tokens)
        if dropped:
            logger.info("历史超预算，丢弃 %d 条最早消息", dropped)

        answer = await self._client.chat(self._conversation.messages)
        self._conversation.add_assistant(answer)
        return answer

    async def stream(self, text: str) -> AsyncIterator[str]:
        """流式问答：逐段产出，结束后把完整回答记入历史。"""
        self._conversation.add_user(text)
        self._conversation.trim(self._max_history_tokens)

        parts: list[str] = []
        async for chunk in self._client.stream(self._conversation.messages):
            parts.append(chunk)
            yield chunk
        self._conversation.add_assistant("".join(parts))

    def ask_sync(self, text: str) -> str:
        """同步包装：给 CLI 和测试用（不能在已有事件循环里调用）。"""
        return asyncio.run(self.ask(text))

    # ---- 会话管理 ----

    def reset(self) -> None:
        self._conversation.clear()

    async def aclose(self) -> None:
        """释放底层 client 的连接资源。"""
        await self._client.aclose()

    @property
    def history(self) -> list[dict[str, str]]:
        """只读快照。"""
        return self._conversation.messages

    def __len__(self) -> int:
        return len(self._conversation)


def build_service(settings: Settings, fake: bool = False) -> AssistantService:
    """工厂函数：按配置组装 service（依赖注入的入口）。

    fake=True 时不联网，用于演示和测试。
    """
    from assistant.client import DeepSeekClient, FakeClient

    client: BaseLLMClient = FakeClient() if fake else DeepSeekClient(settings)
    return AssistantService(client, system_prompt=settings.system_prompt)
