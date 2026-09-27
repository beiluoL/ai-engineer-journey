"""Milestone 01 实验：Prompt 模板。

看四件事：
1. 模板渲染后到底长什么样（变量替换发生在发送之前）；
2. 缺变量 / 拼错变量名会直接报错，而不是静默渲染出半句话；
3. 换一句 system prompt，发出去的 messages 第一条就变了；
4. 模板里的字数限制对 token 的影响。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from assistant.client import FakeClient  # noqa: E402
from assistant.prompts import DEFAULT_SYSTEM, PromptTemplate  # noqa: E402
from assistant.service import ChatService  # noqa: E402
from assistant.settings import Settings  # noqa: E402
from assistant.tokens import estimate_messages_tokens  # noqa: E402

QUESTION = "用一句话解释什么是 RAG。"


def main() -> None:
    print("===== 1. 模板本身 vs 渲染结果 =====")
    print("  模板 :", repr(DEFAULT_SYSTEM.template))
    print("  必填变量 :", DEFAULT_SYSTEM.variables())
    print("  渲染后 :")
    for line in DEFAULT_SYSTEM.render(max_sentences=3).splitlines():
        print("   ", line)

    print("\n===== 2. 缺变量：直接报错，不静默渲染 =====")
    try:
        DEFAULT_SYSTEM.render()
    except ValueError as exc:
        print("  ValueError:", exc)

    print("\n===== 3. 变量名拼错：也报错 =====")
    try:
        DEFAULT_SYSTEM.render(max_sentences=3, max_sentense=3)
    except ValueError as exc:
        print("  ValueError:", exc)
    print("  → 拼错不报的话，模型会看到一句没渲染的 {max_sentences}，答案就废了")

    print("\n===== 4. 换 system prompt，发出去的第一条就变了 =====")
    strict = PromptTemplate(
        name="strict",
        template="你是严谨的技术审稿人。回答不超过 {max_sentences} 句，必须给结论。",
        required=("max_sentences",),
    )
    for tpl in (DEFAULT_SYSTEM, strict):
        service = ChatService(client=FakeClient(reply="RAG 就是先检索再生成。"),
                              settings=Settings(api_key="test-key"),
                              system_prompt=tpl.render(max_sentences=3))
        import asyncio
        asyncio.run(service.ask(QUESTION))
        sent = service.client.calls[-1]["messages"]
        print(f"  [{tpl.name}] system 首条: {sent[0]['content'][:40]}...")
        print(f"         messages 共 {len(sent)} 条，估算 {estimate_messages_tokens(sent)} token")

    print("\n===== 5. system 的长短直接进 token 预算 =====")
    base = [{"role": "user", "content": QUESTION}]
    variants = {
        "空 system": "",
        "默认 system": DEFAULT_SYSTEM.render(max_sentences=3),
        "长 system（加规则）": (DEFAULT_SYSTEM.render(max_sentences=3)
                          + "\n不确定的地方必须说「资料里没有」，不要推测。"
                            "\n回答里引用到的资料要标 [编号]。"),
    }
    for name, text in variants.items():
        msgs = ([{"role": "system", "content": text}] if text else []) + base
        print(f"  {name:<18} system {len(text):>3} 字符 → 整包估算 "
              f"{estimate_messages_tokens(msgs):>3} token")
    print("  → system 是每条请求都带的固定开销；轮数一多，它就是最先该精简的地方")


if __name__ == "__main__":
    main()
