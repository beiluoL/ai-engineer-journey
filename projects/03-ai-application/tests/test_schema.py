"""结构化输出测试（milestones/03）。"""

import json

import pytest
from pydantic import BaseModel, Field

from assistant.client import FakeClient
from assistant.errors import StructuredOutputError
from assistant.schema import extract_json, parse_structured, structured


class Person(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)


def test_extract_json_plain():
    assert extract_json('{"name": "小明", "age": 18}') == {"name": "小明", "age": 18}


def test_extract_json_strips_markdown_fence():
    raw = '```json\n{"name": "小明", "age": 18}\n```'
    assert extract_json(raw) == {"name": "小明", "age": 18}


def test_extract_json_surrounded_by_prose():
    raw = '好的，结果如下：\n{"name": "小明", "age": 18}\n希望对你有帮助'
    assert extract_json(raw) == {"name": "小明", "age": 18}


def test_extract_json_fails_loudly():
    with pytest.raises(json.JSONDecodeError):
        extract_json("完全没有 JSON")


def test_parse_structured_validates():
    assert parse_structured('{"name": "小明", "age": 18}', Person).age == 18


def test_parse_structured_rejects_bad_type():
    with pytest.raises(StructuredOutputError, match="字段校验失败"):
        parse_structured('{"name": "小明", "age": "十八岁"}', Person)


async def test_structured_retries_with_error_feedback():
    """校验失败要重试，且把错误回灌给模型（Chapter 03 的关键设计）。"""
    client = FakeClient(script=[
        {"role": "assistant", "content": '{"name": "小明", "age": "十八岁"}'},
        {"role": "assistant", "content": '{"name": "小明", "age": 18}'},
    ])
    person = await structured(client, [{"role": "user", "content": "抽取"}], Person, max_retry=1)

    assert person.age == 18
    assert len(client.calls) == 2
    # 第二次请求里应该带上上一次的校验错误
    assert "不符合要求" in client.calls[1]["messages"][-1]["content"]
    # 并开启了 JSON Mode
    assert client.calls[1]["response_format"] == {"type": "json_object"}


async def test_structured_gives_up_after_max_retry():
    client = FakeClient(script=[
        {"role": "assistant", "content": "不是 JSON"},
        {"role": "assistant", "content": "还不是 JSON"},
    ])
    with pytest.raises(StructuredOutputError):
        await structured(client, [{"role": "user", "content": "x"}], Person, max_retry=1)
