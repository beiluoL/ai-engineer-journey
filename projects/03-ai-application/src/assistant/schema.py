"""结构化输出：让模型的输出能被程序消费（对应 milestones/03）。

强度阶梯：
    ① Prompt 里写「只输出 JSON」        —— 弱
    ② response_format=json_object      —— 保证是合法 JSON，不保证字段
    ③ 用 tools 强制 schema（Chapter 08）—— 强，但请求复杂

这里实现 ② + Pydantic 校验 + 一次重试。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from assistant.errors import StructuredOutputError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# 模型很爱给 JSON 裹一层 markdown 围栏，解析前必须先剥掉。
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.M)


def extract_json(raw: str) -> Any:
    """从模型输出里尽力抠出一个 JSON 值。

    支持三种情况：
    1. 裸 JSON
    2. ```json ... ``` 围栏
    3. 前后带解释文字（取第一个 { 到最后一个 }）
    """
    cleaned = _FENCE.sub("", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise json.JSONDecodeError("没有找到 JSON 结构", cleaned, 0)
    return json.loads(cleaned[start : end + 1])


def parse_structured(raw: str, model_cls: type[T]) -> T:
    """解析 + 校验。失败抛 StructuredOutputError（带原文摘要，便于回灌重试）。"""
    try:
        data = extract_json(raw)
    except json.JSONDecodeError as e:
        raise StructuredOutputError(f"输出不是合法 JSON：{e}") from e
    try:
        return model_cls.model_validate(data)
    except ValidationError as e:
        raise StructuredOutputError(f"字段校验失败：{_brief(e)}") from e


def _brief(err: ValidationError) -> str:
    """把 Pydantic 的报错压缩成适合回灌给模型的一小段话。"""
    parts = []
    for item in err.errors()[:5]:
        loc = ".".join(str(x) for x in item["loc"])
        parts.append(f"{loc}: {item['msg']}")
    return "；".join(parts)[:300]


async def structured(
    client,
    messages: list[dict],
    model_cls: type[T],
    max_retry: int = 1,
) -> T:
    """调用模型并按 schema 校验；失败时把校验错误回灌重试。

    client 只需要实现 `chat(messages, response_format=?)`。
    """
    last_error = ""
    for attempt in range(max_retry + 1):
        extra: list[dict] = []
        if last_error:
            extra = [{
                "role": "user",
                "content": f"上一轮输出不符合要求：{last_error}\n请严格按字段要求重新输出 JSON。",
            }]
            logger.warning("结构化输出第 %d 次重试：%s", attempt, last_error[:120])

        raw = await client.chat(
            messages + extra,
            response_format={"type": "json_object"},
        )
        try:
            return parse_structured(raw, model_cls)
        except StructuredOutputError as e:
            last_error = str(e)

    raise StructuredOutputError(
        f"结构化输出重试 {max_retry + 1} 次仍失败：{last_error}"
    )
