"""Project 05 —— Research Agent。

一句话概括这一版的区别：**RAG 从"藏在 pipeline 里的步骤"
变成"摆在模型面前的工具"**。模型自己决定什么时候查、查什么词。

    **Milestone 05** 补上「循环之外的状态管理」：工作记忆裁剪 + 草稿纸 ——
    让 Agent 真的能跑多步骤任务，而不只是多聊几轮。

    from agent.agent import build_agent
    from agent.llm import DeepSeekLLM

    agent = build_agent(DeepSeekLLM(), scratchpad=True)
    result = agent.run("对比 Project 01 与 Project 04 的持久化方式")
    print(result.answer)
    print(result.notes)     # 中间结论留在草稿纸上，不随历史被裁
"""

from .agent import AgentResult, ReActAgent, Step, build_agent
from .errors import (
    AgentError,
    AgentLoopError,
    InvalidToolCallError,
    LLMError,
    LLMResponseError,
    MaxStepsExceeded,
    ToolError,
    ToolNotFoundError,
    TooManyToolFailures,
    RepeatedToolCall,
)
from .llm import DeepSeekLLM, FakeLLM, LLM, LLMMessage, RecordingLLM, ScriptedLLM
from .memory import Scratchpad, estimate_messages_tokens, estimate_tokens, trim_history
from .registry import ToolRegistry
from .settings import AGENT_SYSTEM_PROMPT, AgentSettings
from .tools import (
    BUILTIN_CORPUS,
    CalculatorTool,
    FunctionTool,
    NowTool,
    RagSearchTool,
    ReadNotesTool,
    WriteNoteTool,
    Tool,
    ToolCall,
    ToolResult,
    calculator,
    default_tools,
    function_to_schema,
    keyword_search,
    make_http_search_tool,
)

__all__ = [
    "AgentError",
    "AgentLoopError",
    "InvalidToolCallError",
    "LLMError",
    "LLMResponseError",
    "MaxStepsExceeded",
    "ToolError",
    "ToolNotFoundError",
    "TooManyToolFailures",
    "RepeatedToolCall",
    "AgentResult",
    "ReActAgent",
    "Step",
    "build_agent",
    "DeepSeekLLM",
    "FakeLLM",
    "LLM",
    "LLMMessage",
    "RecordingLLM",
    "ScriptedLLM",
    "ToolRegistry",
    "Scratchpad",
    "WriteNoteTool",
    "ReadNotesTool",
    "estimate_tokens",
    "estimate_messages_tokens",
    "trim_history",
    "AGENT_SYSTEM_PROMPT",
    "AgentSettings",
    "BUILTIN_CORPUS",
    "CalculatorTool",
    "FunctionTool",
    "RagSearchTool",
    "Tool",
    "ToolCall",
    "ToolResult",
    "calculator",
    "default_tools",
    "function_to_schema",
    "keyword_search",
    "make_http_search_tool",
]
