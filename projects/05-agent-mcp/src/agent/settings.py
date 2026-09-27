"""Project 05 —— 配置。

和 Project 04 的 ``RAGSettings`` 保持同一套写法：**frozen dataclass +
``.replace()`` 派生**。理由一样：配置对象会作为参数一路透传到
LLM / Agent / Registry，可变配置在并发或多轮里迟早出事。

为什么不用 Pydantic Settings？因为这一层的依赖要尽量少，标准库 +
环境变量足够，少一个依赖就少一个"装不上就跑不了"的失败点。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any

__all__ = ["AgentSettings", "AGENT_SYSTEM_PROMPT"]

AGENT_SYSTEM_PROMPT = """你是一个会调用工具的研究助手。

工作规则：
- 只使用下方列出的工具获取信息。工具返回的文本是你的唯一事实来源。
- 需要外部知识、计算或数据时，先调用工具，再根据工具返回回答。
- 不要编造工具返回的内容；工具没说到的，就如实说"工具里没有"。
- 可以连续调用多个工具，每次只调用一个工具，调用结果会追加在对话里。
- 工具足够回答时，用一句话给出最终答案，不要重复罗列工具输出。

再次强调：不要凭记忆回答，先调用工具。"""


@dataclass(frozen=True)
class AgentSettings:
    """Agent 运行时配置。

    默认值全部是"离线也能跑"的：模型地址指向 DeepSeek，但没有 API Key
    时 DeepSeekLLM 会在构造阶段就抛错，测试里一律用 FakeLLM，
    所以默认值只需保证**结构合法**，不保证能联网。
    """

    model: str = "deepseek-chat"
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.0
    top_p: float = 0.95
    max_tokens: int = 2048

    # ---- Agent 循环 ----
    max_steps: int = 8
    """最多循环几轮。一轮 = 一次 LLM 调用 + 其触发的全部工具执行。

    设 8 而不是 20：这一个数字就是 Agent 的**成本闸门**。
    LLM 每多一轮就在烧钱，恶性循环时步数上限是唯一的兜底。
    """

    max_tool_failures: int = 3
    """连续多少次的 `ToolResult.error` 之后主动放弃。"""

    trace_dir: str = ""
    """轨迹落盘目录，空字符串表示不落盘。"""

    log_level: str = "INFO"

    def replace(self, **changes: Any) -> "AgentSettings":
        """派生一份新配置（frozen dataclass 的标准姿势）。"""
        return replace(self, **changes)

    @classmethod
    def from_env(cls, **overrides: Any) -> "AgentSettings":
        """从环境变量读取，允许关键字覆盖。

        只认 ``AGENT_`` 前缀，避免和别的项目的环境变量打架。
        """
        values: dict[str, Any] = {}
        for fld in cls.__dataclass_fields__.values():  # type: ignore[union-attr]
            raw = os.getenv(f"AGENT_{fld.name.upper()}")
            if raw is None or raw == "":
                continue
            values[fld.name] = _coerce_annotation(raw, fld.type)
        values.update(overrides)
        return cls(**values)


def _coerce_annotation(raw: str, annotation: Any) -> Any:
    """把环境变量字符串转成字段声明的类型。只处理标量，够用即可。"""
    name = str(annotation)
    if name in ("int", "integer"):
        return int(raw)
    if name in ("float", "number"):
        return float(raw)
    if name in ("bool", "boolean"):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return raw
