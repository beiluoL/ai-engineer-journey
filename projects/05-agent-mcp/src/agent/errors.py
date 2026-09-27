"""Project 05 —— 异常体系。

设计原则（和 Project 04 一脉相承）：

1. 所有异常继承同一个根 ``AgentError``，调用方只需要 ``except AgentError``
   就能兜住整条链路，同时还能 ``isinstance`` 精确到某一步。
2. **工具执行阶段的错误不往上抛**。LLM 那一侧只吃文本，如果工具抛异常把
   整个 Agent 打断，一次工具失败就等于整轮任务失败 —— 这在生产里是不能
   接受的。所以 ``ToolRegistry.call`` 永远返回 ``ToolResult(error=...)``，
   把错误当成"工具说的话"回灌给模型（见 agent.py 的循环）。
   只有"注册层/参数层"的结构性错误才抛 ``InvalidToolCallError``。
3. 循环层面的失败（步数超限、连续工具失败）抛 ``AgentLoopError``，
   它是 ``AgentError`` 的子类，让 CLI 可以统一打印友好提示。
"""

from __future__ import annotations

__all__ = [
    "AgentError",
    "ToolError",
    "ToolNotFoundError",
    "ToolSchemaError",
    "LLMError",
    "LLMResponseError",
    "AgentLoopError",
    "InvalidToolCallError",
    "MaxStepsExceeded",
    "TooManyToolFailures",
]


class AgentError(Exception):
    """Agent 链路的根异常。"""


# --------------------------------------------------------------------------
# Tool 层
# --------------------------------------------------------------------------
class ToolError(AgentError):
    """工具实现主动抛出的错误（会被 registry 转成 ToolResult.error）。"""


class ToolNotFoundError(ToolError):
    """模型调用了一个没注册的工具。"""


class ToolSchemaError(AgentError):
    """Tool 定义本身有问题（缺 name / schema 不合法）。"""


# --------------------------------------------------------------------------
# LLM 层
# --------------------------------------------------------------------------
class LLMError(AgentError):
    """调用大模型阶段发生的错误。"""


class LLMResponseError(LLMError):
    """大模型返回了无法解析的结构。"""


# --------------------------------------------------------------------------
# Agent 循环层
# --------------------------------------------------------------------------
class AgentLoopError(AgentError):
    """Agent 一轮任务执行不下去。"""


class InvalidToolCallError(AgentLoopError):
    """模型给出的 tool_call 本身不合法（缺 id / name，参数不是 dict）。"""


class MaxStepsExceeded(AgentLoopError):
    """步数用尽仍未给出最终答案。"""


class TooManyToolFailures(AgentLoopError):
    """连续工具失败次数超过阈值，主动放弃，避免无限空转。"""
