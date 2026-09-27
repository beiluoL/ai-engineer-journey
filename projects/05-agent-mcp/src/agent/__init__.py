"""Project 05 —— Research Agent。

一句话概括这一版的区别：**RAG 从"藏在 pipeline 里的步骤"
变成"摆在模型面前的工具"**。模型自己决定什么时候查、查什么词。

    from agent.agent import ReActAgent
    from agent.llm import DeepSeekLLM
    from agent.registry import ToolRegistry

    agent = ReActAgent(DeepSeekLLM(), ToolRegistry())
    print(agent.run("Project 04 的会话是怎么落盘的？").answer)
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
)
from .llm import DeepSeekLLM, FakeLLM, LLM, LLMMessage, RecordingLLM, ScriptedLLM
from .registry import ToolRegistry
from .settings import AGENT_SYSTEM_PROMPT, AgentSettings
from .tools import (
    BUILTIN_CORPUS,
    CalculatorTool,
    FunctionTool,
    RagSearchTool,
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
