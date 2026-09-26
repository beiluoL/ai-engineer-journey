"""Chapter 00 演示 —— 类 / 继承 / 多态 / @property（真实运行、不联网、不需要 API Key）。

对应 milestones/00-classes-and-oop.md 的 3.1 ~ 3.6 与「坑 4 / 坑 5」：

    @dataclass 模型类        → 自动获得 __repr__ / __init__ / __eq__
    @abstractmethod          → 没实现完的类禁止实例化
    继承 + 多态              → 上层只依赖抽象，换实现不改一行调用代码
    @property 返回副本        → 外部拿到列表也改不动对象内部状态

运行：

    python3 demos/demo-oop.py
"""

from __future__ import annotations

import asyncio
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# 把项目源码目录加进 path，好复用 src/ 里的真实代码（Conversation）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from assistant.conversation import Conversation   # noqa: E402  项目真实代码
from assistant.service import AssistantService    # noqa: E402  项目真实代码


# ============================================================
# 1. @dataclass：数据对象自动获得 __init__ / __repr__ / __eq__
# ============================================================


@dataclass
class Message:
    """一条消息。dataclass 帮我们写了三个方法。"""

    role: str
    content: str

    @property
    def token_estimate(self) -> int:
        """粗略估算 token 数（2 个字符 ≈ 1 token）。"""
        return len(self.content) // 2


# ============================================================
# 2. 抽象基类：定义「必须有什么」，不定义「具体怎么做」
# ============================================================


class BaseLLMClient(ABC):
    """所有模型实现的共同父类。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]]) -> str:
        """子类必须实现。忘了写 → 连实例化都做不到。"""
        raise NotImplementedError


class DeepSeekClient(BaseLLMClient):
    """真实厂商实现（这里用假回答代替网络请求）。"""

    def __init__(self) -> None:
        super().__init__("deepseek")

    async def chat(self, messages: list[dict[str, str]]) -> str:
        last_user = messages[-1]["content"]
        return f"[fake:{self.name}] 你问的是：{last_user}"


class EchoClient(BaseLLMClient):
    """挑战 1 的实现：把最后一条 user 消息原样返回。"""

    def __init__(self) -> None:
        super().__init__("echo")

    async def chat(self, messages: list[dict[str, str]]) -> str:
        return messages[-1]["content"]


class IncompleteClient(BaseLLMClient):
    """坑 5：忘了实现 chat。"""


async def main() -> None:
    # ---- 1. dataclass 自动能力 ----
    print("=" * 60)
    print("1. @dataclass：__repr__ / __eq__ 都是自动生成的")
    print("=" * 60)
    msg = Message(role="user", content="RAG 是怎么工作的？")
    print(f"repr : {msg!r}")
    print(f"字段 : role={msg.role!r} content={msg.content!r} tokens≈{msg.token_estimate}")
    print(f"__eq__: {Message('user', 'RAG 是怎么工作的？') == msg}   # 字段相同即相等")

    # ---- 2. 抽象基类拦住「没写实现」的类 ----
    print()
    print("=" * 60)
    print("2. @abstractmethod：实现不全 → 实例化时直接报错")
    print("=" * 60)
    print(f"BaseLLMClient 是抽象基类: {BaseLLMClient.__abstractmethods__}")
    try:
        IncompleteClient()
    except TypeError as e:
        print(f"TypeError: {e}")

    # ---- 3. 多态：同一个调用，不同实现 ----
    print()
    print("=" * 60)
    print("3. 继承 + 多态：上层只认 BaseLLMClient")
    print("=" * 60)
    messages = [{"role": "system", "content": "你是助手"}, {"role": "user", "content": "讲讲 RAG"}]
    for client in (EchoClient(), DeepSeekClient()):
        answer = await client.chat(messages)
        print(f"{client!r:<34} → chat() → {answer}")

    print()
    print("AssistantService 只依赖抽象（组合而非继承）：")
    service = AssistantService(EchoClient())   # 换实现：这一行之外的代码全都不用改
    print(f"  第 1 轮: {await service.ask('RAG 是什么')}")
    print(f"  第 2 轮: {await service.ask('它和微调有什么区别')}")
    print(f"  历史长度: {len(service.history)} 条（system + 2 问 + 2 答 = 5）")

    # ---- 4. @property 返回副本 ----
    print()
    print("=" * 60)
    print("4. @property 返回副本：外部改不动对象内部状态")
    print("=" * 60)
    conv = Conversation(system_prompt="你是助手")
    conv.add_user("你好")
    print(f"内部 _messages 长度: {len(conv._messages)}")
    view = conv.messages          # @property：看起来像属性，其实是方法
    view.append({"role": "assistant", "content": "伪造一条"})
    print(f"外部 append 后 → 拿到的副本={len(view)} 条，内部仍是 {len(conv._messages)} 条")


if __name__ == "__main__":
    asyncio.run(main())
