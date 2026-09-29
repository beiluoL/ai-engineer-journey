"""Open Source LLM 最小客户端：零第三方依赖，只用标准库。

设计取舍
--------
- **手写而非用 openai SDK**：为了教学可见性。SDK 会把「请求体长什么样、usage
  怎么算、SSE 分包格式」全部藏起来；手写能看清第一层原理，之后再换 SDK 就是一层皮。
- **零依赖**：这条管线刻意保持轻量，不污染 P07 已装好的 torch 环境。

端点说明
--------
- API_BASE 默认 ``https://api.deepseek.com/v1`` ，是官方 REST 路径。
- 若切换到自建网关/企业代理，设置环境变量 ``OPENAI_BASE_URL`` 即可覆盖。

关于「真实证据」的边界
----------------------
本模块里**唯一来自网络的**是模型输出文本与 usage 计数；
而本文档dogma要求的「看得懂、算得出」部分（延迟、吞吐、token 换算）全部在本地由
``time.perf_counter`` 与算术得出，不依赖 LLM 复述。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator, Sequence

API_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
CHAT_PATH = "/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


class LLMError(RuntimeError):
    """调用失败。保留 HTTP 状态码，便于区分「鉴权错 / 限流 / 参数错」三类问题。"""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Usage:
    """token 计数。有一个可用于自检的守恒性质：total == prompt + completion。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def is_conserved(self) -> bool:
        return self.total_tokens == self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class ChatResult:
    """非流式调用的结果快照。"""

    model: str
    content: str
    finish_reason: str
    usage: Usage
    latency_s: float

    @property
    def completion_tps(self) -> float:
        """整体吞吐（tokens/s），含首包延迟；用于与非流式指标对齐比较。"""
        return self.usage.completion_tokens / self.latency_s if self.latency_s > 0 else 0.0


@dataclass
class StreamResult:
    """流式调用的累积快照。"""

    model: str
    content: str
    usage: Usage
    chunks: int
    ttft_s: float
    total_s: float

    @property
    def generation_tps(self) -> float:
        """去掉首包后的净生成吞吐——这才是体感速度，比整体吞吐更有意义。"""
        gen = max(self.total_s - self.ttft_s, 1e-9)
        return self.usage.completion_tokens / gen


def load_api_key() -> str:
    """从环境变量读取 DEEPSEEK_API_KEY。

    坑：非交互 shell 不会自动继承 ``~/.zshrc`` 的导出变量，
    所以本机脚本必须显式 ``source ~/.zshrc`` 后再跑，否则这里会抛错。
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "未找到 DEEPSEEK_API_KEY。请执行：source ~/.zshrc && python demos/<demo>.py",
            status=None,
        )
    return key


def redacted(key: str) -> str:
    """只暴露前 3 位与长度，避免日志/截图泄露完整 key。"""
    return f"{key[:3]}***(len={len(key)})"


def estimate_tokens(text: str) -> int:
    """粗估 token 数（教学用，非精确 BPE）。

    口径与本项目 P06 自写分词器的认知一致：
    中文约 1 字 1 token；英文/数字按约 4 字符 1 token。
    """
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    rest = len(text) - cjk
    return cjk + (rest + 3) // 4


def _post(payload: dict[str, Any], api_key: str, timeout: float):
    """发起 POST。错误时把响应体带上，便于定位是 401 还是 400。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_BASE + CHAT_PATH,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:  # 401 / 400 / 429 都会走这里
        body = e.read().decode("utf-8", "replace")[:400]
        raise LLMError(f"HTTP {e.code}：{body}", status=e.code) from e


def call_chat(
    messages: Sequence[dict[str, str]],
    model: str = DEFAULT_MODEL,
    *,
    temperature: float = 0.7,
    top_p: float = 1.0,
    max_tokens: int = 512,
    timeout: float = 60.0,
) -> ChatResult:
    """单次调用 ``/chat/completions``（非流式）。"""
    api_key = load_api_key()
    payload = {
        "model": model,
        "messages": list(messages),
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
    }
    started = time.perf_counter()
    resp = _post(payload, api_key, timeout)
    raw = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - started

    choice = (raw.get("choices") or [{}])[0]
    usage_raw = raw.get("usage") or {}
    usage = Usage(
        prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
        completion_tokens=int(usage_raw.get("completion_tokens", 0)),
        total_tokens=int(usage_raw.get("total_tokens", 0)),
    )
    return ChatResult(
        model=raw.get("model", model),
        content=(choice.get("message") or {}).get("content", "") or "",
        finish_reason=choice.get("finish_reason", ""),
        usage=usage,
        latency_s=elapsed,
    )


def call_chat_stream(
    messages: Sequence[dict[str, str]],
    model: str = DEFAULT_MODEL,
    *,
    temperature: float = 0.7,
    top_p: float = 1.0,
    max_tokens: int = 512,
    timeout: float = 90.0,
) -> Iterator[tuple[str, StreamResult]]:
    """流式调用。产出 ``(delta, 快照)``，最后一个快照带 usage。

    三个 streams 实现要点（也是教学要点）：
    - SSE 以 ``data: {...}`` 行承载增量，``data: [DONE]`` 收尾；
    - 想在流式下拿到 usage，必须显式请求 ``stream_options.include_usage``；
    - usage 只出现在收尾 chunk，且那个 chunk 的 ``choices`` 通常是空数组——必须容错，
      否则会典型的 ``IndexError``。
    """
    api_key = load_api_key()
    payload = {
        "model": model,
        "messages": list(messages),
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    started = time.perf_counter()
    ttft: float | None = None
    chunks = 0
    buf: list[str] = []
    usage = Usage()
    model_name = model

    resp = _post(payload, api_key, timeout)
    try:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break
            obj = json.loads(data)
            model_name = obj.get("model", model_name)
            if obj.get("usage"):
                u = obj["usage"]
                usage = Usage(
                    prompt_tokens=int(u.get("prompt_tokens", 0)),
                    completion_tokens=int(u.get("completion_tokens", 0)),
                    total_tokens=int(u.get("total_tokens", 0)),
                )
            for choice in obj.get("choices") or []:
                delta = (choice.get("delta") or {}).get("content")
                if delta:
                    if ttft is None:
                        ttft = time.perf_counter() - started
                    chunks += 1
                    buf.append(delta)
                    yield delta, StreamResult(
                        model=model_name,
                        content="".join(buf),
                        usage=usage,
                        chunks=chunks,
                        ttft_s=ttft,
                        total_s=time.perf_counter() - started,
                    )
        yield "", StreamResult(
            model=model_name,
            content="".join(buf),
            usage=usage,
            chunks=chunks,
            ttft_s=ttft or 0.0,
            total_s=time.perf_counter() - started,
        )
    finally:
        resp.close()


__all__ = [
    "API_BASE",
    "DEFAULT_MODEL",
    "LLMError",
    "Usage",
    "ChatResult",
    "StreamResult",
    "call_chat",
    "call_chat_stream",
    "estimate_tokens",
    "load_api_key",
    "redacted",
]
