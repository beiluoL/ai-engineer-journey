"""Exercises 01-oop-dataclass-typehints 参考答案（对应 M00 / M03 / M04 / M05 配置小节）。

用法:
    .venv/bin/python exercises/01-oop-dataclass-typehints/answers.py

规矩:
    先自己把 9 题敲一遍、跑通了再来看这个文件。卡住了只看对应那一个函数，不要整份抄。
    本文件纯离线（不联网、不调真实 LLM、不读真实 API Key）。

判卷标记:
    每题跑完打印 "[PASS] <题号> <这次真的看到的东西>"，判卷脚本靠它计数。
"""

from __future__ import annotations

import dataclasses
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from typing import Optional, Protocol, TypeVar, get_type_hints, runtime_checkable

# 题库里统一用这个打印过关标记，判卷脚本靠 "[PASS]" 这五个字符计数。
def _pass(qid: str, note: str) -> None:
    print(f"[PASS] {qid} {note}")


# ---------- A. 类与 OOP（Milestone 00） ----------

class Turn:
    """A1: 一轮对话。手写类，不用 dataclass。

    为什么手写：要展示「__init__ 决定实例属性」以及「方法/属性挂在类上、数据躺在实例上」。
    """

    ROLES = ("system", "user", "assistant")

    def __init__(self, role: str, content: str) -> None:
        # 校验放在 __init__ 里：对象一旦造出来就一定是合法的（Java 的构造函数同理）
        if role not in self.ROLES:
            raise ValueError(f"role 必须是 {self.ROLES} 之一，收到: {role!r}")
        self.role = role
        self.content = content

    @property
    def is_user(self) -> bool:
        return self.role == "user"

    def token_estimate(self) -> int:
        """中文保守估算：2 字符约 1 token。"""
        return len(self.content) // 2

    def __repr__(self) -> str:
        # 只打印字符数：真实内容可能有几千字，repr 进日志会把一行撑爆
        return f"Turn(role={self.role!r}, chars={len(self.content)})"

    def __eq__(self, other: object) -> bool:
        # 和别的类型比要返回 NotImplemented，Python 才会去试 other.__eq__
        if not isinstance(other, Turn):
            return NotImplemented
        return (self.role, self.content) == (other.role, other.content)

    # 注意: 手写了 __eq__ 就没了默认 __hash__，Turn 天然不可 hash。
    # 想可 hash 就显式加 __hash__ = None 或自己实现。


def a1() -> None:
    """A1: 手写 Turn 类 + 断言。"""
    t = Turn("user", "list 和 dict 有什么区别？")

    # 1) 非法 role 必须在构造时就被拦下
    try:
        Turn("root", "越权")
    except ValueError as e:
        print(f"  非法 role 抛错: {e}")
    else:  # pragma: no cover - 正常不该走到这里
        raise AssertionError("A1: 非法 role 竟然没抛 ValueError")

    # 2) 估算值 = 字符数 // 2（这次真的算出来的）
    print(f"  token_estimate = {t.token_estimate()}（len={len(t.content)}）")
    assert t.token_estimate() == len(t.content) // 2, "A1 token 估算不对"

    # 3) repr 不吐正文
    assert "list" not in repr(t), "A1 repr 把正文打出来了"
    print(f"  repr = {repr(t)}")

    # 4) 与别的类型比较不炸，返回 False
    assert (t == "字符串") is False, "A1 与非 Turn 比较应为 False"
    assert t.is_user is True and Turn("assistant", "x").is_user is False

    # 5) 手写 __eq__ 的代价：不可 hash（这是设计选择，不是 bug）
    try:
        hash(t)
    except TypeError:
        print("  hash(Turn) 抛 TypeError：手写了 __eq__ 就丢了默认 __hash__")
    else:  # pragma: no cover
        raise AssertionError("A1: Turn 应该是不可 hash 的")

    _pass("A1", "非法 role 抛 ValueError、token 估算 = len//2、repr 不含正文、与字符串比较返回 False")


class Conversation:
    """A2: 封装对话历史。内部状态 + 只返回副本的 property。"""

    def __init__(self, system_prompt: str = "你是 Python 助教") -> None:
        self.system_prompt = system_prompt
        self._turns: list[Turn] = []

    def add(self, turn: Turn) -> None:
        self._turns.append(turn)

    @property
    def turns(self) -> list[Turn]:
        """返回副本：外部拿到列表后随便改，都碰不到内部状态。"""
        return self._turns.copy()

    def __len__(self) -> int:
        return len(self._turns)

    def token_estimate(self) -> int:
        return sum(t.token_estimate() for t in self._turns)


def a2() -> None:
    """A2: 封装 + property 给副本 + 与仓库真实 Conversation 对齐数字。"""
    conv = Conversation(system_prompt="你是 Python 助教")
    conv.add(Turn("user", "你好"))
    conv.add(Turn("assistant", "你好，有什么可以帮你？"))

    # 1) property 必须给副本
    outer = conv.turns
    outer.append(Turn("user", "偷渡一条"))
    assert len(conv) == 2, "A2 外部改了副本，内部状态也跟着变了"
    print(f"  改副本后内部条数仍是 {len(conv)}")

    # 2) 与 src/assistant/conversation.py 的真实实现算同一组数字
    from assistant.conversation import Conversation as RealConversation

    real = RealConversation(system_prompt="你是 Python 助教")
    real.add_user("你好")
    real.add_assistant("你好，有什么可以帮你？")
    mine = sum(len(m["content"]) for m in real.messages) // 2
    print(f"  真实 Conversation.token_estimate() = {real.token_estimate()}，手算 = {mine}")
    assert real.token_estimate() == mine, "A2 与真实实现数字不一致"

    _pass("A2", "property 给的是副本（外部改不动内部），且与真实 Conversation 的 token 估算一致")


def a3() -> None:
    """A3: 组合优先于继承 + 绑定方法。"""
    conv = Conversation()
    conv.add(Turn("user", "hi"))

    # 1) 组合：Conversation 不继承 Turn，里面装着 Turn
    assert not issubclass(Conversation, Turn), "A3 Conversation 不该继承 Turn"
    assert all(isinstance(t, Turn) for t in conv._turns)
    print(f"  Conversation 是 Turn 的子类吗: {issubclass(Conversation, Turn)}；内部装的是 {type(conv._turns[0]).__name__}")

    # 2) add 是绑定方法：有 __self__，可以整条传走当函数使
    add = conv.add
    assert getattr(add, "__self__", None) is conv, "A3 add 不是绑定方法"
    add(Turn("assistant", "收到"))
    assert len(conv) == 2
    print(f"  绑定方法 __self__ = {add.__self__.__class__.__name__}，传走后仍能加到同一对象上")

    _pass("A3", "Conversation 组合 Turn 而非继承，且 add 是绑定方法（可直接传走）")


# ---------- B. 类型注解（Milestone 03） ----------


def first_content(messages: Optional[list[dict[str, str]]] = None) -> Optional[str]:
    """B1: Optional 版取值。空 / None 返回 None，而不是空字符串。"""
    if not messages:
        return None
    return messages[0].get("content")


def b1() -> None:
    """B1: Optional 的返回值语义 + 运行时可见的注解。"""
    hints = get_type_hints(first_content)
    print(f"  返回注解 = {hints['return']}，参数注解 = {hints['messages']}")
    # 注意：有 from __future__ import annotations 时，get_type_hints 解析出来的是 typing 对象，
    # 不是源码里的字面量 "Optional[str]"（这也是为什么用 == 而不是比字符串）。
    assert hints["return"] == Optional[str], "B1 返回注解必须是 Optional[str]"
    assert hints["messages"] == Optional[list[dict[str, str]]]

    assert first_content(None) is None
    assert first_content([]) is None
    assert first_content([{"role": "user", "content": "hi"}]) == "hi"
    assert first_content([]) != ""
    print(f"  first_content([]) -> {first_content([])!r}（不是空字符串）")
    print(f"  first_content(None) -> {first_content(None)!r}")

    _pass("B1", "空输入返回 None 而非空串，get_type_hints 读到的返回注解是 Optional[str]")


@runtime_checkable
class Tokens(Protocol):
    """B2: 有界 TypeVar 的下界 —— 只要有 token_estimate() 就算数，不看继承。"""

    def token_estimate(self) -> int: ...


T = TypeVar("T", bound=Tokens)


def total_tokens(items: Sequence[T]) -> int:
    return sum(i.token_estimate() for i in items)


class AnotherTurn:
    """另一个「有 token_estimate 但没有共同基类」的类。"""

    def __init__(self, text: str) -> None:
        self.text = text

    def token_estimate(self) -> int:
        return len(self.text) // 2


def b2() -> None:
    """B2: 有界 TypeVar 泛型求和。"""
    a = total_tokens([Turn("user", "一二三四五"), Turn("assistant", "六七八")])
    b = total_tokens([AnotherTurn("abcdefgh")])
    print(f"  Turn 组 = {a}；AnotherTurn 组 = {b}")
    assert a == 3, "B2 Turn 组求和不对（5//2 + 3//2）"
    assert b == 4, "B2 AnotherTurn 组求和不对"
    assert total_tokens([]) == 0
    print("  同一个 total_tokens 同时吃下两个无共同基类的类型")

    _pass("B2", "同一个 total_tokens 同时吃下 Turn 和 AnotherTurn（无共同基类），求和正确")


@runtime_checkable
class ChatLike(Protocol):
    """B3: 结构化类型 —— 只看有没有 chat()，不看继承谁。"""

    def chat(self, messages: list[dict[str, str]]) -> str: ...


class OnlyClose:
    """只有 aclose()，没有 chat()。"""

    async def aclose(self) -> None: ...


def b3() -> None:
    """B3: Protocol 运行时检查。"""
    from assistant.client import FakeClient

    fake = FakeClient(reply="ok")
    print(f"  isinstance(FakeClient(), ChatLike) = {isinstance(fake, ChatLike)}")
    assert isinstance(fake, ChatLike), "B3: FakeClient 应该有 chat()"

    print(f"  isinstance(OnlyClose(), ChatLike) = {isinstance(OnlyClose(), ChatLike)}")
    assert not isinstance(OnlyClose(), ChatLike), "B3: 只有 aclose 的对象不该通过"

    # 结构化类型真正的作用：函数注解只收「有 chat() 的东西」
    async def call(chat: ChatLike) -> str:
        return await chat.chat([{"role": "user", "content": "hi"}])

    import asyncio

    assert asyncio.run(call(fake)) == "ok"

    _pass("B3", "FakeClient（未继承 ChatLike）通过 isinstance，只有 aclose() 的对象被挡下")


# ---------- C. dataclass 与不可变配置（Milestone 04 + M05 配置小节） ----------


@dataclass(frozen=True)
class ModelConfig:
    """C1: 不可变配置。密钥既不打印也不参与比较。"""

    model: str = "deepseek-chat"
    temperature: float = 0.7
    api_key: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model 不能为空")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature 必须落在 [0.0, 2.0]，当前 {self.temperature}")

    @property
    def label(self) -> str:
        return f"{self.model}@{self.temperature}"


def c1() -> None:
    """C1: frozen 校验、repr 脱敏、compare=False、可 hash。"""
    cfg = ModelConfig(api_key="sk-SECRET-1234")

    # 1) frozen：改不动
    try:
        cfg.temperature = 0.2
    except dataclasses.FrozenInstanceError as e:
        print(f"  改字段抛 FrozenInstanceError: {e}")
    else:  # pragma: no cover
        raise AssertionError("C1: frozen dataclass 竟然能改字段")

    # 2) repr 里不能出现密钥
    assert "sk-SECRET-1234" not in repr(cfg), "C1 repr 泄露了密钥"
    print(f"  repr = {cfg!r}")

    # 3) compare=False：只差密钥的两个实例相等
    twin = ModelConfig(api_key="sk-另一个KEY")
    assert cfg == twin, "C1: compare=False 应忽略 api_key"
    assert cfg.label == twin.label

    # 4) frozen + 参与比较的字段 → 自动可 hash
    assert isinstance(hash(cfg), int) and hash(cfg) == hash(twin)
    print(f"  hash(cfg) == hash(仅密钥不同的实例) -> {hash(cfg) == hash(twin)}")

    # 5) __post_init__ 校验
    try:
        ModelConfig(model="")
    except ValueError as e:
        print(f"  model 为空抛: {e}")
    else:  # pragma: no cover
        raise AssertionError("C1: model 为空没抛错")
    try:
        ModelConfig(temperature=5.0)
    except ValueError as e:
        print(f"  temperature=5.0 抛: {e}")
    else:  # pragma: no cover
        raise AssertionError("C1: temperature 越界没抛错")

    _pass("C1", "改字段抛 FrozenInstanceError、repr 无密钥、只差密钥的两实例相等且可 hash")


def c2() -> None:
    """C2: replace() 改配置，原件不动。"""
    cfg = ModelConfig(api_key="sk-SECRET-1234", temperature=0.7, model="deepseek-chat")
    changed = dataclasses.replace(cfg, temperature=0.1, model="deepseek-coder")

    assert cfg.temperature == 0.7 and cfg.model == "deepseek-chat", "C2: 原对象被改了"
    assert changed.temperature == 0.1 and changed.model == "deepseek-coder"
    assert changed.api_key == cfg.api_key, "C2: replace 应沿用原密钥"
    assert cfg is not changed
    print(f"  原对象 {cfg.label} → 新对象 {changed.label}（密钥仍是 {changed.api_key!r}）")

    # 真实 Settings 也一样：replace 返回新对象
    from assistant.settings import Settings

    real = Settings(api_key="sk-test")
    real2 = dataclasses.replace(real, timeout=5.0, max_retries=0)
    print(f"  Settings timeout {real.timeout} -> {real2.timeout}，model 不变: {real2.model}")
    assert real.timeout == 30.0 and real2.timeout == 5.0 and real2.model == real.model
    assert "sk-test" not in repr(real2), "C2: repr 又泄露密钥了"

    _pass("C2", "replace() 返回全新对象、原配置一字未动、密钥被沿用")


def c3() -> None:
    """C3: 反射真实 Settings —— 字段、repr=False、frozen、validate 报错。"""
    from assistant.errors import LLMConfigError
    from assistant.settings import Settings

    names = [f.name for f in fields(Settings)]
    print(f"  Settings 字段({len(names)}) = {names}")
    assert "api_key" in names and "timeout" in names

    api_key_field = next(f for f in fields(Settings) if f.name == "api_key")
    assert api_key_field.repr is False, "C3: api_key 的 repr 必须是 False"
    print(f"  api_key 的 repr=False -> {api_key_field.repr}")

    assert Settings.__dataclass_params__.frozen is True, "C3: Settings 必须是 frozen"
    print(f"  Settings.__dataclass_params__.frozen -> {Settings.__dataclass_params__.frozen}")

    # validate() 的三类错误
    bad_cases = [
        Settings(api_key=""),
        Settings(api_key="k", base_url="ftp://x"),
        Settings(api_key="k", timeout=0),
    ]
    for s in bad_cases:
        try:
            s.validate()
        except LLMConfigError as e:
            print(f"  validate 抛: {str(e).splitlines()[0]}")
        else:  # pragma: no cover
            raise AssertionError("C3: 非法配置竟然没抛 LLMConfigError")
    assert Settings(api_key="k").validate() is None
    print(f"  合法配置 validate() 返回 {Settings(api_key='k').validate()!r}")

    _pass("C3", "反射确认 Settings 是 frozen、api_key 的 repr=False，且三类非法配置都抛 LLMConfigError")


def main() -> None:
    here = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
    print("--- A ---")
    a1()
    a2()
    a3()

    print("\n--- B ---")
    b1()
    b2()
    b3()

    print("\n--- C ---")
    c1()
    c2()
    c3()

    print(f"\n全部 9 题跑完，退出码 0（Python {sys.version.split()[0]}，题库 {here}）")


if __name__ == "__main__":
    main()
