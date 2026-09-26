"""Chapter 04 演示 —— dataclass：frozen / default_factory / __post_init__ / replace。

对应 milestones/04-dataclass.md 的 3 / 10 / 11 / 12 / 13 / 19 / 20 / 坑 2：

    手写类 vs @dataclass   → 样板代码和自动获得的 __init__/__repr__/__eq__
    frozen=True            → 创建后不可改（配置对象的正确姿态）
    field(default_factory) → 可变默认值不能共享
    __post_init__          → 构造完之后立刻校验
    replace()              → 不改原对象，派生一份新配置
    asdict()               → 内部模型 → 外部 API 的 dict

运行：

    python3 demos/demo-dataclass.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from assistant.settings import Settings   # noqa: E402  项目真实代码：frozen + repr=False


# ============================================================
# 1. 手写类（要自己写三个方法）vs @dataclass（全送）
# ============================================================


class PlainMessage:
    """手写版：__init__ / __repr__ / __eq__ 都得自己写。"""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content

    def __repr__(self) -> str:
        return f"PlainMessage(role={self.role!r}, content={self.content!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlainMessage):
            return NotImplemented
        return (self.role, self.content) == (other.role, other.content)


class RawMessage:
    """对照：一行方法都不写，默认 repr 只有内存地址。"""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


@dataclass
class Message:
    """dataclass 版：上面三个方法一个都没写，但全都有。"""

    role: str
    content: str

    def is_user(self) -> bool:
        """数据 + 与数据直接相关的行为，可以放在这里。"""
        return self.role == "user"


# ============================================================
# 2. 带默认值的配置对象
# ============================================================


@dataclass
class LLMConfig:
    model: str
    api_key: str = field(repr=False)        # repr 里隐藏，防 Key 泄露
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: float = 60.0
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FrozenConfig:
    """frozen：创建后不能改。"""

    model: str
    temperature: float


# ============================================================
# 3. __post_init__ 校验
# ============================================================


@dataclass
class ChatRequest:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"role 非法: {self.role!r}")
        if not self.content.strip():
            raise ValueError("content 不能为空")


@dataclass
class Session:
    """default_factory=list：每个实例有自己一份。"""

    messages: list[ChatRequest] = field(default_factory=list)


class BadSession:
    """反例：类属性被所有实例共享。"""

    messages: list = []


def main() -> None:
    # ---- 1. 手写 vs dataclass ----
    print("=" * 62)
    print("1. 手写类 vs @dataclass")
    print("=" * 62)
    plain = PlainMessage("user", "讲讲 RAG")
    msg = Message("user", "讲讲 RAG")
    print(f"  手写 PlainMessage : {plain!r}")
    print(f"  dataclass Message : {msg!r}")
    print(f"  两者比较 : {plain == PlainMessage('user', '讲讲 RAG')} / {msg == Message('user', '讲讲 RAG')}")
    print(f"  Message 自带方法 : {[m for m in ('__init__', '__repr__', '__eq__') if m in vars(Message)]}")
    print(f"  完全不写方法的类: {RawMessage('user', '讲讲 RAG')!r}")

    # ---- 2. 默认值 + repr=False ----
    print()
    print("=" * 62)
    print("2. 默认值、repr=False（Key 不进日志）")
    print("=" * 62)
    config = LLMConfig(model="deepseek-chat", api_key="sk-test-xxxx")
    print(f"  config          : {config}")
    print(f"  config.api_key  : {config.api_key}   ← 访问得到，只是不出现在 repr 里")

    # ---- 3. frozen ----
    print()
    print("=" * 62)
    print("3. frozen=True：改一个字段试试")
    print("=" * 62)
    frozen = FrozenConfig("deepseek-chat", 0.7)
    print(f"  frozen          : {frozen}")
    try:
        frozen.temperature = 1.0
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")
    newer = replace(frozen, temperature=1.0)
    print(f"  replace(...) 派生: {newer}")
    print(f"  原对象没被改    : {frozen.temperature}")
    print()
    print("  真实项目代码 src/assistant/settings.py: Settings 也是 frozen + repr=False")
    real = Settings(api_key="sk-test-xxxx")
    print(f"  repr 里看不见 api_key: {'api_key' not in repr(real)}（但 {real.model} 照常可读）")

    # ---- 4. default_factory ----
    print()
    print("=" * 62)
    print("4. 可变默认值：default_factory 让每个实例各有一份")
    print("=" * 62)
    a, b = Session(), Session()
    a.messages.append(ChatRequest("user", "第一轮"))
    print(f"  A 加了 1 条 → A={len(a.messages)} 条，B={len(b.messages)} 条")
    print(f"  A.messages is B.messages : {a.messages is b.messages}")

    bad1, bad2 = BadSession(), BadSession()
    bad1.messages.append("污染")
    print(f"  反例（类属性）→ bad1={bad1.messages}，bad2={bad2.messages}")

    # ---- 5. __post_init__ ----
    print()
    print("=" * 62)
    print("5. __post_init__：构造完立刻校验")
    print("=" * 62)
    print(f"  合法: {ChatRequest('user', '  RAG 是什么 ').role!r}")
    for bad in (dict(role="tool", content="ok"), dict(role="user", content="   ")):
        try:
            ChatRequest(**bad)
        except ValueError as e:
            print(f"  非法 {bad} → ValueError: {e}")

    # ---- 6. asdict：内部模型 → 外部 API ----
    print()
    print("=" * 62)
    print("6. asdict(): 内部模型 → 请求体")
    print("=" * 62)
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [asdict(m) for m in a.messages],
    }
    print("  " + json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
