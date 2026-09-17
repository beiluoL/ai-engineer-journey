"""LLMClient：封装对 DeepSeek API 的调用（v0.1 单轮问答）。

教学说明（对应 01-python-foundation/11-class.md、14-json.md）：
- v0.1 刻意使用标准库 urllib，不引入任何第三方依赖，
  让你先看清一次 HTTP + JSON 调用的完整链路；
- Phase 1 会引入 requests/httpx，并回答"框架替我们解决了什么"。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from assistant.config import Config
from assistant.errors import LLMAuthError, LLMRateLimitError, LLMResponseError

DEFAULT_SYSTEM_PROMPT = "你是一个简洁、耐心的中文 AI 助手。"


class LLMClient:
    """对 DeepSeek Chat API 的最小封装。"""

    def __init__(self, config: Config, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> None:
        if not config.api_key:
            raise LLMResponseError("api_key 不能为空")
        self.config = config
        self.system_prompt = system_prompt

    # ---- 请求构造（纯函数，方便单测） ----

    def build_messages(self, question: str) -> list[dict[str, str]]:
        """把用户问题构造成 API 要求的 messages 列表。"""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]

    def build_payload(self, question: str) -> dict:
        """构造完整的 JSON 请求体。"""
        return {
            "model": self.config.model,
            "messages": self.build_messages(question),
            "stream": False,
        }

    # ---- 响应解析（纯函数，方便单测） ----

    @staticmethod
    def parse_answer(response_json: dict) -> str:
        """从 API 响应 JSON 中提取回答文本。"""
        try:
            answer: str = response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMResponseError(f"响应格式不符合预期: {e}\n原始响应: {response_json}") from e
        return answer

    # ---- 网络调用 ----

    def _raise_for_status(self, status: int, body: str) -> None:
        """把 HTTP 错误状态映射成具体异常（对应 12-exception 的错误层级）。"""
        if status in (401, 403):
            raise LLMAuthError(f"认证失败（HTTP {status}）：请检查 DEEPSEEK_API_KEY 是否有效。{body[:200]}")
        if status == 429:
            raise LLMRateLimitError(f"触发限流（HTTP 429）：请稍后重试。{body[:200]}")
        raise LLMResponseError(f"API 返回异常状态（HTTP {status}）：{body[:200]}")

    def ask(self, question: str) -> str:
        """单轮问答：输入问题，返回模型回答文本。"""
        payload = self.build_payload(question)
        request = urllib.request.Request(
            url=f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            self._raise_for_status(e.code, error_body)
        except urllib.error.URLError as e:
            raise LLMResponseError(f"网络错误，无法连接 API：{e.reason}") from e
        except TimeoutError as e:
            raise LLMResponseError(f"请求超时（>{self.config.timeout}s）") from e

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise LLMResponseError(f"响应不是合法 JSON：{e}") from e

        return self.parse_answer(data)
