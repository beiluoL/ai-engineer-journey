"""Project 03 练习 02 参考答案：结构化输出、流式与模型参数（纯离线）。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient
from pydantic import ValidationError

from assistant.api import create_app, get_service
from assistant.client import DeepSeekClient, FakeClient
from assistant.errors import LLMConfigError, StructuredOutputError
from assistant.models import SkillExtraction
from assistant.schema import extract_json, parse_structured, structured
from assistant.service import ChatService
from assistant.settings import Settings


def _pass(qid: str, note: str) -> None:
    print(f"[PASS] {qid} {note}")


def a1() -> None:
    qid = "A1"
    expected = {"name": "小明", "age": 18}
    raws = [
        json.dumps(expected, ensure_ascii=False),
        f"```json\n{json.dumps(expected, ensure_ascii=False)}\n```",
        f"结果如下：\n{json.dumps(expected, ensure_ascii=False)}\n以上。",
    ]
    parsed = [extract_json(raw) for raw in raws]
    assert parsed == [expected, expected, expected]
    try:
        extract_json("完全没有 JSON")
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("无 JSON 文本应抛 JSONDecodeError")
    _pass(qid, f"三种输入均解析为 {parsed[0]!r}，无 JSON 输入明确失败")


def a2() -> None:
    qid = "A2"
    schema = SkillExtraction.model_json_schema()
    properties = schema["properties"]
    assert set(properties) == {"name", "skills", "years", "summary"}
    assert properties["years"]["minimum"] == 0
    assert properties["years"]["maximum"] == 40
    raw = '{"name":"小明","skills":["Python"],"years":3,"summary":"后端工程师"}'
    result = parse_structured(raw, SkillExtraction)
    assert isinstance(result, SkillExtraction)
    assert result.name == "小明" and result.years == 3 and result.skills == ["Python"]
    _pass(qid, f"Schema 有 {len(properties)} 个字段，解析对象 years={result.years}")


def a3() -> None:
    qid = "A3"
    raw = '{"name":"小明","skills":["Python"],"years":"三年","summary":"后端工程师"}'
    try:
        parse_structured(raw, SkillExtraction)
    except StructuredOutputError as exc:
        assert "字段校验失败" in str(exc) and "years" in str(exc)
        assert isinstance(exc.__cause__, ValidationError)
        cause_name = type(exc.__cause__).__name__
    else:
        raise AssertionError("非法 years 应抛 StructuredOutputError")
    _pass(qid, f"错误点名 years，异常链根因为 {cause_name}")


def a4() -> None:
    qid = "A4"

    async def scenario() -> tuple[SkillExtraction, FakeClient]:
        client = FakeClient(script=[
            {"role": "assistant", "content": '{"name":"小明","skills":[],"years":"三年","summary":"x"}'},
            {"role": "assistant", "content": '{"name":"小明","skills":["Python"],"years":3,"summary":"后端"}'},
        ])
        result = await structured(
            client,
            [{"role": "user", "content": "抽取"}],
            SkillExtraction,
            max_retry=1,
        )
        return result, client

    result, client = asyncio.run(scenario())
    assert result.years == 3
    assert len(client.calls) == 2
    assert "不符合要求" in client.calls[1]["messages"][-1]["content"]
    assert all(call["response_format"] == {"type": "json_object"} for call in client.calls)
    _pass(qid, f"第 {len(client.calls)} 次调用成功，第二次请求已带校验反馈")


def b1() -> None:
    qid = "B1"
    reply = "流式 OK"
    client = FakeClient(reply=reply)

    async def collect() -> list[str]:
        return [chunk async for chunk in client.stream([{"role": "user", "content": "开始"}])]

    chunks = asyncio.run(collect())
    assert "".join(chunks) == reply
    assert len(chunks) == len(reply)
    assert client.calls[-1]["stream"] is True
    _pass(qid, f"收到 {len(chunks)} 个增量，拼接结果长度={len(''.join(chunks))}")


def b2() -> None:
    qid = "B2"
    client = FakeClient(reply="完整流式答案")
    service = ChatService(client=client, settings=Settings(api_key="offline-test"), system_prompt="离线助手")

    async def collect() -> list[str]:
        return [chunk async for chunk in service.astream("问题")]

    chunks = asyncio.run(collect())
    full = "".join(chunks)
    turns = service.sessions.get("default").turns
    assert full == "完整流式答案"
    assert turns[-1] == {"role": "assistant", "content": full}
    assert turns[-2] == {"role": "user", "content": "问题"}
    _pass(qid, f"{len(chunks)} 个增量回灌为一条长度 {len(full)} 的 assistant 消息")


def b3() -> None:
    qid = "B3"
    service = ChatService(
        client=FakeClient(reply="流式"),
        settings=Settings(api_key="offline-test"),
        system_prompt="离线助手",
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post("/chat/stream", json={"message": "开始"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [block.removeprefix("data: ") for block in response.text.strip().split("\n\n")]
        assert events[-1] == "[DONE]"
        deltas = [json.loads(event)["delta"] for event in events[:-1]]
        assert "".join(deltas) == "流式"
    finally:
        client.close()
        app.dependency_overrides.clear()
    _pass(qid, f"SSE 返回 {len(events) - 1} 个 JSON 事件，并以 {events[-1]} 结束")


def c1() -> None:
    qid = "C1"
    base = Settings(api_key="offline-test")
    extract = base.for_profile("extract")
    creative = base.for_profile("creative")
    assert base.temperature == 0.7 and base.max_tokens == 1024
    assert extract is not base and creative is not base
    assert extract.temperature < creative.temperature
    assert extract.max_tokens < creative.max_tokens
    _pass(
        qid,
        f"extract={extract.temperature}/{extract.max_tokens}，creative={creative.temperature}/{creative.max_tokens}，原配置未变",
    )


def c2() -> None:
    qid = "C2"
    settings = Settings(
        api_key="offline-test-key",
        model="offline-model",
        temperature=0.2,
        top_p=0.9,
        max_tokens=321,
    )
    client = DeepSeekClient(settings)
    messages = [{"role": "user", "content": "只构造请求，不发送"}]
    response_format = {"type": "json_object"}
    tools = [{"type": "function", "function": {"name": "noop", "parameters": {"type": "object"}}}]
    try:
        payload = client.build_payload(
            messages,
            stream=True,
            response_format=response_format,
            tools=tools,
        )
        assert payload == {
            "model": "offline-model",
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 321,
            "response_format": response_format,
            "tools": tools,
        }
        headers = client.headers()
        assert "offline-test-key" not in str(headers)
        assert headers.get("authorization") == "***"
    finally:
        asyncio.run(client.aclose())
    _pass(qid, f"payload 含 {len(payload)} 个顶层字段，Authorization 已脱敏为 {headers.get('authorization')!r}")


def c3() -> None:
    qid = "C3"
    cases = [
        (Settings(api_key="offline-test", temperature=2.1), "temperature"),
        (Settings(api_key="offline-test", top_p=0), "top_p"),
        (Settings(api_key="offline-test", max_tokens=0), "max_tokens"),
    ]
    seen: list[str] = []
    for settings, field in cases:
        try:
            settings.validate()
        except LLMConfigError as exc:
            assert field in str(exc)
            seen.append(field)
        else:
            raise AssertionError(f"非法 {field} 应抛 LLMConfigError")
    assert Settings(api_key="offline-test").validate() is None
    _pass(qid, f"校验器拒绝 {len(seen)} 个非法参数：{', '.join(seen)}")


def main() -> None:
    for answer in (a1, a2, a3, a4, b1, b2, b3, c1, c2, c3):
        answer()


if __name__ == "__main__":
    main()
