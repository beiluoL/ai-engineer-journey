"""Project 05 —— 工具注册表。

Registry 干四件事，每一件都有明确的"为什么"：

1. **收 schema**：把注册工具的 JSON Schema 汇总成一个数组交给模型。
   汇总的位置只有这一处，不会出现"某个工具忘了给 schema"的情况。

2. **校验 + 纠偏**：模型给的参数不总是对的 —— 数字写成字符串、
   必填项直接漏掉、甚至编一个不存在的工具名。这里把三件事分开处理：
      - 不存在的工具 → ``ToolResult(error="未知工具...")``（让模型换个名字重试）
      - 缺必填     → ``ToolResult(error="缺少必填参数...")``
      - 类型差一点  → **自动纠偏**，字符串 "3" 变成整数 3

   第三条是真实项目里最常见的修法：OpenAI 在小模型上经常把整数写成
   ``"3"``，如果直接抛错，模型会陷入"重试—报错—重试"的死循环；
   而纠偏是**不改变语义**的修复，成本低得多。

3. **执行并兜异常**：任何异常都不是抛出，而是变成 ``ToolResult.error``。

4. **记录派发**：``last_results`` 让 demo 和单测能打印真实的调用流水，
   截图素材就是从这里出来的。
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .errors import InvalidToolCallError, ToolNotFoundError, ToolSchemaError
from .tools import FunctionTool, Tool, ToolCall, ToolResult, default_tools, function_to_schema

__all__ = ["ToolRegistry"]


class ToolRegistry:
    """线程安全不在这一层做 —— Agent 默认是单轮同步执行。

    需要并发的话，真正的坑是"多个工具同时写同一个文件"，
    那是工具的职责，不是注册表的职责。
    """

    def __init__(self, tools: Iterable[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.schemas_cache: dict[str, dict[str, Any]] = {}
        self.last_results: list[ToolResult] = []
        # 默认装载内置工具集：绝大多数场景不需要"什么都不装"的注册表，
        # 而空注册表会让 Agent 退化成"只有嘴没有手"。
        for tool in (default_tools() if tools is None else tools):
            self.register(tool)

    # ---------------------------------------------------------------- 注册
    def register(self, tool: Tool) -> None:
        name = getattr(tool, "name", "") or ""
        if not name:
            raise ToolSchemaError(f"工具 {tool!r} 缺少 name")
        self._tools[name] = tool

    def register_function(
        self,
        fn: Any,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> FunctionTool:
        """把裸函数丢进注册表，返回造出来的 Tool 便于断言。"""
        tool = FunctionTool(fn, name=name, description=description)
        self.register(tool)
        return tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    # ---------------------------------------------------------------- schema
    def schema_of(self, name: str) -> dict[str, Any]:
        """单个工具的 function-calling schema。结果带缓存。"""
        if name not in self.schemas_cache:
            tool = self._tools[name]
            schema = tool.schema()["function"]
            self.schemas_cache[name] = schema
        return self.schemas_cache[name]

    def schemas(self) -> list[dict[str, Any]]:
        """给模型的全部工具声明。

        注意返回的是**工具对象**（``{"type":"function","function":{...}}``），
        不是内层那个 function 对象。早期版本直接返回内层，服务端一直 422
        ``missing field `type` `` —— 因为少了最外面那层 type。

        ``schema_of`` 返回内层，是为了让调用方方便看参数；两者别混。
        """
        return [{"type": "function", "function": self.schema_of(n)} for n in self.names()]

    # ---------------------------------------------------------------- 执行
    def call(self, call: ToolCall) -> ToolResult:
        """执行一次调用。结构上不合法直接抛，执行期错误一律转 ToolResult。"""
        if not isinstance(call, ToolCall):
            raise InvalidToolCallError(f"call 必须是 ToolCall，收到 {type(call).__name__}")

        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                error=f"未知工具「{call.name}」。当前可用：{', '.join(self.names()) or '（空）'}",
            )

        kwargs, err = self._prepare_kwargs(call)
        if err:
            return ToolResult(call_id=call.id, name=call.name, error=err)

        try:
            output = tool.run(**kwargs)
        except Exception as exc:  # noqa: BLE001 —— 这里就是要吞掉所有异常
            detail = str(exc) or type(exc).__name__
            return ToolResult(call_id=call.id, name=call.name, error=f"{type(exc).__name__}: {detail}")
        return ToolResult(call_id=call.id, name=call.name, output=str(output))

    def call_many(self, calls: Sequence[ToolCall]) -> list[ToolResult]:
        results = [self.call(c) for c in calls]
        self.last_results.extend(results)
        return results

    def dispatch(self, messages: list[dict[str, Any]], result: ToolResult) -> dict[str, Any]:
        """把 ToolResult 转成协议要求的 tool 消息。

        单独拎出来是因为这块格式最容易记错：``role`` 必须是 ``"tool"``，
        还要带上 ``tool_call_id`` 和 ``name``，少一个字段服务端直接 400。
        """
        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "name": result.name,
            "content": result.render(),
        }

    # ---------------------------------------------------------------- 内部
    def _prepare_kwargs(self, call: ToolCall) -> tuple[dict[str, Any], str | None]:
        schema = self.schema_of(call.name)
        params = schema.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])

        for key in call.arguments:
            if key not in props:
                return {}, f"参数「{key}」不存在于 {call.name} 的声明中"

        kwargs: dict[str, Any] = {}
        for pname, pspec in props.items():
            if pname not in call.arguments:
                if pname in required:
                    return {}, f"缺少必填参数「{pname}」"
                continue
            raw = call.arguments[pname]
            coerced, err = _coerce(raw, pspec.get("type"))
            if err:
                return {}, f"参数「{pname}」类型错误：{err}"
            kwargs[pname] = coerced
        return kwargs, None


def _coerce(raw: Any, type_hint: str | None) -> tuple[Any, str | None]:
    """尽力纠偏。纠不动就返回错误说明，由 registry 转成 ToolResult。"""
    if type_hint is None or raw is None:
        return raw, None
    if type_hint == "integer":
        if isinstance(raw, bool):
            return None, "期望整数，收到布尔值"
        if isinstance(raw, int):
            return raw, None
        if isinstance(raw, float) and float(raw).is_integer():
            return int(raw), None
        if isinstance(raw, str):
            try:
                return int(raw.strip()), None
            except ValueError:
                return None, f"期望整数，收到字符串 {raw!r}"
        return None, f"期望整数，收到 {type(raw).__name__}"
    if type_hint == "number":
        if isinstance(raw, bool):
            return None, "期望数字，收到布尔值"
        if isinstance(raw, (int, float)):
            return float(raw), None
        if isinstance(raw, str):
            try:
                return float(raw.strip()), None
            except ValueError:
                return None, f"期望数字，收到字符串 {raw!r}"
        return None, f"期望数字，收到 {type(raw).__name__}"
    if type_hint == "boolean":
        if isinstance(raw, bool):
            return raw, None
        if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
            return raw.strip().lower() == "true", None
        if isinstance(raw, (int, float)) and raw in (0, 1):
            return bool(raw), None
        return None, f"期望布尔值，收到 {raw!r}"
    if type_hint == "array":
        if isinstance(raw, list):
            return raw, None
        if isinstance(raw, str):
            return None, "期望数组，收到字符串"
        return raw, None
    return str(raw), None


def assert_valid_schema(schema: dict[str, Any]) -> None:
    """自测用：一个合格的函数 schema 必须长什么样。"""
    fn = schema.get("function", schema)
    if not fn.get("name"):
        raise ToolSchemaError("schema 缺少 function.name")
    params = fn.get("parameters") or {}
    if params.get("type") != "object":
        raise ToolSchemaError("parameters.type 必须是 object")
    if not isinstance(params.get("properties"), dict):
        raise ToolSchemaError("parameters.properties 必须是对象")


_ = function_to_schema  # 保持导入可见，供测试直接断言签名推导
