"""Project 05 —— Tool 层。

三个要讲清的概念：

1. **Tool 的最小接口**：一个名字、一段描述、一个 ``run(**kwargs) -> str``。
   ``run`` 必须返回**字符串**，因为大模型只吃文本 —— 返回 dict 就意味着
   有人要写序列化，那部分通用逻辑应该由框架（registry）统一做，
   而不是每个工具各写一遍。

2. **ToolCall 与 ToolResult 是分离的**。
   ``ToolCall(id, name, arguments)`` 是"模型提出的要求"，
   ``ToolResult(call_id, name, output|error)`` 是"执行的结果"。
   两者靠 ``call_id`` 对应 —— 这和 OpenAI / Anthropic 的协议一致：
   一轮里模型可能调用多个工具，靠 id 把"哪个结果属于哪个调用"对上。

3. **"检索即工具"**：RAG 里的检索在这一版不再藏在 pipeline 内部，
   而是被包成一个叫 ``rag_search`` 的工具交给模型自己决定何时调用。
   这一句话的区别，就是"问答系统"和"Agent"的区别。
"""

from __future__ import annotations

import ast
import inspect
import operator
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterator, Sequence

import httpx

from .errors import ToolError, ToolSchemaError

__all__ = [
    "ToolCall",
    "ToolResult",
    "Tool",
    "FunctionTool",
    "function_to_schema",
    "keyword_search",
    "calculator",
    "make_http_search_tool",
    "BUILTIN_CORPUS",
    "default_tools",
]


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ToolCall:
    """模型提出的工具调用。

    ``arguments`` 是 dict，frozen 只保证"这个对象不被重新赋值"，
    所以 run 内部拿到什么就当什么用，不要原地改它 —— 需要改先 ``dict(args)``。
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("tool_call.id 不能为空")
        if not self.name:
            raise ValueError("tool_call.name 不能为空")
        if self.arguments is None:
            # 模型偶尔会把 null 塞进来，归一化成空 dict 比报错更友好
            object.__setattr__(self, "arguments", {})
        elif not isinstance(self.arguments, dict):
            raise ToolSchemaError(f"tool_call.arguments 必须是 dict，收到 {type(self.arguments).__name__}")


@dataclass(frozen=True)
class ToolResult:
    """一次工具执行的结果。**永远不抛异常**。"""

    call_id: str
    name: str
    output: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def render(self) -> str:
        """转成回灌给模型的文本。

        错误也用同样的格式回灌，因为对模型来说"工具报错"和"工具返回了一段
        文字"没有区别 —— 这样模型才有机会自己换个参数重试。
        """
        if self.error is None:
            return self.output
        return f"[工具执行失败] {self.name}: {self.error}"


class Tool(ABC):
    """工具基类。子类至少要写 ``name`` / ``description`` / ``run``。"""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """执行工具，**返回值必须是 str**。抛异常由 registry 兜住。"""

    def schema(self) -> dict[str, Any]:
        """按 OpenAI function-calling 格式描述自己。默认由类属性生成。"""
        return function_schema(self.name, self.description, {"type": "object", "properties": {}, "required": []})


def function_schema(
    name: str,
    description: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """拼一个合法的 function-calling schema。

    ``parameters`` 必须是 object 类型；字段写错（比如把 required 写成字符串）
    在服务端是 400，在本地只能靠这条断言挡住。
    """
    if parameters.get("type") != "object":
        raise ToolSchemaError("parameters.type 必须是 object")
    for key in parameters.get("required", []):
        if key not in parameters.get("properties", {}):
            raise ToolSchemaError(f"required 里的「{key}」没有对应的 property")
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


class FunctionTool(Tool):
    """把一个普通 Python 函数变成 Tool。

    适合工具逻辑简单、schema 不用手写的场景，也是本项目演示
    "Python 函数即工具" 的直接证据。
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self._fn = fn
        self._name = name or fn.__name__
        self._description = description or (inspect.getdoc(fn) or "").strip() or f"调用 {self._name}"
        super().__init__()

    @property
    def name(self) -> str:            # type: ignore[override]
        return self._name

    @property
    def description(self) -> str:     # type: ignore[override]
        return self._description

    def run(self, **kwargs: Any) -> str:
        return str(self._fn(**kwargs))

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": function_to_schema(self._fn, name=self._name, description=self._description),
        }


def function_to_schema(
    fn: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """从 Python 函数签名反推 JSON Schema。

    这是"少写代码"和"少出错"的交换：手写 schema 可以写得更啰嗦但更贴合语义
    （比如 enum、范围限制），自动推导保证**schema 和代码永远一致** ——
    改了参数忘了改 schema 是最经典的线上事故来源。

    支持类型：`str / int / float / bool / list[str]`，默认值即"非必填"。
    """
    sig = inspect.signature(fn)
    props: dict[str, Any] = {}
    required: list[str] = []

    for pname, p in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        ann = p.annotation
        hint = ann if isinstance(ann, str) else _annotation_name(ann)
        prop: dict[str, Any] = {"type": _TYPE_MAP.get(hint, "string")}
        if hint.startswith("list[") or hint == "list":
            prop["items"] = {"type": "string"}
        if p.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["description"] = f"默认 {p.default!r}"
        props[pname] = prop

    doc = inspect.getdoc(fn) or ""
    desc = description or doc.split("\n")[0].strip()

    return {
        "name": name or fn.__name__,
        "description": desc,
        "parameters": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "list[str]": "array",
    "Optional[str]": "string",
}


def _annotation_name(ann: Any) -> str:
    if isinstance(ann, str):
        return ann
    return getattr(ann, "__name__", str(ann))


# --------------------------------------------------------------------------
# 内置工具 1：rag_search —— 「检索即工具」
# --------------------------------------------------------------------------
BUILTIN_CORPUS: tuple[dict[str, str], ...] = (
    {
        "id": "p01-cli",
        "title": "Project 01 AI CLI Assistant",
        "text": "Python 标准库 argparse 搭单轮问答 CLI，循环读 stdin，回车退出，零第三方依赖。",
        "tags": "project01 cli python argparse",
    },
    {
        "id": "p01-refactor",
        "title": "Project 01 重构",
        "text": "把散落的领域逻辑收进 assistant/ 包，入口 main.py 只做参数解析与退出码，单测覆盖拒答。",
        "tags": "project01 refactor 架构 重构",
    },
    {
        "id": "p02-async",
        "title": "Project 02 Engineering AI Assistant",
        "text": "async CLI + FastAPI 服务层，用 asyncio.Lock 保护单实例状态，uvicorn 承载 HTTP 接口。",
        "tags": "project02 async fastapi uvicorn",
    },
    {
        "id": "p02-lock",
        "title": "Project 02 并发保护",
        "text": "并发写状态会丢更新，asyncio.Lock 把读-改-写整个包起来，压测 20 并发验证不丢。",
        "tags": "project02 lock 并发 asyncio",
    },
    {
        "id": "p03-prompt",
        "title": "Project 03 AI Application",
        "text": "Prompt 模板集中管理，结构化输出用 Pydantic 校验后再回给上游，拒答走独立的 safety 闸门。",
        "tags": "project03 prompt pydantic 结构化输出",
    },
    {
        "id": "p03-tools",
        "title": "Project 03 Function Calling 预告",
        "text": "让模型以 JSON 形式声明意图，再由宿主代码决定真实执行的函数，模型拿到的是函数返回文本。",
        "tags": "project03 function calling tool json",
    },
    {
        "id": "p04-rag",
        "title": "Project 04 Personal RAG",
        "text": "解析分块 embedding 向量库相似度检索重排上下文组装，最后拼成一条带引用的回答。",
        "tags": "project04 rag embedding chroma rerank",
    },
    {
        "id": "p04-session",
        "title": "Project 04 会话与多轮",
        "text": "Turn 不可变、会话落盘走 mkstemp+fsync+os.replace 原子写，历史拼进 prompt 的顺序是 system 历史 本次提问。",
        "tags": "project04 session 多轮 原子写 历史",
    },
    {
        "id": "p05-agent",
        "title": "Project 05 Research Agent",
        "text": "Tool 注册表给模型发 JSON Schema 声明能力，模型返回 tool_call，宿主执行后把结果文本回灌，循环到给出最终答案。",
        "tags": "project05 agent tool function calling react",
    },
    {
        "id": "p05-mcp",
        "title": "Project 05 MCP 预告",
        "text": "MCP 把工具发现调用协议化，Server 暴露能力，Client 接能力，Agent 换工具不用改代码。",
        "tags": "project05 mcp protocol server client",
    },
)


_CJK = "一-鿿"


def _terms(query: str) -> list[str]:
    """把查询切成检索词。

    中文没有空格，而 ``\\w`` 又能匹配汉字 —— 如果直接按 ``\\w+`` 切，
    「会话怎么落盘」会变成**一个**整串，和语料里的「会话与多轮」永远对不上。
    所以这里对连续汉字段额外切出**二元组**（会话 / 话怎 / 怎么 / 么落 / 落盘），
    命中一个就算部分相关。这是不用分词库时的最小可行方案。
    """
    terms: list[str] = []
    for run in re.findall(f"[{_CJK}]+", query):
        terms.append(run)
        terms.extend(run[i:i + 2] for i in range(len(run) - 1))
    terms.extend(re.findall(r"[A-Za-z0-9_]+", query))
    seen: set[str] = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _score(title: str, text: str, tags: str, query: str) -> float:
    """单条语料的得分。title 也要参与，否则「Project 04 Personal RAG」
    会因为项目号只写在 tags 里而永远搜不到。"""
    """确定性打分：命中的检索词越多越靠前，同一个词反复出现再加权。

    英文词必须**整词命中**（``Counter`` 里做 key 比较），不能子串匹配 ——
    否则查询里的 "in" 会被 "em**bedding**" 命中，噪声查询永远有结果。
    汉字串则是子串匹配（二元组天然是子串）。
    """
    hay = f"{title} {text} {tags}".lower()
    ascii_words = re.findall(r"[a-z0-9_]+", hay)
    cjk_run = "".join(re.findall(f"[{_CJK}]", hay))

    score = 0.0
    for term in _terms(query.strip().lower()):
        if not term:
            continue
        # 英文走"前缀匹配"：输入 project 要能命中 project01/project04 这类标记；
        # 但 must-not 也成立 —— in 不会命中 embedding，因为后者不以 in 开头。
        hits = sum(1 for w in ascii_words if w.startswith(term)) if term.isascii() else cjk_run.count(term)
        if hits:
            score += 1.0 + 0.5 * (hits - 1)
    return score


def _iter_docs() -> Iterator[dict[str, str]]:
    return iter(BUILTIN_CORPUS)


def keyword_search(query: str, k: int = 3) -> str:
    """在本地语料里检索，返回命中的片段。Agent 版 RAG 的入场券。"""
    if not query.strip():
        raise ToolError("query 不能为空")
    if k <= 0:
        raise ToolError("k 必须是正整数")
    hits = [doc for doc in BUILTIN_CORPUS if _score(doc["title"], doc["text"], doc["tags"], query) > 0]
    hits.sort(key=lambda d: -_score(d["title"], d["text"], d["tags"], query))
    hits = hits[:k]
    if not hits:
        topics = "、".join(d["title"] for d in BUILTIN_CORPUS[:5])
        return f"语料里没有和「{query}」相关的内容。可查的主题：{topics}"
    return "\n".join(f"[{i}] {d['title']}（{d['id']}）：{d['text']}" for i, d in enumerate(hits, 1))


class RagSearchTool(Tool):
    """把任意检索函数包成工具。默认走本地语料，可换成 HTTP 后端。"""

    name: ClassVar[str] = "rag_search"
    description: ClassVar[str] = (
        "在本地项目知识库里检索资料。传入一个检索词（用自然语言即可），"
        "返回最相关的若干条笔记。事实性问题的答案必须来自这里。"
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索词，直接用用户的提问即可"},
            "k": {"type": "integer", "description": "返回条数，默认 3，最多 5"},
        },
        "required": ["query"],
    }

    def __init__(self, backend: Callable[[str, int], str] | None = None, *, k: int = 3) -> None:
        self._backend = backend or (lambda query, top_k: keyword_search(query, top_k))
        self._k = k
        super().__init__()

    def schema(self) -> dict[str, Any]:
        return function_schema(self.name, self.description, self.parameters)

    def run(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "")
        k = kwargs.get("k", self._k)
        return self._backend(query, k)


def make_http_search_tool(base_url: str, *, k: int = 3, timeout: float = 10.0) -> RagSearchTool:
    """造一个走 HTTP 的 ``rag_search`` —— 后端是 Project 04 的 RAG 服务。

    同一个工具名、两个后端，正是"工具只是能力描述，实现可插拔"的证明。
    """
    import httpx  # 延迟导入：离线测试不需要联网依赖

    def _http_search(query: str, top_k: int) -> str:
        with httpx.Client(timeout=timeout) as client:  # noqa: SIM117
            resp = client.post(f"{base_url.rstrip('/')}/ask", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        payload = resp.json()
        ctx = payload.get("context") or []
        if not ctx:
            return f"检索没有命中：{query}"
        return "\n".join(f"- {c.get('text') or c.get('content')}" for c in ctx)

    return RagSearchTool(backend=_http_search, k=k)


# --------------------------------------------------------------------------
# 内置工具 2：calculator —— 演示「工具不是只有检索」
# --------------------------------------------------------------------------
_OPERATORS: dict[ast.operator, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculator(expression: str) -> str:
    """求值一个算术表达式。

    注意：**这里绝不能用 eval**。``eval`` 会把 ``__import__`` 一起执行，
    等于把代码执行权交给了模型输出的任意字符串。改用 ``ast`` 解析 +
    **白名单节点**，出现任何不在白名单里的节点直接拒绝。
    """
    if not expression or not expression.strip():
        raise ToolError("expression 不能为空")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"解析失败：{exc}") from exc
    try:
        value = _eval_node(tree.body)
    except ToolError:
        raise
    except Exception as exc:  # 运行时错误（除零、溢出等）
        raise ToolError(f"求值失败：{type(exc).__name__}: {exc}") from exc
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return repr(value)


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ToolError("只支持数字字面量")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ToolError(f"不允许的表达式成分：{type(node).__name__}（例如函数调用、名称引用都被禁用）")


class CalculatorTool(Tool):
    name: ClassVar[str] = "calculator"
    description: ClassVar[str] = "计算算术表达式（支持 + - * / // % 与括号，不支持变量和函数）。"
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "算术表达式，例如 (12+8)*3/7"},
        },
        "required": ["expression"],
    }

    def schema(self) -> dict[str, Any]:
        return function_schema(self.name, self.description, self.parameters)

    def run(self, **kwargs: Any) -> str:
        return calculator(kwargs.get("expression", ""))


# --------------------------------------------------------------------------
# 内置工具 3：无副作用工具 —— 当前时间
# --------------------------------------------------------------------------
def now_utc() -> str:
    """返回当前 UTC 时间与日期，用于需要「今天」的问题。"""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class NowTool(Tool):
    name: ClassVar[str] = "now"
    description: ClassVar[str] = "返回当前 UTC 时间与日期。问「今天几号」「现在几点」时用。"
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}, "required": []}

    def schema(self) -> dict[str, Any]:
        return function_schema(self.name, self.description, self.parameters)

    def run(self, **kwargs: Any) -> str:
        return now_utc()


def default_tools() -> Sequence[Tool]:
    """默认注册给 Agent 的工具集。"""
    return [RagSearchTool(), CalculatorTool(), NowTool()]
