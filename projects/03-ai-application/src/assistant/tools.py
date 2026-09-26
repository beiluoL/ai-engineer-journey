"""工具注册表（对应 milestones/08-function-calling.md）。

核心认知：**模型不执行任何代码**。
模型只是说「我想调用 get_weather，参数是 city='北京'」——真正执行的是你的程序。

所以这里要提供三样东西：
    1. schema —— 给模型看的接口文档（JSON Schema）
    2. dispatch —— 按名字找到函数并执行
    3. 错误即结果 —— 工具不存在/参数错都作为返回值回灌，而不是崩

安全边界：只注册只读、无害的工具。绝不注册 shell / 删除 / 任意文件读写。
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Callable
from typing import get_type_hints

logger = logging.getLogger(__name__)

REGISTRY: dict[str, Callable[..., object]] = {}

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def tool(fn: Callable[..., object]) -> Callable[..., object]:
    """把一个函数注册成可被调用的工具，schema 从类型注解自动生成。

    坑：模块里有 `from __future__ import annotations` 时，
    `inspect.signature()` 拿到的注解是**字符串**（"float" 而不是 float），
    直接查表会得到 string，模型就会传 "128" 而不是 128。
    必须用 `typing.get_type_hints()` 把字符串注解解析回真实类型。
    """
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        annotation = hints.get(name, str)
        schema_type = _TYPE_MAP.get(annotation, "string")
        properties[name] = {"type": schema_type, "description": name}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    fn._tool_schema = {  # type: ignore[attr-defined]
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip() or fn.__name__,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
    REGISTRY[fn.__name__] = fn
    return fn


def schemas() -> list[dict]:
    """全部工具的 JSON Schema（发给模型）。"""
    return [fn._tool_schema for fn in REGISTRY.values()]  # type: ignore[attr-defined]


def dispatch(name: str, raw_args: str) -> dict:
    """执行工具。任何问题都作为 {'error': ...} 返回，交给模型自己纠正。"""
    try:
        args = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError as e:
        return {"error": f"参数不是合法 JSON：{e}"}

    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"没有名为 {name!r} 的工具，可用工具: {sorted(REGISTRY)}"}

    try:
        result = fn(**args)
    except TypeError as e:
        return {"error": f"参数不匹配：{e}"}
    except Exception as e:  # 工具内部异常也不该让整个应用崩
        logger.exception("工具 %s 执行失败", name)
        return {"error": f"工具执行失败：{type(e).__name__}: {e}"}

    return {"result": result}


def describe_calls(tool_calls: list[dict]) -> str:
    """把工具调用渲染成人类可读的一行（用于 CLI 展示与日志）。"""
    parts = []
    for call in tool_calls:
        fn = call.get("function", {})
        parts.append(f"{fn.get('name')}({fn.get('arguments', '')})")
    return "，".join(parts)


# ---- 内置工具（全部只读、无害、不联网） ----

@tool
def add(a: float, b: float) -> float:
    """计算两个数的和。用于演示工具调用。"""
    return a + b


@tool
def multiply(a: float, b: float) -> float:
    """计算两个数的乘积。"""
    return a * b


@tool
def get_weather(city: str) -> dict:
    """查询指定城市今天的天气（演示用：返回固定数据，不联网）。"""
    return {"city": city, "temp_c": 26, "desc": "晴", "source": "demo"}
