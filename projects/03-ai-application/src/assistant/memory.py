"""会话记忆（对应 milestones/02、05）。

两件事：

1. 正确构造 messages：四种 role，system 只放一份
2. 控制历史长度：按 token 预算裁剪，超硬阈值时留给上层做摘要

铁律（Chapter 05）：
    - system 永远保留
    - 最后一轮用户输入永远保留
    - 按「轮」剪切，不要切在工具调用中间
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from assistant.tokens import estimate_messages_tokens, estimate_tokens

logger = logging.getLogger(__name__)

Message = dict  # {"role": "system"|"user"|"assistant"|"tool", "content": str, ...}

VALID_ROLES = {"system", "user", "assistant", "tool"}


def validate_messages(messages: list[Message]) -> None:
    """发送前的自检——让「模型为什么答非所问」在请求前就暴露。"""
    if not messages:
        raise ValueError("messages 不能为空")
    for i, m in enumerate(messages):
        role = m.get("role")
        if role not in VALID_ROLES:
            raise ValueError(f"第 {i} 条消息 role 非法: {role!r}")
        if role == "tool" and "tool_call_id" not in m:
            raise ValueError(f"第 {i} 条 tool 消息缺少 tool_call_id")
        if "content" not in m and "tool_calls" not in m:
            raise ValueError(f"第 {i} 条消息既没有 content 也没有 tool_calls")


@dataclass
class Conversation:
    """一段对话的历史。system 单独存，turns 只放对话内容。"""

    system_prompt: str = ""
    turns: list[Message] = field(default_factory=list)

    # ---- 写入 ----

    def add_user(self, content: str) -> None:
        self.turns.append({"role": "user", "content": content})

    def add_assistant(self, content: str, tool_calls: list[dict] | None = None) -> None:
        msg: Message = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.turns.append(msg)

    def add_tool(self, tool_call_id: str, content: str) -> None:
        self.turns.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

    def clear(self) -> None:
        self.turns.clear()

    # ---- 读取（一律返回副本） ----

    def to_messages(self) -> list[Message]:
        head = [{"role": "system", "content": self.system_prompt}] if self.system_prompt else []
        return head + [dict(m) for m in self.turns]

    def to_messages_with(self, text: str) -> list[Message]:
        """在不污染历史的前提下，追加一条用户输入后返回完整消息。"""
        return self.to_messages() + [{"role": "user", "content": text}]

    @property
    def history(self) -> list[Message]:
        return [dict(m) for m in self.turns]

    # ---- 预算控制 ----

    def tokens(self) -> int:
        return estimate_messages_tokens(self.to_messages())

    def trim_to_budget(self, budget_tokens: int) -> int:
        """从最近的往前保留，最多留到 budget_tokens。返回丢弃的条数。

        保留规则：跳过 system（单独存，不参与裁剪），
        且最后一轮用户输入一定保留。
        """
        if not self.turns or budget_tokens <= 0:
            return 0

        kept: list[Message] = []
        used = estimate_tokens(self.system_prompt) if self.system_prompt else 0
        for msg in reversed(self.turns):
            cost = estimate_messages_tokens([msg])
            if used + cost > budget_tokens and kept:
                break
            kept.append(msg)
            used += cost

        # 保证最后一轮 user 输入还在（如果它恰好被裁掉，就补回来）
        kept = list(reversed(kept))
        last = self.turns[-1]
        if last not in kept:
            kept = [last] + kept

        dropped = len(self.turns) - len(kept)
        if dropped > 0:
            logger.warning(
                "历史超预算，裁剪掉 %d 条（预算 %d token）", dropped, budget_tokens
            )
            self.turns = kept
        return dropped


class SessionStore:
    """按 session_id 隔离会话（Chapter 05 坑 3：共享会话 = 数据泄漏）。"""

    def __init__(self, system_prompt: str = "") -> None:
        self._system_prompt = system_prompt
        self._sessions: dict[str, Conversation] = {}

    def get(self, session_id: str) -> Conversation:
        if session_id not in self._sessions:
            self._sessions[session_id] = Conversation(system_prompt=self._system_prompt)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def ids(self) -> list[str]:
        return list(self._sessions)
