"""业务编排层（对应 milestones/09 —— 五层里的「编排层」）。

这一层只做流程编排，不碰 HTTP、不拼 URL（那是 client 的事），
也不直接写 Prompt 字符串（那是 prompts 的事）。

四条路径：
    ask()            普通问答
    astream()        流式
    ask_structured() 结构化输出（Chapter 03）
    run_agent()      工具循环（Chapter 08）
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import BaseModel

from assistant.agent import run_agent
from assistant.client import BaseLLMClient
from assistant.errors import ContextWindowError
from assistant.memory import Conversation, SessionStore, validate_messages
from assistant.schema import structured
from assistant.settings import Settings
from assistant.tokens import Budget, cost_cny, estimate_messages_tokens

logger = logging.getLogger(__name__)


@dataclass
class Usage:
    """一次会话的累计消耗（Chapter 07）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def cost(self, model: str) -> float:
        return cost_cny(model, self.prompt_tokens, self.completion_tokens)

    def as_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "calls": self.calls,
        }


@dataclass
class ChatService:
    """串起 prompt / memory / schema / tools 的编排层。"""

    client: BaseLLMClient
    settings: Settings
    system_prompt: str = ""
    budget: Budget = field(default_factory=Budget)
    usage: Usage = field(default_factory=Usage)
    sessions: SessionStore = field(default_factory=SessionStore)

    def __post_init__(self) -> None:
        self.sessions._system_prompt = self.system_prompt or self.settings.system_prompt

    # ---- 内部：取会话 + 预算控制 ----

    def _conversation(self, session_id: str) -> Conversation:
        return self.sessions.get(session_id)

    def _prepare(self, conv: Conversation) -> None:
        """发送前：先按预算裁剪，超窗口就明确报错（不静默失败）。"""
        tokens = estimate_messages_tokens(conv.to_messages())
        verdict = self.budget.check(tokens)
        if verdict == "trim":
            conv.trim_to_budget(self.budget.history_budget)
        elif verdict == "overflow":
            conv.trim_to_budget(self.budget.history_budget)
            still = estimate_messages_tokens(conv.to_messages())
            if self.budget.check(still) == "overflow":
                raise ContextWindowError(
                    f"上下文超出窗口（{still} > {self.budget.context_window - self.budget.reserved_output}），"
                    "请开一个新会话。"
                )

    def _record_usage(self) -> None:
        """把 client 记录的 usage 累加进来（真实 client 才有）。"""
        last = getattr(self.client, "last_usage", None)
        if last:
            self.usage.prompt_tokens += last.get("prompt_tokens", 0)
            self.usage.completion_tokens += last.get("completion_tokens", 0)
        self.usage.calls += 1

    # ---- 四条路径 ----

    async def ask(self, text: str, session_id: str = "default") -> str:
        conv = self._conversation(session_id)
        self._prepare(conv)
        messages = conv.to_messages_with(text)
        validate_messages(messages)

        reply = await self.client.chat(messages)
        self._record_usage()

        conv.add_user(text)
        conv.add_assistant(reply)
        return reply

    async def astream(self, text: str, session_id: str = "default") -> AsyncIterator[str]:
        conv = self._conversation(session_id)
        self._prepare(conv)
        messages = conv.to_messages_with(text)
        validate_messages(messages)

        buf: list[str] = []
        async for delta in self.client.stream(messages):
            buf.append(delta)
            yield delta

        self._record_usage()
        full = "".join(buf)
        conv.add_user(text)
        conv.add_assistant(full)          # 漏了这句：下一轮就会「失忆」

    async def ask_structured(
        self,
        text: str,
        model_cls: type[BaseModel],
        session_id: str = "default",
        max_retry: int = 1,
    ) -> BaseModel:
        conv = self._conversation(session_id)
        self._prepare(conv)
        messages = conv.to_messages_with(text)
        validate_messages(messages)

        result = await structured(self.client, messages, model_cls, max_retry=max_retry)
        self._record_usage()

        conv.add_user(text)
        conv.add_assistant(result.model_dump_json(ensure_ascii=False))
        return result

    async def run_agent(self, text: str, session_id: str = "default") -> str:
        conv = self._conversation(session_id)
        self._prepare(conv)
        messages = conv.to_messages_with(text)
        validate_messages(messages)

        answer, trace = await run_agent(self.client, messages)
        self._record_usage()

        conv.add_user(text)
        for msg in trace[len(messages):]:
            conv.turns.append(msg)
        return answer

    # ---- 辅助 ----

    def reset(self, session_id: str = "default") -> None:
        self.sessions.reset(session_id)

    def cost_so_far(self) -> float:
        return self.usage.cost(self.settings.model)


def build_service(
    settings: Settings,
    client: BaseLLMClient | None = None,
) -> ChatService:
    """组装一个 service。client 可注入（测试用 FakeClient）。"""
    if client is None:
        from assistant.client import DeepSeekClient

        client = DeepSeekClient(settings)
    return ChatService(
        client=client,
        settings=settings,
        system_prompt=settings.system_prompt,
        budget=Budget(context_window=settings.context_window),
    )
