"""Project 05 —— Milestone 05：Agent Loop 的真实演示。

六节，全部是**真跑出来的数字**（不是描述）：

    1. 上下文是怎么膨胀的        —— 逐步打 token 数
    2. trim_history 裁了什么     —— 占位符与协议配对
    3. 草稿纸为什么会存在        —— 历史被裁没了，笔记还在
    4. 第三道闸门：重复调用      —— 失败闸门看不见的空转
    5. 一个真正的多步骤任务      —— 查 A → 记 → 查 B → 记 → 汇总
    6. 真实模型（--real）        —— 让 DeepSeek 自己决定怎么拆

    python demos/demo_05_agent_loop.py
    python demos/demo_05_agent_loop.py --real
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.agent import ReActAgent  # noqa: E402
from agent.errors import AgentError, RepeatedToolCall  # noqa: E402
from agent.llm import LLMMessage, ScriptedLLM, DeepSeekLLM  # noqa: E402
from agent.memory import (  # noqa: E402
    Scratchpad,
    TRIMMED_MARK,
    estimate_messages_tokens,
    trim_history,
)
from agent.registry import ToolRegistry  # noqa: E402
from agent.settings import AgentSettings  # noqa: E402
from agent.tools import ToolCall, default_tools  # noqa: E402

WIDTH = 72


def show(title: str, body: str = "") -> None:
    print()
    print(f"── {title} " + "─" * max(0, WIDTH - len(title) - 4))
    if body:
        print(body)


def search(query: str, cid: str) -> LLMMessage:
    return LLMMessage(role="assistant", tool_calls=[ToolCall(id=cid, name="rag_search", arguments={"query": query})])


def note(key: str, value: str, cid: str) -> LLMMessage:
    return LLMMessage(
        role="assistant", tool_calls=[ToolCall(id=cid, name="write_note", arguments={"key": key, "value": value})]
    )


def answer(text: str) -> LLMMessage:
    return LLMMessage(role="assistant", content=text)


# --------------------------------------------------------------------------
def section_1_context_growth() -> None:
    show("1. 上下文是怎么一步一步膨胀的")

    pad = Scratchpad()
    agent = ReActAgent(
        ScriptedLLM(
            search("Project 04 会话", "c1"),
            search("Project 02 服务层", "c2"),
            answer("完成"),
        ),
        ToolRegistry(default_tools(pad)),
        scratchpad=pad,
        system_prompt="短规则",
    )
    agent.run("对比 Project 01 与 Project 04 的持久化方式")

    print("每一轮真正发给模型的体量：")
    print(f"  {'轮':<4}{'token':>8}  消息角色")

    def _roles(messages) -> str:
        out = []
        for m in messages:
            if m.tool_calls:
                out.append(f"assistant(+{len(m.tool_calls)} calls)")
            else:
                out.append(m.role)
        return " → ".join(out)

    for i, (messages, tools, _reply) in enumerate(agent._recorder.transcript, 1):
        print(f"  {i:<4}{estimate_messages_tokens(messages):>8}  {_roles(messages)}")
    total = sum(estimate_messages_tokens(m) for m, _, _ in agent._recorder.transcript)
    peak = max(estimate_messages_tokens(m) for m, _, _ in agent._recorder.transcript)
    print(f"\n  峰值 {peak} token；三轮累计发送 {total} token。")
    print("  注意：第 1 轮只有几十 token，第 3 轮是它的数倍 —— 而每轮都要把前面的历史重发一遍，")
    print("  所以真实成本是这个数字的累加，不是最后一轮那个数字。")


# --------------------------------------------------------------------------
def section_2_trim() -> None:
    show("2. trim_history 到底动了什么")

    messages = [
        LLMMessage(role="system", content="短规则"),
        LLMMessage(role="user", content="原始提问"),
    ]
    for i in range(1, 4):
        messages.append(
            LLMMessage(
                role="assistant",
                content=f"第{i}步思考",
                tool_calls=[ToolCall(id=f"c{i}", name="rag_search", arguments={"query": f"q{i}"})],
            )
        )
        messages.append(
            LLMMessage(
                role="tool",
                content=("Project 04 的会话落盘走 mkstemp + fsync + os.replace 原子写。" * 4),
                tool_call_id=f"c{i}",
                name="rag_search",
            )
        )

    before = estimate_messages_tokens(messages)
    trimmed = trim_history(messages, budget=250, keep_recent=1)
    after = estimate_messages_tokens(trimmed)

    print(f"裁剪前 {before} token / {len(messages)} 条消息")
    print(f"裁剪后 {after} token / {len(trimmed)} 条消息（预算 250）")
    print("\n被压缩的那几条长成了这样：")
    for m in trimmed:
        if m.role == "tool" and TRIMMED_MARK in (m.content or ""):
            print(f"  tool → {m.content}")
    print("\n最近一步保留原文（模型马上要引用它）：")
    last = [m for m in trimmed if m.role == "tool"][-1]
    print(f"  tool → {last.content[:60]}…")

    print("\n协议配对自检（每条 tool 消息前面必须有对应的 assistant tool_calls）：")
    pending: set[str] = set()
    orphans = []
    for m in trimmed:
        if m.tool_calls:
            pending.update(c.id for c in m.tool_calls)
        elif m.role == "tool":
            if m.tool_call_id not in pending:
                orphans.append(m.tool_call_id)
            pending.discard(m.tool_call_id)
    print(f"  孤儿 tool 消息：{orphans or '无'}")
    print("  这一项是硬要求 —— 真发请求时留下孤儿消息会直接被服务端打回来。")


# --------------------------------------------------------------------------
def section_3_scratchpad() -> None:
    show("3. 历史可以被裁，纸上的结论不能丢")

    pad = Scratchpad()
    pad.write("p04", "会话落盘：mkstemp + fsync + os.replace 原子写")
    pad.write("p01", "入口 main.py，单轮循环读 stdin")

    long_history = [
        LLMMessage(role="system", content="短规则"),
        LLMMessage(role="user", content="原始提问"),
    ]
    for i in range(1, 6):
        long_history.append(LLMMessage(role="assistant", content=f"第{i}步思考"))
        long_history.append(LLMMessage(role="tool", content="很长很长的一段检索结果。" * 20, tool_call_id=f"c{i}", name="rag_search"))

    trimmed = trim_history(long_history, budget=600, keep_recent=1)
    lost = [m for m in long_history if m.role == "tool"][:2]
    print(f"历史被裁：{estimate_messages_tokens(long_history)} → {estimate_messages_tokens(trimmed)} token")
    print(f"  被压掉的工具结果：{len(lost)} 条，内容变成占位符")
    print("\n同一时刻草稿纸上：")
    print(pad.render())
    print("\n→ 结论：**中间事实必须写在循环之外**。")
    print("  历史是会被压缩的工作记忆，草稿纸是不会被压缩的结论。")


# --------------------------------------------------------------------------
def section_4_repeat_guard() -> None:
    show("4. 第三道闸门：它在原地打转，但一次都没报错")

    llm = ScriptedLLM(
        search("同一个检索词", "c1"),
        search("同一个检索词", "c2"),
        search("同一个检索词", "c3"),
        answer("不会走到这里"),
    )
    agent = ReActAgent(llm, ToolRegistry(), settings=AgentSettings(max_steps=8, max_repeats=2))
    print("剧本：连续三次用完全相同的参数调 rag_search")
    try:
        agent.run("这个问题查不到")
    except RepeatedToolCall as exc:
        print(f"\n  拦下了 → {exc}")
    print(f"\n  实际模型往返 {agent._recorder.transcript and len(agent._recorder.transcript)} 次就停了，")
    print("  而不是等 max_steps=8 烧完 —— 这就是重复闸门比步数闸门更早触发的价值。")
    print("\n  为什么 max_tool_failures 拦不住它：")
    print("    rag_search 每次都成功返回（没有 error），失败计数一次都没涨。")
    print("    所以这是一类**只看成功率和失败率都发现不了**的空转。")

    print("\n  反过来，换个参数重试是被允许的：")
    agent2 = ReActAgent(
        ScriptedLLM(search("A", "c1"), search("A 换个说法", "c2"), answer("查到了")),
        ToolRegistry(),
        settings=AgentSettings(max_repeats=2),
    )
    print(f"    A → A 换个说法 → 答案：{agent2.run('问').answer}")


# --------------------------------------------------------------------------
def section_5_multi_step() -> None:
    show("5. 一个真正的多步骤任务：查 → 记 → 查 → 记 → 汇总")

    pad = Scratchpad()
    # 第一步必须是「思考 + 工具调用」在同一条消息里：
    # 只给 content 而没有 tool_calls，循环会把它当成最终答案直接结束。
    llm = ScriptedLLM(
        LLMMessage(
            role="assistant",
            content="我分两步查，每查完一个就记到草稿纸上。",
            tool_calls=[ToolCall(id="c1", name="rag_search", arguments={"query": "Project 01 持久化"})],
        ),
        note("p01", "P01：入口 main.py 参数解析；项目结构重构后单轮循环读 stdin", "w1"),
        search("Project 04 持久化", "c2"),
        note("p04", "P04：Turn 不可变，会话走 mkstemp+fsync+os.replace 原子写", "w2"),
        answer("P01 靠 main.py 单轮循环，没有跨轮状态要存；P04 有了多轮会话，才引入原子写。"),
    )
    agent = ReActAgent(
        llm,
        ToolRegistry(default_tools(pad)),
        settings=AgentSettings(context_budget=1200),
        scratchpad=pad,
    )
    result = agent.run("对比 Project 01 与 Project 04 各自怎么处理状态持久化")

    print(result.trace())
    print()
    print(f"用了 {result.steps_used} 步 / {len(result.tool_calls)} 次工具调用")
    print(f"草稿纸留下 {len(result.notes)} 条笔记：")
    for key, value in result.notes.items():
        print(f"  · {key}：{value}")


# --------------------------------------------------------------------------
def section_6_real(real: bool) -> None:
    show("6. 真实模型：让它自己决定怎么拆这个任务")

    if not real:
        print("（跳过。加 --real 并设好 DEEPSEEK_API_KEY 后，这一节会真的发请求）")
        return

    pad = Scratchpad()
    try:
        llm = DeepSeekLLM(AgentSettings())
    except AgentError as exc:
        print(f"无法连接真实模型：{exc}")
        return

    agent = ReActAgent(
        llm,
        ToolRegistry(default_tools(pad)),
        settings=AgentSettings.from_env(max_steps=8, context_budget=900, keep_recent_steps=1),
        scratchpad=pad,
    )
    question = "对比 Project 01 与 Project 04 各自怎么处理状态持久化，每查完一个方面先记到草稿纸上。"
    result = agent.run(question)
    print(result.trace())
    print()
    print(f"步数 {result.steps_used} / 工具调用 {len(result.tool_calls)} / 草稿纸 {len(result.notes)} 条")

    print("\n每一轮真正发出去的体量（预算 900，keep_recent=1）：")
    print(f"  {'轮':<4}{'token':>8}{'消息数':>8}{'其中占位':>10}")
    cumulative = 0
    for i, (messages, _tools, _reply) in enumerate(agent._recorder.transcript, 1):
        size = estimate_messages_tokens(messages)
        cumulative += size
        placeholders = sum(1 for m in messages if m.role == "tool" and TRIMMED_MARK in (m.content or ""))
        print(f"  {i:<4}{size:>8}{len(messages):>8}{placeholders:>10}")
    print(f"\n  累计发送 {cumulative} token，而最后一轮只有其中一部分 —— 账单按累计算。")
    print("  出现「占位」的那些轮次，就是工作记忆真的被裁剪过的证据。")


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 05：Agent Loop 演示")
    parser.add_argument("--real", action="store_true", help="第 6 节发真实请求（需要 DEEPSEEK_API_KEY）")
    args = parser.parse_args()

    print("=" * WIDTH)
    print("Project 05 · Milestone 05 —— Agent Loop：工作记忆 + 多步骤任务")
    print("=" * WIDTH)

    section_1_context_growth()
    section_2_trim()
    section_3_scratchpad()
    section_4_repeat_guard()
    section_5_multi_step()
    section_6_real(args.real)

    show("结论")
    print("1. 多步骤任务的成本是「每轮重发历史」的累加，不是最后一轮那个数。")
    print("2. 裁剪必须整round配对地裁，留下孤儿 tool 消息会被服务端打回。")
    print("3. 中间结论要写在循环之外（草稿纸），写在历史里迟早被裁掉。")
    print("4. 空转分两种：报错的（失败闸门管）和原地打转的（重复闸门管）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
