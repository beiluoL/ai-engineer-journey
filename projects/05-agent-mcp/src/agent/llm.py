"""Project 05 —— LLM 抽象层。

这一层只做一件事：**把"和某个具体厂商对话"这件事抽象掉**。

为什么要抽象？因为 Agent 循环里最需要确定性的部分是"少调用几次模型"，
而不是"调用得有多酷"。如果代码里直接 ``requests.post(openai...)``，
那么离线测试就只能靠 mock 网络，mock 出来的路径和真实路径往往不是同一条。

所以这里定一个极小的接口：:

    class LLM(ABC):
        def chat(self, messages, tools=None) -> LLMMessage

然后给两个实现：``FakeLLM``（纯离线、脚本驱动、测试用它）
和 ``DeepSeekLLM``（真实 HTTP）。Agent 只认接口，换实现不动一行。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Sequence

from .errors import LLMError, LLMResponseError
from .settings import AgentSettings
from .tools import ToolCall

__all__ = [
    "LLMMessage",
    "LLM",
    "FakeLLM",
    "ScriptedLLM",
    "RecordingLLM",
    "DeepSeekLLM",
]

ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"


@dataclass
class LLMMessage:
    """一条对话消息。

    content 允许为 ``None`` —— 模型要调用工具时，content 就是 null，
    ``tool_calls`` 才是这一轮真正的内容。这是新手最容易搞混的地方：
    **没有内容和调用工具是两种状态，不是同一状态的两种写法**。
    """

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转成厂商协议要求的字典。"""
        payload: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            payload["content"] = self.content
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.name:
            payload["name"] = self.name
        if self.tool_calls:
            # 注意 tool_calls 必须是 dict 列表，不是对象列表
            payload["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": _dump(c.arguments)},
                }
                for c in self.tool_calls
            ]
        return payload


def _dump(arguments: dict[str, Any]) -> str:
    """模型协议要求 arguments 是 JSON 字符串，不是对象。"""
    import json

    return json.dumps(arguments, ensure_ascii=False)


class LLM(ABC):
    """大模型接口。 implementations 见 FakeLLM / DeepSeekLLM。"""

    name: ClassVar[str] = "llm"

    @abstractmethod
    def chat(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMMessage:
        """发一轮对话，返回模型的回复。

        tools 传 None 表示这一轮不声明工具（通常是收尾那一轮）。
        """


def _load_tool_calls(raw: Any) -> list[ToolCall] | None:
    """把厂商返回的 tool_calls 归一化成 ToolCall 列表。

    返回 ``None`` 表示"这一轮没有调用工具"，返回空列表表示"有调用但解析出
    零个" —— 这两种必须区分，否则一次解析失败会被误判成"模型决定回答"。
    """
    if not raw:
        return None
    calls: list[ToolCall] = []
    for item in raw:
        if not item.get("id"):
            # 没有 id，工具结果就无法与调用对应 —— 这属于协议错误，
            # 必须在解析阶段就拦住，不能等到 Agent 循环里才炸。
            raise LLMResponseError("tool_call 缺少 id，无法把执行结果对应回去")
        fn = item.get("function") or {}
        name = fn.get("name") or item.get("name")
        if not name:
            raise LLMResponseError("tool_call 缺少 function.name")
        arguments = fn.get("arguments") or item.get("arguments") or {}
        if isinstance(arguments, str):
            import json

            try:
                arguments = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError as exc:
                raise LLMResponseError(f"工具参数不是合法 JSON：{arguments!r}") from exc
        if not isinstance(arguments, dict):
            raise LLMResponseError(f"工具参数必须是对象，收到 {type(arguments).__name__}")
        calls.append(ToolCall(id=item.get("id") or "", name=name or "", arguments=arguments))
    return calls


class FakeLLM(LLM):
    """离线 LLM。

    两种驱动方式：

    - ``responder``：一个函数，接收 (messages, tools)，返回回复。
      适合"按规则生成"的场景，比如"总是先检索再回答"。
    - ``script``：一串预设回复，按顺序取用。适合写死剧本的集成测试。

    两种方式都会把每次输入记进 ``self.calls``，这是断言"工具结果确实回灌了"
    的唯一依据 —— **接口通不等于链路对**，不记录就无法证明。
    """

    name: ClassVar[str] = "fake"

    def __init__(
        self,
        responder: Callable[[Sequence[LLMMessage], Sequence[dict[str, Any]] | None], LLMMessage]
        | None = None,
        *,
        script: Sequence[LLMMessage] | None = None,
        strict: bool = True,
    ) -> None:
        self._responder = responder
        self._queue: deque[LLMMessage] = deque(script or [])
        self.strict = strict
        self.calls: list[list[LLMMessage]] = []
        self.tool_lists: list[list[dict[str, Any]] | None] = []

    def chat(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMMessage:
        self.calls.append(list(messages))
        self.tool_lists.append(tools)

        if self._responder is not None:
            reply = self._responder(messages, tools)
        else:
            if not self._queue:
                raise LLMError("FakeLLM 脚本已耗尽：模型这一轮没有给出回复")
            reply = self._queue.popleft()

        if self.strict and tools and reply.tool_calls is None and reply.content is None:
            raise LLMError(
                "FakeLLM 配置错误：声明了工具却返回了一条既没有 content 也没有 tool_calls 的消息"
            )
        return reply

    @property
    def call_count(self) -> int:
        return len(self.calls)


class ScriptedLLM(FakeLLM):
    """按顺序吐出预设回复的 LLM。剧本用完就抛错而不是静默返回空。"""

    def __init__(self, *messages: LLMMessage) -> None:
        super().__init__(script=list(messages))


class RecordingLLM(LLM):
    """装饰器：包住任何一个 LLM，把往返记下来。

    真实跑通之后要打印一整条 ReAct 轨迹，靠的就是它。
    """

    name: ClassVar[str] = "recording"

    def __init__(self, inner: LLM) -> None:
        self._inner = inner
        self.transcript: list[tuple[list[LLMMessage], list[dict] | None, LLMMessage]] = []

    def chat(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMMessage:
        reply = self._inner.chat(messages, tools, **kwargs)
        self.transcript.append((list(messages), tools, reply))
        return reply

    @property
    def inner(self) -> LLM:
        return self._inner


class DeepSeekLLM(LLM):
    """真实调用 DeepSeek Chat Completions。

    两个必须注意的点：

    1. **没有 API Key 要早失败**。构造时检查，别等到 Agent 循环里第 5 步
       才炸 —— 那时候前面几步的钱已经花出去了。
    2. ``tool`` 角色的消息在协议里**必须有 tool_call_id**，缺一个服务端就
       400。这类错误在离线 mock 里永远复现不出来，只能靠真实调用暴露。
    """

    name: ClassVar[str] = "deepseek"

    def __init__(self, settings: AgentSettings | None = None, http_client: Any = None) -> None:
        self.settings = settings or AgentSettings()
        key = os.getenv(self.settings.api_key_env, "").strip()
        if not key:
            raise LLMError(f"环境变量 {self.settings.api_key_env} 为空，无法调用真实模型")
        self._key = key
        self._client = http_client
        self._owns_client = http_client is None

    @property
    def headers(self) -> dict[str, str]:
        """鉴权头。**最最容易漏的一行**：少了它服务端只会回 401，
        而且离线 mock 永远复现不出来 —— 单测里必须断言它存在。"""
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        import httpx  # 延迟导入，离线测试不强制依赖

        if self._client is not None:
            resp = self._client.post("/chat/completions", json=payload, headers=self.headers)
        else:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    self.settings.base_url.rstrip("/") + "/chat/completions",
                    json=payload,
                    headers=self.headers,
                )
        if resp.status_code != 200:
            raise LLMError(f"模型返回 HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        try:
            choice = data["choices"][0]
            return choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(f"响应结构异常：{str(data)[:400]}") from exc

    def chat(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMMessage:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.settings.temperature),
            "top_p": kwargs.get("top_p", self.settings.top_p),
            "max_tokens": kwargs.get("max_tokens", self.settings.max_tokens),
            "stream": False,
        }
        if tools:
            # 原样透传：每条声明必须自带 "type": "function"。
            # 曾经想当然地"拆掉外层"再发，服务端直接 422 missing field `type`。
            payload["tools"] = [dict(t) for t in tools]
            payload["tool_choice"] = "auto"

        raw = self._post(payload)

        content = raw.get("content")
        content = content if isinstance(content, str) else None
        tool_calls = _load_tool_calls(raw.get("tool_calls"))
        if content is None and not tool_calls:
            raise LLMResponseError(f"模型返回既无内容也无工具调用：{str(raw)[:300]}")
        return LLMMessage(role=ROLE_ASSISTANT, content=content, tool_calls=tool_calls)


_ = ToolCall  # 保持类型可见
