"""Chapter 05 演示：多轮记忆与「超预算裁剪」的前后对比。

跑法（在 `projects/03-ai-application` 目录下）：

    PYTHONPATH=src python3 demos/memory_history.py

全程离线：用 `FakeClient` 当模型（不联网、不需要 API Key），
但 messages 的累积、裁剪、会话隔离全部走 `src/assistant/` 的真实实现。
"""

from __future__ import annotations

import asyncio
import logging

from assistant.client import FakeClient
from assistant.memory import Conversation
from assistant.service import ChatService
from assistant.settings import Settings
from assistant.tokens import Budget, estimate_messages_tokens


class WarningCollector(logging.Handler):
    """收集 memory.py 裁剪时打出的 WARNING（用来给出真实的触发次数）。"""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


collector = WarningCollector()
logging.getLogger("assistant.memory").addHandler(collector)

# 演示用的「长」用户输入与模型回复（内容够长，几轮后就能触发裁剪）
USER_TEXT = (
    "记一下背景：我用 FastAPI 写了个 /chat 接口，调用 client.chat 的时候报错说缺少参数 messages，"
    "但我明明只传了 text 这一个参数，本地 pytest 又是全绿的，帮我看看为什么。"
)
BOT_REPLY = (
    "先记下这个背景：FastAPI 接口、client.chat 报缺少 messages、单测全绿。"
    "结论方向是接口层和客户端层的函数签名不一致——单测直接调客户端，所以覆盖不到接口层。"
    "把接口的入参改成 messages 列表，或者让客户端接受 text 并自己拼 messages。"
)


async def main() -> None:
    settings = Settings(
        api_key="local-fake-key",
        system_prompt="你是一个简洁、耐心的中文 AI 助手。",
    )

    # 故意把窗口调小，让裁剪在几轮内就能被观察到
    budget = Budget(context_window=1600, reserved_output=128, history_ratio=0.5)
    client = FakeClient(reply=BOT_REPLY)
    service = ChatService(client=client, settings=settings, budget=budget)

    print("=== 1. 预算配置 ===")
    print(f"  context_window  = {budget.context_window}（输入与输出共享）")
    print(f"  reserved_output = {budget.reserved_output}（预留给本次回答）")
    print(f"  history_budget  = {budget.history_budget}（历史可用的上限）")
    print(f"  软阈值：超过 {budget.history_budget} → trim（裁剪）")
    print(f"  硬阈值：超过 {budget.context_window - budget.reserved_output} → overflow（报错）")

    print("\n=== 2. 逐轮提问：发送前 vs 实际发出（FakeClient 离线）===")
    rounds = 8
    for i in range(1, rounds + 1):
        conv = service.sessions.get("default")
        before, before_turns = conv.tokens(), len(conv.turns)   # 发送前（裁剪前）
        verdict = budget.check(before)
        await service.ask(USER_TEXT, session_id="default")
        sent = client.calls[-1]["messages"]           # FakeClient 真正收到的 messages
        print(
            f"  第 {i:>2} 轮：发送前 {before_turns:>2} 条 / {before:>4} token"
            f" → 实际发送 {len(sent):>2} 条 / {estimate_messages_tokens(sent):>4} token"
            f"  判定 {verdict}",
            flush=True,
        )
    print(f"  → memory.py 共打了 {len(collector.messages)} 次裁剪 WARNING，例如：")
    print(f"    {collector.messages[0]}")

    print("\n=== 3. 最后一轮的裁剪前 / 后对比 ===")
    last_sent = client.calls[-1]["messages"]
    kept = len(last_sent) - 2                     # 减去 system 与本轮 user
    kept_tokens = estimate_messages_tokens(last_sent)
    print(f"  裁剪前：history {before_turns} 条 / 估算 {before} token（判定 {verdict}）")
    print(f"  裁剪后：history {kept} 条 / 估算 {kept_tokens} token（含 system 与本轮输入）")
    print(f"  丢弃   ：{before_turns - kept} 条 / 约 {before - kept_tokens} token")
    print(f"  预算上限 history_budget = {budget.history_budget} token")
    print(f"  system 仍排在首位   ：{last_sent[0]['role'] == 'system'}")
    print(f"  最后一轮 user 仍保留：{last_sent[-1]['role'] == 'user'}")

    # ---- 4. 直接观察 trim_to_budget 的返回值 ----
    print("\n=== 4. 单独调用 trim_to_budget()（超长历史，一次裁到位）===")
    long_conv = Conversation(system_prompt=settings.system_prompt)
    for i in range(1, 13):
        long_conv.add_user(f"第 {i} 轮问题：{USER_TEXT}")
        long_conv.add_assistant(BOT_REPLY)
    raw_turns, raw_tokens = len(long_conv.turns), long_conv.tokens()
    dropped = long_conv.trim_to_budget(budget.history_budget)
    print(f"  裁剪前：{raw_turns} 条 / {raw_tokens} token")
    print(f"  丢弃   ：{dropped} 条")
    print(f"  裁剪后：{len(long_conv.turns)} 条 / {long_conv.tokens()} token")
    first_role = long_conv.turns[0]["role"]
    print(f"  裁剪后首条 role = {first_role}、末条 role = {long_conv.turns[-1]['role']}")
    if first_role == "user":
        print("  首条是 user：这次刚好落在「轮」的边界上")
    else:
        print(f"  首条是 {first_role}：说明裁剪落在了轮中间（Chapter 02 坑 5）")

    # ---- 5. 会话隔离：两个 session 交替提问不会串味 ----
    print("\n=== 5. 会话隔离（SessionStore）===")
    await service.ask("我是 A 用户，我在学 Rust。", session_id="user-A")
    await service.ask("我是 B 用户，我在学 Go。", session_id="user-B")
    a = service.sessions.get("user-A")
    b = service.sessions.get("user-B")
    print(f"  会话 user-A：{len(a.turns)} 条，本轮输入 = {a.turns[-2]['content']}")
    print(f"  会话 user-B：{len(b.turns)} 条，本轮输入 = {b.turns[-2]['content']}")
    print(f"  两个会话是不同对象：{a is not b}")
    print(f"  A 的历史里没有 B：{'B 用户' not in str(a.turns)}")


if __name__ == "__main__":
    asyncio.run(main())
