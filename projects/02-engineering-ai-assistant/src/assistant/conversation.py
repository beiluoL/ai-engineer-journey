"""对话历史（对应 milestones/00-classes-and-oop.md 3.5 封装）。

为什么要有这个类：

- 对话历史是「状态」，状态应该和「操作它的方法」放在一起
- 用 @property 返回副本，防止外部绕过方法直接改内部列表
- 上层（service / CLI / API）不需要知道历史是怎么存的
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Conversation:
    """一段对话的消息列表。"""

    system_prompt: str = "你是一个简洁、耐心的中文 AI 助手。"
    _messages: list[dict[str, str]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not self._messages:
            self._messages = [{"role": "system", "content": self.system_prompt}]

    # ---- 写入 ----

    def add_user(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self._messages.append({"role": "assistant", "content": text})

    def clear(self) -> None:
        """清空历史，保留 system prompt。"""
        self._messages = [{"role": "system", "content": self.system_prompt}]

    # ---- 读取 ----

    @property
    def messages(self) -> list[dict[str, str]]:
        """只读视图：返回副本，外部改不了内部状态。"""
        return self._messages.copy()

    def __len__(self) -> int:
        """不含 system 的对话轮数 × 2。"""
        return len(self._messages) - 1

    def token_estimate(self) -> int:
        """粗略估算 token 数（中文约 1 字 0.6 token，这里用 2 字符 ≈ 1 token 的保守算法）。"""
        return sum(len(m["content"]) for m in self._messages) // 2

    def trim(self, max_tokens: int = 2000) -> int:
        """超出预算时丢弃最早的 user/assistant 对，保留 system。返回丢弃条数。"""
        dropped = 0
        while self.token_estimate() > max_tokens and len(self._messages) > 2:
            self._messages.pop(1)   # index 0 是 system，从 1 开始丢
            dropped += 1
        return dropped
