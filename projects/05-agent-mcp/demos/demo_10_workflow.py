"""Project 05 —— Milestone 10：Agent Workflow 的真实演示。

核心问题是这一个：

    同一个多步骤任务，用「一个大 Agent 从头跑到尾」和「拆给多个 Worker」，
    上下文开销差多少？

这一章把它**量出来**，而不是停留在口头。

    1. 一个大 Agent 的上下文是怎么长的
    2. 同样的活拆给 3 个 Worker
    3. 两者对比（累计发送 token）
    4. 上下文隔离的证据 —— 汇总者看到什么
    5. 失败传播 —— 上游炸了下游怎么办
    6. 真实模型（--real）

    python demos/demo_10_workflow.py
    python demos/demo_10_workflow.py --real
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.agent import ReActAgent  # noqa: E402
from agent.llm import LLMMessage, ScriptedLLM  # noqa: E402
from agent.memory import Scratchpad, estimate_messages_tokens  # noqa: E402
from agent.plan import Plan  # noqa: E402
from agent.registry import ToolRegistry  # noqa: E402
from agent.settings import AgentSettings  # noqa: E402
from agent.tools import ToolCall, default_tools  # noqa: E402
from agent.workflow import Workflow  # noqa: E402

WIDTH = 72

GOAL = "对比 Project 01 与 Project 04 各自怎么处理状态持久化"
TASKS = (
    '[{"id":"t1","title":"查 Project 01 怎么落盘"},'
    '{"id":"t2","title":"查 Project 04 怎么落盘"},'
    '{"id":"t3","title":"汇总两者差异","depends_on":["t1","t2"]}]'
)
ANSWER_T1 = "P01 是单轮问答 CLI，循环读 stdin，不做跨轮状态持久化（无状态）。"
ANSWER_T2 = "P04 的会话用 mkstemp+fsync+os.replace 原子写落盘，Turn 不可变。"
ANSWER_SUMMARY = "P01 无状态、不落盘；P04 有状态，会话用原子写落盘且 Turn 不可变。"


def show(title: str) -> None:
    print()
    print("─" * WIDTH)
    print(f"  {title}")
    print("─" * WIDTH)


def search(query: str, call_id: str) -> LLMMessage:
    return LLMMessage(
        role="assistant",
        tool_calls=[ToolCall(id=call_id, name="rag_search", arguments={"query": query})],
    )


def answer(text: str) -> LLMMessage:
    return LLMMessage(role="assistant", content=text)


def cumulative_tokens(recorder) -> int:
    """累计发送 token —— 每轮都要把前面的历史重发一遍，所以成本按累计算。"""
    return sum(estimate_messages_tokens(msgs) for msgs, _t, _r in recorder.transcript)


# ────────────────────────────────────────────────────────────────────── 1
def section_1() -> int:
    show("1. 一个大 Agent：上下文是怎么一路膨胀的")
    pad = Scratchpad()
    agent = ReActAgent(
        ScriptedLLM(
            search("Project 01 落盘", "c1"),
            search("Project 04 落盘", "c2"),
            answer(ANSWER_SUMMARY),
        ),
        ToolRegistry(default_tools(pad)),
        settings=AgentSettings(max_steps=6, context_budget=100000),
        scratchpad=pad,
        system_prompt="你是研究助手。用工具查证后再回答。",
    )
    result = agent.run(GOAL + "，每查完一个方面先记到草稿纸上")
    print("  每一轮实际发给模型的体量：")
    total = 0
    for i, (msgs, _t, _r) in enumerate(agent._recorder.transcript, 1):
        n = estimate_messages_tokens(msgs)
        total += n
        print(f"    第 {i} 轮  {n:>5} token   messages={len(msgs)}   累计={total}")
    print()
    print(f"  答案：{result.answer[:60]}…")
    print(f"  **累计发送 {total} token**")
    print()
    print("  问题在第 3 轮：它要输出「汇总」这个只需要两句结论的动作，")
    print("  却不得不把前面两次检索的**原文**一起带在上下文里。")
    return total


# ────────────────────────────────────────────────────────────────────── 2
def section_2() -> tuple[int, int]:
    show("2. 同样的活拆给 3 个 Worker")
    pad = Scratchpad()
    plan = Plan()

    def responder(messages, tools=None):
        text = ""
        for m in messages:
            if m.role == "user":
                text = m.content or ""
        if not any(m.role == "tool" for m in messages):
            return search("落盘", "c1")
        if "（t1）" in text:
            return answer(ANSWER_T1)
        if "（t2）" in text:
            return answer(ANSWER_T2)
        return answer(ANSWER_SUMMARY)

    from agent.llm import FakeLLM

    seen: list[int] = []

    def counting(messages, tools=None):
        seen.append(estimate_messages_tokens(messages))
        return responder(messages, tools)

    wf = Workflow(
        FakeLLM(responder=counting),
        ToolRegistry(default_tools(pad, plan)),
        settings=AgentSettings(max_steps=4, context_budget=100000),
        scratchpad=pad,
        plan=plan,
        verbose=True,
    )
    result = wf.run(GOAL, tasks=TASKS)
    print()
    print("  每个 Worker 各自发给了模型什么：")
    for i, n in enumerate(seen, 1):
        print(f"    第 {i} 次请求  {n:>5} token")
    total = sum(seen)
    print()
    print(result.render())
    print()
    print(f"  **累计发送 {total} token**，共 {len(seen)} 次请求")
    return total, len(seen)


# ────────────────────────────────────────────────────────────────────── 3
def _single_cost(n: int) -> tuple[int, int]:
    """一个大 Agent 做 n 次检索后汇总，返回 (累计 token, 单轮最大 token)。"""
    pad = Scratchpad()
    script = [search(f"检索第 {i} 个方面", f"c{i}") for i in range(1, n + 1)]
    script.append(answer("汇总结论：" + "。" * 40))
    agent = ReActAgent(
        ScriptedLLM(*script),
        ToolRegistry(default_tools(pad)),
        settings=AgentSettings(max_steps=n + 2, context_budget=100000),
        scratchpad=pad,
        system_prompt="你是研究助手。用工具查证后再回答。",
    )
    agent.run(GOAL)
    sizes = [estimate_messages_tokens(msgs) for msgs, _t, _r in agent._recorder.transcript]
    return sum(sizes), max(sizes)


def _workflow_cost(n: int) -> tuple[int, int]:
    """n 个查询子任务 + 1 个汇总，返回 (累计 token, 单轮最大 token)。"""
    from agent.llm import FakeLLM

    pad = Scratchpad()
    plan = Plan()
    tasks = [{"id": f"t{i}", "title": f"查第 {i} 个方面"} for i in range(1, n + 1)]
    tasks.append({"id": "tsum", "title": "汇总", "depends_on": [t["id"] for t in tasks]})
    import json as _json

    seen: list[int] = []

    def responder(messages, tools=None):
        seen.append(estimate_messages_tokens(messages))
        text = ""
        for m in messages:
            if m.role == "user":
                text = m.content or ""
        if "请据此给出一段完整的回答" in text:
            return answer("汇总结论")
        if not any(m.role == "tool" for m in messages):
            return search("落盘", "c1")
        return answer("这一方面的结论。")

    wf = Workflow(
        FakeLLM(responder=responder),
        ToolRegistry(default_tools(pad, plan)),
        settings=AgentSettings(max_steps=4, context_budget=100000),
        scratchpad=pad,
        plan=plan,
    )
    wf.run(GOAL, tasks=_json.dumps(tasks, ensure_ascii=False))
    return sum(seen), max(seen)


def section_3(single: int, workflow_total: int, requests: int) -> None:
    show("3. 两者对比")
    print(f"  同一个 3 子任务：一个大 Agent {single} token vs 三个 Worker {workflow_total} token")
    if workflow_total < single:
        print(f"  拆开省下 {single - workflow_total} token（{(single - workflow_total) / single * 100:.0f}%）")
    else:
        print(f"  拆开**多花** {workflow_total - single} token。")
    print()
    print("  这个结果值得认真对待：**任务这么短的时候，拆开是亏的。**")
    print("  每个 Worker 都要重新带一遍 system 提示和自己的提问，这笔固定开销")
    print("  在只有 2-3 步时压过了省下的历史。所以真正该问的是：什么时候拆才划算？")
    print()

    show("3b. 规模扫描：什么时候拆才划算")
    print(f"  {'子任务数':>8}  {'单 Agent 累计':>14}  {'单轮最大':>10}  {'Workflow 累计':>14}  {'单轮最大':>10}")
    crossover = None
    for n in (2, 3, 5, 8):
        s_total, s_max = _single_cost(n)
        w_total, w_max = _workflow_cost(n)
        flag = ""
        if w_total < s_total and crossover is None:
            crossover = n
            flag = "  ← 拆开开始划算"
        elif w_max < s_max:
            flag = f"  单轮峰值低 {(s_max - w_max) / s_max * 100:.0f}%"
        print(f"  {n:>8}  {s_total:>14}  {s_max:>10}  {w_total:>14}  {w_max:>10}{flag}")
    print()
    if crossover:
        print(f"  交叉点大约在 {crossover} 个子任务 —— 超过这个规模，拆开才真的省钱。")
    else:
        print("  在这个规模区间内，拆开的总量还没追平，但**单轮峰值**一直更低 ——")
        print("  峰值低意味着不容易撞上下文窗口上限，这是另一个维度的收益。")
    print()
    print("  单 Agent 的第 N 轮要带着前 N-1 轮的原文，体量随步数**线性增长**；")
    print("  Worker 的每个请求只带自己的那一点，体量**基本恒定**。")
    print()
    print("  拆分的收益不是凭空来的，它来自两件事：")
    print("    ① 每个 Worker 的请求里没有别的 Worker 的检索原文（上下文隔离）")
    print("    ② 传递的是**结论**而不是原文")
    print()
    print("  代价也要说清楚：")
    print("    · Worker 之间不能直接对话，只能通过草稿纸 / Plan 传结论")
    print("    · 子任务拆得太碎，光是启动上下文就比省下的还多")
    print("  所以 PLANNER_PROMPT 里写的是「3 到 6 个子任务为宜」")


# ────────────────────────────────────────────────────────────────────── 4
def section_4() -> None:
    show("4. 上下文隔离的证据：汇总者到底看到了什么")
    pad = Scratchpad()
    plan = Plan()
    captured: list[str] = []

    def responder(messages, tools=None):
        text = ""
        for m in messages:
            if m.role == "user":
                text = m.content or ""
        if "请据此给出一段完整的回答" in text:
            captured.append(text)
            return answer(ANSWER_SUMMARY)
        if not any(m.role == "tool" for m in messages):
            return search("落盘", "c1")
        if "（t1）" in text:
            return answer(ANSWER_T1)
        return answer(ANSWER_T2)

    from agent.llm import FakeLLM

    wf = Workflow(
        FakeLLM(responder=responder),
        ToolRegistry(default_tools(pad, plan)),
        settings=AgentSettings(max_steps=4),
        scratchpad=pad,
        plan=plan,
    )
    wf.run(GOAL, tasks=TASKS)
    prompt = captured[0] if captured else ""
    print("  汇总者收到的提问（原文）：")
    for line in prompt.splitlines():
        print(f"    {line}")
    print()
    print("  逐条核对：")
    print(f"    ✓ 有上游结论      ：{'原子写' in prompt}")
    print(f"    ✗ 有检索原文      ：{'（p04-session）' in prompt}")
    print("  它只拿到了两句结论，没有拿到任何一次检索的原文。")


# ────────────────────────────────────────────────────────────────────── 5
def section_5() -> None:
    show("5. 失败传播：上游炸了下游怎么办")
    pad = Scratchpad()
    plan = Plan()

    def responder(messages, tools=None):
        text = ""
        for m in messages:
            if m.role == "user":
                text = m.content or ""
        if "（t1）" in text:
            raise RuntimeError("检索服务不可用")
        if "请据此给出一段完整的回答" in text:
            return answer("只能基于已有结论汇总")
        if not any(m.role == "tool" for m in messages):
            return search("落盘", "c1")
        return answer(ANSWER_T2)

    from agent.llm import FakeLLM

    wf = Workflow(
        FakeLLM(responder=responder),
        ToolRegistry(default_tools(pad, plan)),
        settings=AgentSettings(max_steps=4),
        scratchpad=pad,
        plan=plan,
    )
    result = wf.run(GOAL, tasks=TASKS)
    print(result.render())
    print()
    print("  t1 失败 → t3（依赖它）被自动跳过，t2 不受影响。")
    print("  执行是**动态**的：每轮重新取 ready()，而不是照着开局那份批次派完 ——")
    print("  否则 t1 已经失败了，t3 照样会被派出去（这个 bug 真踩过）。")


# ────────────────────────────────────────────────────────────────────── 6
def section_6() -> None:
    show("6. 真实模型（--real）")
    from agent.llm import DeepSeekLLM
    from agent.mcp.client import mcp_tools, spawn_default_server
    from agent.tools import ReadNotesTool, WriteNoteTool

    pad = Scratchpad()
    plan = Plan()
    client = spawn_default_server()
    client.start()
    try:
        client.initialize()
        # 检索走 MCP 子进程，草稿纸留在本地 —— 它是 Agent 自己的状态
        wf = Workflow(
            DeepSeekLLM(AgentSettings()),
            ToolRegistry(list(mcp_tools(client)) + [WriteNoteTool(pad), ReadNotesTool(pad)]),
            settings=AgentSettings.from_env(max_steps=6),
            scratchpad=pad,
            plan=plan,
            verbose=True,
        )
        result = wf.run(GOAL, tasks=TASKS)
        print()
        print(result.render())
        print()
        print(f"  子任务数 {len(result.workers)} / 完成 {sum(1 for w in result.workers if w['status'] == 'done')}")
        print("  注意：这些 Worker 用的工具全部来自 **MCP 子进程**，")
        print("  主进程里没有这些工具的实现 —— 09 的成果在这里接上了。")
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 10 Workflow 演示")
    parser.add_argument("--real", action="store_true", help="调真实 DeepSeek + MCP 工具")
    args = parser.parse_args()

    print("=" * WIDTH)
    print("  Project 05 · Milestone 10 —— Agent Workflow：把计划派给多个 Worker")
    print("=" * WIDTH)

    single = section_1()
    workflow_total, requests = section_2()
    section_3(single, workflow_total, requests)
    section_4()
    section_5()
    if args.real:
        section_6()
    else:
        show("6. 真实模型（跳过）")
        print("  加 --real 会用真实 DeepSeek + MCP 子进程跑一遍")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
