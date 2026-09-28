"""Project 05 —— 工作记忆与草稿纸（Milestone 05）。

Milestone 04 的循环有个先天缺陷：**它是没有记性的**。
每执行一步就把消息往上堆，跑完 8 步之后上下文可能翻几倍；
而模型在多步骤任务里产生的中间结论，只存在 assistant 的 content 里 ——
一旦为了省 token 把历史裁掉，那些结论就跟着没了。

所以这一章补两块东西：

1. **``trim_history``（工作记忆）**：按 token 预算裁剪**发给模型**的消息。
   铁律是「助手提出调用」和「工具给出结果」必须**同进同出** ——
   只裁掉 tool 消息而留下它的 assistant，服务端会直接 400。

2. **``Scratchpad``（草稿纸）**：一张放在循环**外面**的命名便签，
   模型可以把中间结论显式写进去，**不随历史裁剪消失**。
   这就是 Plan → Act → Observe 里 "Observe" 的落点 ——
   观察到的东西要落到纸面上，而不是留在随时会被裁掉的对话流里。

token 估算是借用 Project 03 那条铁律：**估算用来做决策，不用来做计费**。
真要算钱请用响应里的 usage。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "estimate_tokens",
    "estimate_messages_tokens",
    "trim_history",
    "TRIMMED_MARK",
    "Scratchpad",
]

ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"

TRIMMED_MARK = "[已省略]"


def estimate_tokens(text: str) -> int:
    """粗估一段文本的 token 数。

    中文是这里的重点：1 个汉字通常接近 1 个 token，
    所以「字符数 // 4」这种纯英文经验公式在中文场景会严重低估。
    """
    if not text:
        return 0
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    other_chars = len(text) - ascii_chars
    return ascii_chars // 4 + other_chars + 1


def estimate_messages_tokens(messages: list[Any]) -> int:
    """估一组消息的 token 数。

    ``messages`` 可以是 ``LLMMessage`` 对象，也可以是 dict
    （to_dict() 之后的形态各处都在用，两种都支持比较好用）。
    """
    total = 0
    for m in messages:
        text = _content_of(m)
        total += estimate_tokens(text) + 4  # +4 是 role 那一行的开销
        extra = getattr(m, "tool_calls", None)
        if extra:
            for call in extra:
                total += estimate_tokens(getattr(call, "name", "")) + estimate_tokens(
                    str(getattr(call, "arguments", {}))
                )
    return total


def _content_of(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _set_content(message: Any, text: str) -> Any:
    """返回一个「内容被改写」的新消息，不原地改。

    LLMMessage 是可变 dataclass，但裁剪发生在**要把消息发出去之前**，
    原地修改会污染 RecordingLLM 里那份 transcript —— 它存的是同一个对象引用，
    结果就是「日志里看到的历史」和「实际发出去的历史」对不上，
    排查问题时看到的不是真相。返回新对象，代价只是多几个对象。
    """
    if isinstance(message, dict):
        new = dict(message)
        new["content"] = text
        return new
    from dataclasses import replace

    return replace(message, content=text)


def trim_history(
    messages: list[Any],
    *,
    budget: int,
    keep_recent: int = 2,
) -> list[Any]:
    """把消息压进 token 预算内。

    规则（顺序即优先级）：
        1. ``system`` 永不裁剪 —— 工作规则丢了 Agent 就变裸模型
        2. 第一条 ``user`` 问题永不裁剪 —— 模型不知道自己在回答什么
        3. 最近 ``keep_recent`` 轮的 assistant+tool 原文保留
        4. 更早的 tool 结果替换成一行占位（写明省略了多少字符，模型知道有过但它读不到）
        5. **assistant(tool_calls) 与它的 tool 消息同进同出**

    第 5 条是关键也是最容易写错的：把中间某轮 assistant 裁了、却留下它的 tool 消息，
    服务端会报「tool message 找不到对应的 tool_call」。这和 M03 讲的顺序坑是同一个根因 ——
    **协议要求的是配对，不是先后**。
    """
    if budget <= 0:
        return list(messages)
    if estimate_messages_tokens(messages) <= budget:
        return list(messages)

    # 先给每条消息标好它在轮次结构里的身份
    protected_head: list[Any] = []
    rounds: list[list[Any]] = []  # 除首尾之外的中间轮：[(assistant, [tool...]), ...]

    seen_first_user = False
    current: list[Any] = []
    for m in messages:
        role = _role_of(m)
        if role == ROLE_SYSTEM:
            protected_head.append(m)
            continue
        if not seen_first_user and role == ROLE_USER:
            protected_head.append(m)
            seen_first_user = True
            continue
        if role == ROLE_ASSISTANT:
            if current:
                rounds.append(current)
            current = [m]
            continue
        if role == ROLE_TOOL:
            current.append(m)
            continue
        current.append(m)
    if current:
        rounds.append(current)

    # 最近的 keep_recent 轮原文保护，更早的可以压
    keep_index = max(0, len(rounds) - keep_recent) if keep_recent >= 0 else len(rounds)
    result: list[Any] = list(protected_head)
    for i, group in enumerate(rounds):
        if i >= keep_index:
            result.extend(group)
            continue
        result.extend([_compress(m) for m in group])

    # 一轮下来如果还超预算，就从最老的中间轮开始整轮丢弃
    while estimate_messages_tokens(result) > budget and len(result) > len(protected_head) + 1:
        for idx in range(len(protected_head), len(result)):
            if _role_of(result[idx]) == ROLE_ASSISTANT:
                # 连同它后面挂着的 tool 消息一起丢
                end = idx + 1
                while end < len(result) and _role_of(result[end]) == ROLE_TOOL:
                    end += 1
                del result[idx:end]
                break
        else:
            break
    return result


def _role_of(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role", ""))
    return str(getattr(message, "role", ""))


def _compress(message: Any) -> Any:
    """把一条 tool 结果压成占位行；assistant 的 thought 文本也按同一规则压。"""
    role = _role_of(message)
    text = _content_of(message)
    if not text:
        return message
    if role == ROLE_TOOL:
        name = message.get("name", "") if isinstance(message, dict) else (getattr(message, "name", "") or "")
        prefix = f"{name}：" if name else ""
        return _set_content(message, f"{TRIMMED_MARK} {prefix}此处曾有 {len(text)} 字符的工具结果，已省略。")
    return _set_content(message, f"{TRIMMED_MARK} {len(text)} 字符")


class Scratchpad:
    """循环之外的草稿纸（计划与观察结果的落点）。

    和对话历史的区别：**它不按 token 计费，也不参与裁剪**。
    模型把「查到的 A」「查到的 B」写进来，最后一步 read 出来做汇总，
    这样即使中间 8 轮历史被裁得只剩占位，关键事实也还在。

    这也是为什么它要被做成**工具而不是 prompt 的一个字段**：
    由模型自己决定记什么、什么时候读，控制权还在模型手上。
    """

    def __init__(self) -> None:
        self._notes: dict[str, str] = {}

    # -------------------------------------------------------------- 写与读
    def write(self, key: str, value: str) -> str:
        key = key.strip()
        if not key:
            from .errors import ToolError

            raise ToolError("note 的 key 不能为空")
        existed = key in self._notes
        self._notes[key] = value
        action = "已更新" if existed else "已记下"
        return f"{action}笔记「{key}」（{len(value)} 字符）。当前共 {len(self._notes)} 条：{', '.join(sorted(self._notes))}"

    def read(self, key: str = "") -> str:
        if not self._notes:
            return "草稿纸是空的，还没有任何笔记。"
        if key:
            if key not in self._notes:
                return f"没有名为「{key}」的笔记。已有：{', '.join(sorted(self._notes))}"
            return f"「{key}」：{self._notes[key]}"
        return "\n".join(f"- {k}：{v}" for k, v in self._notes.items())

    def clear(self) -> None:
        self._notes.clear()

    # -------------------------------------------------------------- 快照
    def render(self) -> str:
        """渲染成可以塞进 system 提示的一段文本。

        让它常驻在提示里，模型就不必每次都调用 read_notes ——
        省一轮工具往返，这在多步骤任务里就是实打实的省钱。
        """
        if not self._notes:
            return ""
        head = "你之前的笔记（来自草稿纸工具，跨步骤保留）："
        body = "\n".join(f"[{k}] {v}" for k, v in self._notes.items())
        return f"{head}\n{body}"

    def to_dict(self) -> dict[str, str]:
        return dict(self._notes)

    def __len__(self) -> int:
        return len(self._notes)

    def __contains__(self, key: object) -> bool:
        return key in self._notes
