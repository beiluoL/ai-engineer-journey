"""Milestone 04 实验：流式输出。

用 FakeClient 走真实的 ChatService.astream()，验证三件事：
1. 流式拿到的是「逐块增量」，累加起来必须严格等于一次性答案（正确性的底线）；
2. 分块发「累积前缀」会造成前端重复显示（反例，代码里显式构造出来看）；
3. 一次性与流式内容一致 —— 流式不改变答案，只改变到达方式。

关于 TTFT：FakeClient 没有网络延迟，这里量出来的是 0ms，
**不能拿它当真实首字延迟**。真实链路的 TTFT 见 Project 04 第 13 章
（真实 DeepSeek：TTFT 361ms vs 整段 1741ms）。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from assistant.client import FakeClient  # noqa: E402
from assistant.service import ChatService  # noqa: E402
from assistant.settings import Settings  # noqa: E402

QUESTION = "用三句话解释 RAG 为什么能减少幻觉。"
REPLY = ("因为答案有了出处。模型不再凭记忆编，而是先读你给的资料再回答。"
         "资料里没有的它就该说不知道。这样幻觉从「随机编」变成「可控的拒答」。")


def make_service() -> ChatService:
    return ChatService(client=FakeClient(reply=REPLY),
                       settings=Settings(api_key="test-key"),
                       system_prompt="你是一个简洁的中文 AI 助手。")


async def main() -> None:
    print("===== 1. 一次性 ask() =====")
    svc = make_service()
    once = await svc.ask(QUESTION)
    print(f"  {len(once)} 个字符：{once[:40]}...")

    print("\n===== 2. 流式 astream()：逐块到达 =====")
    svc = make_service()
    chunks: list[str] = []
    async for chunk in svc.astream(QUESTION):
        chunks.append(chunk)
        if len(chunks) <= 6:
            print(f"  第 {len(chunks)} 块: {chunk!r}")
    print(f"  ... 共 {len(chunks)} 块（FakeClient 按字符切，真实模型按 token 切）")

    print("\n===== 3. 底线：逐块增量累加 == 一次性答案 =====")
    joined = "".join(chunks)
    print(f"  累加长度 {len(joined)} ／ 一次性长度 {len(once)}")
    print(f"  完全一致：{joined == once}")
    assert joined == once, "流式拼接与一次性结果不一致"
    print("  → 这条断言应该进 CI：只要有一处发了累积前缀，这里立刻红")

    print("\n===== 4. 反例：如果分块发的是「累积前缀」会怎样 =====")
    wrong: list[str] = []
    buf = ""
    for ch in REPLY[:12]:        # 模拟一个写错的流式实现
        buf += ch
        wrong.append(buf)        # ← 每块发的都是从开头到当前的累积内容
    print("  错误实现的前 3 块:", [w[:6] for w in wrong[:3]])
    print("  前端按追加消费得到:", repr("".join(wrong)))
    print("  正确结果应为      :", repr(REPLY[:12]))
    print("  → 同一段话被重复显示；块数越多越离谱")
    print("  修法：用游标只 yield 新增的那一段")

    print("\n===== 5. 流式不改变答案，只改变到达方式 =====")
    svc = make_service()
    again = "".join([c async for c in svc.astream(QUESTION)])
    print(f"  再跑一次流式，与一次性一致：{again == once}")
    print("  → 想改答案质量要动 prompt / 参数；流式只影响等待感")


if __name__ == "__main__":
    asyncio.run(main())
