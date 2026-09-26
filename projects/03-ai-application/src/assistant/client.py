"""LLM 客户端层（对应 milestones/02、03、04、08）。

沿用 Project 02 的分层：

    BaseLLMClient (ABC)     —— 抽象：声明「能 chat / chat_message / stream」
        ├── DeepSeekClient  —— 真实实现：httpx 连接池 + 超时 + 退避重试
        └── FakeClient      —— 测试替身：不联网、可编排回复与工具调用

Project 03 相比 P02 的两个扩展：
    - `chat_message()`：返回**完整 assistant 消息**（含 tool_calls），工具循环需要
    - 请求里带上 temperature / top_p / max_tokens / response_format / tools
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from assistant.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMRateLimitError,
    LLMResponseError,
)
from assistant.logging_setup import redact_headers
from assistant.memory import Message
from assistant.settings import Settings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """所有 LLM 客户端的抽象基类。上层只依赖它。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        """返回助手回复文本。"""
        ...

    @abstractmethod
    async def chat_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> Message:
        """返回完整 assistant 消息（可能有 tool_calls）。工具循环用。"""
        ...

    @abstractmethod
    async def aclose(self) -> None:
        ...

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """流式输出。默认退化成一次性返回。"""
        yield await self.chat(messages)

    async def __aenter__(self) -> "BaseLLMClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


class DeepSeekClient(BaseLLMClient):
    """DeepSeek Chat API 的异步客户端（httpx）。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.api_key:
            raise LLMConfigError("api_key 为空，无法创建客户端")
        self.settings = settings
        self.last_usage: dict[str, int] = {}
        self.last_finish_reason: str = ""
        self._client = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            timeout=httpx.Timeout(
                connect=5.0, read=settings.timeout, write=10.0, pool=5.0
            ),
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
        )

    # ---- 请求构造（纯逻辑，可单测） ----

    def build_payload(
        self,
        messages: list[Message],
        stream: bool = False,
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "stream": stream,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "max_tokens": self.settings.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
        return payload

    # ---- 错误映射 ----

    def _raise_for_status(self, status: int, body: str) -> None:
        detail = body[:200]
        if status in (401, 403):
            raise LLMAuthError(f"认证失败（HTTP {status}）：请检查 API Key。{detail}")
        if status == 429:
            raise LLMRateLimitError(f"触发限流（HTTP 429）。{detail}")
        raise LLMResponseError(f"API 返回异常状态（HTTP {status}）：{detail}")

    # ---- 网络调用 ----

    async def _post(self, payload: dict) -> dict:
        """带退避重试的一次 POST（只对超时/连接错误/429 重试）。"""
        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 2):
            try:
                resp = await self._client.post("/chat/completions", json=payload)
                if resp.status_code >= 400:
                    self._raise_for_status(resp.status_code, resp.text)
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, LLMRateLimitError) as e:
                last_error = e
                if attempt > self.settings.max_retries:
                    break
                wait = 2 ** (attempt - 1)
                logger.warning("调用失败（%s），%.1fs 后第 %d 次重试", type(e).__name__, wait, attempt)
                await asyncio.sleep(wait)
            except json.JSONDecodeError as e:
                raise LLMResponseError(f"响应不是合法 JSON：{e}") from e
        raise LLMResponseError(f"调用失败，已重试 {self.settings.max_retries} 次：{last_error}")

    def _record(self, data: dict) -> dict:
        """记录 usage / finish_reason，返回 message 字典。"""
        usage = data.get("usage") or {}
        self.last_usage = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMResponseError(f"响应格式不符合预期: {e}") from e

        self.last_finish_reason = choice.get("finish_reason", "")
        if self.last_finish_reason == "length":
            logger.warning("输出被 max_tokens 截断，考虑调大 DEEPSEEK_MAX_TOKENS")

        logger.info(
            "LLM 调用完成",
            extra={"extra_fields": {
                "model": self.settings.model,
                "prompt_tokens": self.last_usage["prompt_tokens"],
                "completion_tokens": self.last_usage["completion_tokens"],
                "finish_reason": self.last_finish_reason,
            }},
        )
        return choice.get("message", {})

    async def chat_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> Message:
        payload = self.build_payload(messages, response_format=response_format, tools=tools)
        data = await self._post(payload)
        return self._record(data)

    async def chat(
        self,
        messages: list[Message],
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        msg = await self.chat_message(messages, tools=tools, response_format=response_format)
        return msg.get("content") or ""

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        payload = self.build_payload(messages, stream=True)
        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                self._raise_for_status(
                    resp.status_code, (await resp.aread()).decode("utf-8", "replace")
                )
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta

    async def aclose(self) -> None:
        await self._client.aclose()

    def headers(self) -> dict[str, str]:
        """脱敏后的请求头（用于日志）。"""
        return redact_headers(dict(self._client.headers))


class FakeClient(BaseLLMClient):
    """测试替身：不联网、不花钱，可编排回复与工具调用。

    script 的用法：
        FakeClient(script=[
            {"tool_calls": [{"id": "1", "function": {"name": "add", "arguments": '{"a":1,"b":2}'}}]},
            {"content": "答案是 3"},
        ])
    """

    def __init__(self, script: list[Message] | None = None, reply: str = "固定回答") -> None:
        self.script = list(script or [])
        self.reply = reply
        self.calls: list[dict] = []
        self.closed = False

    def _next(self) -> Message:
        if self.script:
            return self.script.pop(0)
        return {"role": "assistant", "content": self.reply}

    async def chat_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> Message:
        self.calls.append({"messages": messages, "tools": tools, "response_format": response_format})
        return self._next()

    async def chat(
        self,
        messages: list[Message],
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        msg = await self.chat_message(messages, tools=tools, response_format=response_format)
        return msg.get("content") or ""

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        self.calls.append({"messages": messages, "stream": True})
        for ch in self.reply:
            yield ch

    async def aclose(self) -> None:
        self.closed = True
