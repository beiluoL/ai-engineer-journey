"""Project 05 —— Milestone 06：多步骤任务与显式计划的真实演示。

七节，全部是**真跑出来的数字**（不是描述）：

    1. 一份计划长什么样        —— SubTask 的四要素
    2. 依赖决定能并行多少      —— 菱形依赖的分批结果
    3. 成环会被拦下            —— 模型写出 A→B→A 时
    4. 上游失败会跳过下游      —— 传递闭包，不是只跳一层
    5. 计划工具                —— 模型自己拆、自己推进
    6. 离线跑一次多步骤任务    —— 带计划的完整轨迹
    7. 真实模型（--real）      —— 让 DeepSeek 自己决定拆几步

    python demos/demo_06_multi_step.py
    python demos/demo_06_multi_step.py --real
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.agent import ReActAgent  # noqa: E402
from agent.llm import LLMMessage, ScriptedLLM  # noqa: E402
from agent.plan import (  # noqa: E402
    DONE,
    FAILED,
    CircularDependencyError,
    Plan,
)
from agent.registry import ToolRegistry  # noqa: E402
from agent.settings import AgentSettings  # noqa: E402
from agent.tools import ToolCall, default_tools, plan_tools  # noqa: E402

WIDTH = 72


def show(title: str, body: str = "") -> None:
    print()
    print("─" * WIDTH)
    print(f"  {title}")
    print("─" * WIDTH)
    if body:
        print(body)


def diamond() -> Plan:
    """菱形依赖：t1 → (t2 ∥ t3) → t4。"""
    p = Plan(goal="对比两个项目的持久化方式")
    p.add("t1", "确定要对比哪两个项目")
    p.add("t2", "查 Project 01 怎么落盘", depends_on=("t1",))
    p.add("t3", "查 Project 04 怎么落盘", depends_on=("t1",))
    p.add("t4", "汇总两者的差异", depends_on=("t2", "t3"))
    return p


# ────────────────────────────────────────────────────────────────────── 1
def section_1() -> None:
    show("1. 一份计划长什么样：SubTask 的四要素")
    p = diamond()
    print(p.render())
    print()
    print("每个 SubTask 只有四样东西，但缺一不可：")
    print("  id         —— 依赖要引用它，必须唯一")
    print("  title      —— 给模型看的一句话")
    print("  depends_on —— 要等谁。**这是唯一能算出并行度的信息**")
    print("  status     —— pending/running/done/failed/skipped，推进的依据")
    print()
    print("它和 Milestone 05 的草稿纸不是一回事：")
    print("  草稿纸存**结论**（已经查到了什么）")
    print("  计划存**待办**（还要做什么、先做哪个）")


# ────────────────────────────────────────────────────────────────────── 2
def section_2() -> None:
    show("2. 依赖决定能并行多少：拓扑分层")
    p = diamond()
    layers = p.batches()
    for i, layer in enumerate(layers):
        ids = "、".join(t.id for t in layer)
        note = "可并行" if len(layer) > 1 else "单独一步"
        print(f"  第 {i} 批：[{ids}]  （{note}）")
    print()
    print(f"串行做要 4 轮，按批做只要 {len(layers)} 轮 —— 中间那批两个任务互不依赖。")
    print("这个信息**模型给不出来**：它在 thought 里写下的计划只是一串文字，")
    print("没有可计算的依赖边。有了显式 Plan，循环之外的代码就能求它。")

    chain = Plan(goal="全串行")
    chain.add("a", "A")
    chain.add("b", "B", depends_on=("a",))
    chain.add("c", "C", depends_on=("b",))
    print()
    print(f"反例：全串行的链 → {[[t.id for t in l] for l in chain.batches()]}")
    print("一条依赖边都没有额外并行度，分层结果就是 3 批。")


# ────────────────────────────────────────────────────────────────────── 3
def section_3() -> None:
    show("3. 成环会被拦下")
    p = Plan(goal="一个自相矛盾的计划")
    p.add("a", "先做 A", depends_on=("b",))
    p.add("b", "先做 B", depends_on=("a",))
    print(p.render())
    try:
        p.batches()
        print("  （没拦住 —— 这是 bug）")
    except CircularDependencyError as exc:
        print(f"  拦住了：{exc}")
    print()
    print("人看一眼就知道 A、B 谁也先不了，但代码如果不查，")
    print("表现是「剩下的任务凑不出下一批」—— 然后静静地卡住。")
    print()
    dangling = Plan()
    dangling.add("t1", "查资料", depends_on=("t9",))
    try:
        dangling.validate()
    except CircularDependencyError as exc:
        print(f"另一种同类错误（依赖不存在的任务）：{exc}")
    print("必须**在派活之前**查：否则错误信息会变成「卡住了」，根本没法排查。")


# ────────────────────────────────────────────────────────────────────── 4
def section_4() -> None:
    show("4. 上游失败会跳过下游（传递闭包）")
    p = diamond()
    p.update("t1", DONE, "就比 P01 和 P04")
    p.update("t2", FAILED, "检索没有命中")
    skipped = p.skip_downstream("t2")
    print(p.render())
    print()
    print(f"被跳过的：{skipped}")
    print("注意 t3 仍是 pending —— 它不依赖 t2，不该被牵连。")
    print("这正是显式依赖换来的：失败的影响范围可以**精确计算**，")
    print("而不是「整个任务重来」或者「每步都重试一遍」。")


# ────────────────────────────────────────────────────────────────────── 5
def section_5() -> None:
    show("5. 计划工具：让模型自己拆、自己推进")
    plan = Plan()
    set_tool, update_tool, view_tool = plan_tools(plan)
    print("三个工具共用同一份 Plan（各建各的就成了三份互不相通的计划）。")
    print()
    tasks_json = (
        '[{"id":"t1","title":"确定对比对象"},'
        '{"id":"t2","title":"查 P01 落盘","depends_on":["t1"]},'
        '{"id":"t3","title":"查 P04 落盘","depends_on":["t1"]},'
        '{"id":"t4","title":"汇总差异","depends_on":["t2","t3"]}]'
    )
    print("模型调用 plan_set（tasks 是一段 JSON 字符串）：")
    print(f"  → {set_tool.run(goal='对比两个项目的持久化方式', tasks=tasks_json)}")
    print()
    print("模型写错 JSON 时（很常见），工具返回文本而不是抛异常：")
    print(f"  → {set_tool.run(tasks='我觉得应该先查资料再汇总')}")
    print()
    print("  ↑ 注意：这次失败把上一份计划清空了。这是「整份重设」的代价，")
    print("    换来的是不会出现半新半旧的计划 —— 模型重发一次就好。")
    set_tool.run(
        tasks='''[{"id":"t1","title":"确定对比对象"},
     {"id":"t2","title":"查 P01 落盘","depends_on":["t1"]},
     {"id":"t3","title":"查 P04 落盘","depends_on":["t1"]},
     {"id":"t4","title":"汇总差异","depends_on":["t2","t3"]}]'''
    )
    print()
    print("推进 t1、t2 之后，t4 会自动变成可做的：")
    update_tool.run(id="t1", status=DONE, result="P01 与 P04")
    update_tool.run(id="t2", status=DONE, result="P01 用 JSON 文件落盘")
    print(view_tool.run())


# ────────────────────────────────────────────────────────────────────── 6
def section_6() -> None:
    show("6. 离线跑一次带计划的多步骤任务")
    plan = Plan()
    pad = None
    from agent.memory import Scratchpad

    pad = Scratchpad()
    registry = ToolRegistry(default_tools(pad, plan))

    scripted = ScriptedLLM(
        LLMMessage(
            role="assistant",
            content="我先拆成四步，其中两步可以一起查。",
            tool_calls=[
                ToolCall(
                    id="p1",
                    name="plan_set",
                    arguments={
                        "goal": "对比 P01 与 P04 的持久化方式",
                        "tasks": '[{"id":"t1","title":"确定对比对象"},'
                        '{"id":"t2","title":"查 P01 落盘","depends_on":["t1"]},'
                        '{"id":"t3","title":"查 P04 落盘","depends_on":["t1"]},'
                        '{"id":"t4","title":"汇总差异","depends_on":["t2","t3"]}]',
                    },
                )
            ],
        ),
        LLMMessage(
            role="assistant",
            tool_calls=[
                ToolCall(id="s1", name="rag_search", arguments={"query": "Project 01 持久化"}),
                ToolCall(id="s2", name="rag_search", arguments={"query": "Project 04 会话落盘"}),
            ],
        ),
        LLMMessage(
            role="assistant",
            tool_calls=[
                ToolCall(id="u0", name="plan_update", arguments={"id": "t1", "status": "done", "result": "P01 与 P04"}),
                ToolCall(id="u1", name="plan_update", arguments={"id": "t2", "status": "done", "result": "P01 用 JSON 落盘"}),
                ToolCall(id="u2", name="plan_update", arguments={"id": "t3", "status": "done", "result": "P04 用原子写 + 会话存储"}),
            ],
        ),
        LLMMessage(role="assistant", content="P01 用 JSON 文件直接落盘；P04 改成原子写并接了会话存储。"),
    )
    agent = ReActAgent(
        scripted,
        registry,
        settings=AgentSettings(max_steps=8, context_budget=4000),
        scratchpad=pad,
        plan=plan,
    )
    result = agent.run("对比 Project 01 与 Project 04 各自怎么处理状态持久化")
    print(result.trace())
    print()
    print(f"步数 {result.steps_used} / 工具调用 {len(result.tool_calls)}")
    if result.plan:
        print(f"计划终态：{result.plan['goal']}（{len(result.plan['tasks'])} 个子任务）")
    print("计划**每轮都会重新渲染进 system**，所以模型看到的是最新进度，")
    print("不会因为照着开局那份过时的计划而重复做事。")


# ────────────────────────────────────────────────────────────────────── 7
def section_7() -> None:
    show("7. 真实模型：让 DeepSeek 自己决定拆几步（--real）")
    from agent.llm import DeepSeekLLM

    plan = Plan()
    from agent.memory import Scratchpad

    pad = Scratchpad()
    agent = ReActAgent(
        DeepSeekLLM(AgentSettings()),
        ToolRegistry(default_tools(pad, plan)),
        settings=AgentSettings.from_env(max_steps=10, context_budget=4000),
        scratchpad=pad,
        plan=plan,
    )
    question = (
        "对比 Project 01 与 Project 04 各自怎么处理状态持久化。"
        "先用 plan_set 拆成子任务，查的时候用 rag_search，每查完一个用 plan_update 标记完成，最后汇总。"
    )
    result = agent.run(question)
    print(result.trace())
    print()
    print(f"步数 {result.steps_used} / 工具调用 {len(result.tool_calls)}")
    if result.plan:
        print("计划终态：")
        for t in result.plan["tasks"]:
            print(f"  [{t['status']}] {t['id']} {t['title']}  → {t['result'][:60]}")
    print()
    print("观察点：")
    print("  · 模型自己决定拆几步、哪些步互不依赖")
    print("  · 它会主动调 plan_update 标完成 —— 计划是它自己在维护")
    print("  · 如果它没拆（直接开查），说明提示词里的引导还不够强")


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 06 多步骤任务演示")
    parser.add_argument("--real", action="store_true", help="调真实 DeepSeek")
    args = parser.parse_args()

    print("=" * WIDTH)
    print("  Project 05 · Milestone 06 —— Multi-Step Task（显式计划 + 依赖拓扑）")
    print("=" * WIDTH)

    for fn in (section_1, section_2, section_3, section_4, section_5, section_6):
        fn()
    if args.real:
        section_7()
    else:
        show("7. 真实模型（跳过）", "加 --real 会调真实 DeepSeek 跑第 7 节")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
