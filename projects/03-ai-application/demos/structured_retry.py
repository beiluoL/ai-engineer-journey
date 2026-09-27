"""Milestone 03 实验：结构化输出。

看四件事：
1. 模型常见的三种「不规范」输出，extract_json 分别怎么抠出 JSON；
2. 完全不是 JSON 时报什么错；
3. 字段类型不对时报什么错（而且错误信息要能回灌给模型重试）；
4. 真跑一次 ask_structured：第一次坏、第二次好，重试成功后拿到对象。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pydantic import BaseModel, Field  # noqa: E402

from assistant.client import FakeClient  # noqa: E402
from assistant.errors import StructuredOutputError  # noqa: E402
from assistant.schema import extract_json, parse_structured  # noqa: E402
from assistant.service import ChatService  # noqa: E402
from assistant.settings import Settings  # noqa: E402


class SkillSet(BaseModel):
    """想让模型输出的结构。"""

    skills: list[str] = Field(default_factory=list)
    years: int = Field(ge=0, le=50)


CASES = [
    ("裸 JSON", '{"skills": ["Java"], "years": 5}'),
    ("```json 围栏", '```json\n{"skills": ["Java", "Spring Boot"], "years": 5}\n```'),
    ("前后带解释", '好的，结果如下：{"skills": ["Java"], "years": 5}希望对你有帮助。'),
]


def main() -> None:
    print("===== 1. 三种常见输出，都能抠出 JSON =====")
    for name, raw in CASES:
        try:
            print(f"  {name:<12} → {extract_json(raw)}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:<12} → 失败：{type(exc).__name__}: {exc}")

    print("\n===== 2. 完全不是 JSON =====")
    for raw in ("抱歉，我做不到。", "技能：Java、Spring Boot"):
        try:
            parse_structured(raw, SkillSet)
        except StructuredOutputError as exc:
            print(f"  输入 {raw!r}")
            print(f"  → StructuredOutputError: {exc}")

    print("\n===== 3. 是 JSON 但字段不对 =====")
    for raw in ('{"skills": ["Java"], "years": 999}', '{"skills": ["Java"]}',
                '{"skills": "Java", "years": 5}'):
        try:
            parse_structured(raw, SkillSet)
            print(f"  {raw} → 通过")
        except StructuredOutputError as exc:
            print(f"  {raw}")
            print(f"  → StructuredOutputError: {exc}")
    print("  → 错误信息要带上「哪错了」，才能回灌给模型让它改")

    print("\n===== 4. 真跑一次：第一次坏、重试后成功 =====")
    client = FakeClient(script=[
        {"role": "assistant", "content": "抱歉，我没看懂你的要求。"},
        {"role": "assistant", "content": '{"skills": ["Java", "Spring Boot"], "years": 5}'},
    ])
    service = ChatService(client=client, settings=Settings(api_key="test-key"),
                          system_prompt="只输出 JSON。")
    result = asyncio.run(service.ask_structured(
        "从这句话里抽技能：我会 Java 和 Spring Boot，干了 5 年。", SkillSet))
    print("  模型被调用了几次 :", len(client.calls))
    print("  最终结果         :", result)
    print(f"  类型             : {type(result).__name__}（已经是对象，不是字符串）")
    print("  → max_retry=1 意味着最多重试一次；重试次数要设上限，否则坏模型会无限循环")

    print("\n===== 5. 一直坏下去会怎样 =====")
    bad = FakeClient(script=[
        {"role": "assistant", "content": "我不是 JSON"},
        {"role": "assistant", "content": "我还是不是 JSON"},
    ])
    svc2 = ChatService(client=bad, settings=Settings(api_key="test-key"))
    try:
        asyncio.run(svc2.ask_structured("抽技能：Java 5 年", SkillSet, max_retry=1))
    except StructuredOutputError as exc:
        print("  StructuredOutputError:", exc)
    print("  → 失败必须是显式异常，不能返回 None 让调用方拿到空对象")


if __name__ == "__main__":
    main()
