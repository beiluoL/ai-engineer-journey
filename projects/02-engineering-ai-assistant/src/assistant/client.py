"""LLM 客户端层（对应 milestones/00、01、02）。

分层设计：

    BaseLLMClient (ABC)     —— 抽象：只声明「能 chat / stream」
        ├── DeepSeekClient  —— 真实实现：httpx 异步 + 连接池 + 超时 + 重试
        └── FakeClient      —— 测试替身：不联网、可预设失败次数

上层（service）只依赖 BaseLLMClient，所以：
- 换厂商 = 换一个子类，上层零改动
- 测试   = 注入 FakeClient，不花钱不联网
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from assistant.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMRateLimitError,
    LLMResponseError,
)
from assistant.logging_setup import redact_headers
from assistant.settings import Settings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """所有 LLM 客户端的抽象基类。"""

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]]) -> str:
        """发送完整消息列表，返回助手回复文本。"""
        ...

    @abstractmethod
    async def aclose(self) -> None:
        """释放连接资源。"""
        ...

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """流式返回。默认实现：退化成一次性返回（子类可覆盖）。"""
        yield await self.chat(messages)

    async def __aenter__(self) -> "BaseLLMClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


class DeepSeekClient(BaseLLMClient):
    """DeepSeek Chat API 的异步客户端（httpx）。

    关键点：

    - AsyncClient 复用：连接池 + Keep-Alive，避免每次握手
    - 区分 connect / read / write 超时：LLM 响应慢，read 要给足
    - 429 / 超时才重试，401 绝不重试
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.api_key:
            raise LLMConfigError("api_key 为空，无法创建客户端")
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            timeout=httpx.Timeout(
                connect=5.0,
                read=settings.timeout,
                write=10.0,
                pool=5.0,
            ),
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
        )

    # ---- 请求构造（纯逻辑，可单测） ----

    def build_payload(self, messages: list[dict[str, str]], stream: bool = False) -> dict:
        return {
            "model": self.settings.model,
            "messages": messages,
            "stream": stream,
        }

    @staticmethod
    def parse_answer(data: dict) -> str:
        try:
            answer: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMResponseError(f"响应格式不符合预期: {e}") from e
        return answer

    # ---- 错误映射 ----

    def _raise_for_status(self, status: int, body: str) -> None:
        detail = body[:200]
        if status in (401, 403):
            raise LLMAuthError(f"认证失败（HTTP {status}）：请检查 API Key 是否有效。{detail}")
        if status == 429:
            raise LLMRateLimitError(f"触发限流（HTTP 429）：请稍后重试。{detail}")
        raise LLMResponseError(f"API 返回异常状态（HTTP {status}）：{detail}")

    # ---- 网络调用（带重试） ----

    async def chat(self, messages: list[dict[str, str]]) -> str:
        payload = self.build_payload(messages)
        last_error: Exception | None = None

        for attempt in range(1, self.settings.max_retries + 2):
            try:
                logger.debug(
                    "请求 LLM: model=%s, messages=%d, attempt=%d",
                    self.settings.model, len(messages), attempt,
                )
                resp = await self._client.post("/chat/completions", json=payload)
                if resp.status_code >= 400:
                    self._raise_for_status(resp.status_code, resp.text)
                data = resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, LLMRateLimitError) as e:
                last_error = e
                if attempt > self.settings.max_retries:
                    break
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "调用失败（%s），%.1fs 后第 %d 次重试",
                    type(e).__name__, wait, attempt,
                )
                import asyncio
                await asyncio.sleep(wait)
                continue
            except json.JSONDecodeError as e:
                raise LLMResponseError(f"响应不是合法 JSON：{e}") from e

            answer = self.parse_answer(data)
            usage = data.get("usage") or {}
            logger.info(
                "LLM 调用完成",
                extra={"extra_fields": {
                    "model": self.settings.model,
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "attempt": attempt,
                }},
            )
            return answer

        raise LLMResponseError(f"LLM 调用失败，已重试 {self.settings.max_retries} 次：{last_error}")

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """SSE 流式：逐个 delta 产出。"""
        payload = self.build_payload(messages, stream=True)
        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                self._raise_for_status(resp.status_code, (await resp.aread()).decode("utf-8", "replace"))
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta

    async def aclose(self) -> None:
        await self._client.aclose()
        logger.debug("httpx client 已关闭")


class FakeClient(BaseLLMClient):
    """测试替身：不联网、不花钱、可预设失败次数（对应 milestones/07）。

    这是 Chapter 07 能「离线测业务逻辑」的关键。
    """

    def __init__(self, reply: str = "这是 FakeClient 的固定回答", fail_times: int = 0) -> None:
        self.reply = reply
        self.fail_times = fail_times
        self.calls: list[list[dict[str, str]]] = []
        self.closed = False

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages.copy())
        if len(self.calls) <= self.fail_times:
            raise LLMRateLimitError("模拟限流")
        return self.reply

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        for ch in self.reply:
            yield ch

    async def aclose(self) -> None:
        self.closed = True
