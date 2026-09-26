"""Chapter 03 演示 —— 类型提示：运行时读取 / 泛型 / 校验 / 注解字符串化陷阱。

对应 milestones/03-type-hints.md 的 6 / 12 / 13 / 16 / 19 / 坑 1：

    get_type_hints         → 把注解当成数据读出来（给框架用）
    Generic[T]             → 一个容器，装什么类型由调用方决定
    Optional / Union       → 「可能是 None」必须显式写
    运行时校验（pydantic）   → 类型提示只是注释，边界还得靠真校验
    注解字符串化            → from __future__ import annotations 让 __annotations__ 变成字符串

注意：这个文件**故意不写** from __future__ import annotations，
所以第 1 段读到的注解是真对象，好和最后那段坑做对照。

运行：

    python3 demos/demo-type-hints.py
"""

import importlib.util
import tempfile
from pathlib import Path
from typing import Generic, Optional, TypeVar, TypedDict, Union, get_type_hints


# ============================================================
# 0. 业务结构：TypedDict 描述「这个 dict 长什么样」
# ============================================================


class Message(TypedDict):
    role: str
    content: str


class LLMResponse(TypedDict):
    content: str
    model: str


def chat(
    model: str,
    messages: list[Message],
    temperature: float | None = None,
) -> LLMResponse:
    """一个带完整注解的函数。"""
    raise NotImplementedError


T = TypeVar("T")


class Box(Generic[T]):
    """泛型容器：具体类型由调用方填。"""

    def __init__(self, item: T) -> None:
        self.item = item


def first_of(items: list[T]) -> T | None:
    """返回第一个元素，空列表返回 None。"""
    return items[0] if items else None


def legacy_style(a: Optional[str], b: Union[int, float]) -> Optional[int]:
    """老写法：Optional / Union。"""
    return len(a) if a is not None else None


def main() -> None:
    # ---- 1. 把注解当成数据读出来 ----
    print("=" * 62)
    print("1. __annotations__ vs get_type_hints()")
    print("=" * 62)
    print("chat.__annotations__:")
    for name, annotation in chat.__annotations__.items():
        print(f"    {name}: {annotation}")
    print("typing.get_type_hints(chat):")
    for name, annotation in get_type_hints(chat).items():
        print(f"    {name}: {annotation}")

    print()
    print("Optional[str] 和 str | None 其实是同一个东西：")
    print(f"  legacy_style.__annotations__ = {legacy_style.__annotations__}")
    print(f"  get_type_hints(legacy_style) = {get_type_hints(legacy_style)}")

    # ---- 2. 泛型 ----
    print()
    print("=" * 62)
    print("2. 泛型 Generic[T]：一份代码服务多种类型")
    print("=" * 62)
    box = Box[int](item=42)
    print(f"  Box[int](item=42).item = {box.item}，__orig_class__ = {box.__orig_class__}")
    print(f"  get_type_hints(Box.__init__) = {get_type_hints(Box.__init__)}")
    print(f"  get_type_hints(first_of)     = {get_type_hints(first_of)}")
    print(f"  first_of(['a','b']) = {first_of(['a', 'b'])!r}   first_of([]) = {first_of([])!r}")

    # ---- 3. 类型提示不是强制类型系统 ----
    print()
    print("=" * 62)
    print("3. 坑：写了 int 也拦不住你（所以边界要真校验）")
    print("=" * 62)
    from pydantic import BaseModel, ValidationError

    class ChatRequest(BaseModel):
        model: str
        temperature: float
        max_tokens: int = 1024

    print(f"  合法输入: {ChatRequest(model='deepseek-chat', temperature=0.7)}")
    try:
        ChatRequest(model="deepseek-chat", temperature="hot")    # 字符串塞进 float
    except ValidationError as e:
        for err in e.errors():
            print(f"  非法输入被拦下 → loc={err['loc']} type={err['type']} msg={err['msg']}")
    print("  → 类型提示管静态检查；真正挡住脏数据的是运行时校验")

    # ---- 4. 注解字符串化陷阱 ----
    print()
    print("=" * 62)
    print("4. 坑：from __future__ import annotations 把注解变成字符串")
    print("=" * 62)
    with tempfile.TemporaryDirectory() as tmp:
        no_future = """
def ask(messages: list[Message]) -> LLMResponse:
    ...

class Message(dict): pass
class LLMResponse(dict): pass
"""
        with_future = """
from __future__ import annotations

def ask(messages: list[Message]) -> LLMResponse:
    ...

class Message(dict): pass
class LLMResponse(dict): pass
"""
        unresolvable = """
from __future__ import annotations

def ask(messages: list[Message]) -> LLMResponse:
    ...
"""

        def load(name: str, source: str) -> object:
            path = Path(tmp) / f"{name}.py"
            path.write_text(source, encoding="utf-8")
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)     # 注解是否被求值，看这一步会不会炸
            return module

        print("[A] 没有 future import，注解却被前向引用（类定义在函数后面）")
        try:
            load("mod_plain", no_future)
        except NameError as e:
            print(f"    NameError: {e}")
        print("    → 不用 future import 时，注解在类定义时就要求值，前向引用直接炸")

        print()
        print("[B] 加了 from __future__ import annotations：模块能导入了")
        mod = load("mod_future", with_future)
        print(f"    ask.__annotations__ = {mod.ask.__annotations__}")
        print("    → 全是字符串，pydantic / 序列化框架拿到手没法直接用")

        print()
        print("[C] 用 typing.get_type_hints 把字符串 eval 回真类型")
        print(f"    get_type_hints(ask) = {get_type_hints(mod.ask)}")

        print()
        print("[D] 但名字根本不存在时，get_type_hints 一样会炸")
        try:
            get_type_hints(load("mod_bad", unresolvable).ask)
        except NameError as e:
            print(f"    NameError: {e}")

    print()
    print("结论：注解可能是字符串，也可能是解析不出来的名字；")
    print("      想拿类型就统一用 get_type_hints，别直接读 __annotations__。")


if __name__ == "__main__":
    main()
