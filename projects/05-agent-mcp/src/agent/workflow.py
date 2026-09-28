"""Project 05 —— Agent Workflow：把计划派给多个 Worker（Milestone 10）。

到 Milestone 09 为止，一个任务始终是**一个 Agent 从头跑到尾**。
它现在有了计划（06）、有了草稿纸（05）、还能用别人的工具（09），
但所有步骤仍挤在同一段对话里。

问题在哪：

    一个跑了 8 步的 Agent，它的 messages 里有 8 轮工具输出。
    第 8 步做「汇总」时，前面 7 步的检索原文全还在上下文里 ——
    而它真正需要的只是那 7 步各自的**结论**。

Milestone 05 的裁剪能压掉一部分，但压掉的是"早的"，不是"无关的"。

Workflow 的做法是**换一种组织方式**：

    Plan 的每个子任务 → 派给一个**独立的 Worker**（自己的 ReActAgent、自己的 messages）
    Worker 只拿到：这个子任务是什么 + 它依赖的那些子任务的**结论**
    Worker 做完后：结论写进共享的草稿纸 + 在 Plan 上标 done

好处是三条：

1. **上下文隔离** —— 每个 Worker 只看自己需要的那一点，不会被别处的检索原文撑大。
2. **失败不扩散** —— 一个子任务炸了，只影响它的下游（Plan 已经算好了是谁）。
3. **同批可并行** —— Milestone 06 算出的 batches() 在这里才真正派上用场。

代价也要说清楚：**Worker 之间不能直接对话**，只能通过草稿纸传结论。
所以「子任务的结论该写多详细」是个真问题 —— 写少了汇总时信息不够，
写多了又回到上下文膨胀。本项目要求 Worker **写结论而不是写原文**，就是这个原因。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .agent import AgentResult, ReActAgent
from .llm import LLM
from .memory import Scratchpad
from .plan import DONE, FAILED, PENDING, RUNNING, Plan
from .registry import ToolRegistry
from .settings import AgentSettings

__all__ = ["WorkflowResult", "Workflow", "build_workflow", "PLANNER_PROMPT", "WORKER_PROMPT"]

PLANNER_PROMPT = """你是一个任务规划者。把用户给的目标拆成若干子任务，并用 plan_set 记录下来。

要求：
- 每个子任务要能被**独立完成**（一句话说清要做什么）
- 只把真正的前置关系写成 depends_on；没有依赖就留空数组 —— 它们会被并行执行
- 3 到 6 个子任务为宜，不要拆得太碎
- 最后一定要有一个「汇总」类的子任务，它依赖前面所有查询类子任务

拆完计划后，直接说一句「计划已建立」即可，不要自己开始执行。"""

WORKER_PROMPT = """你是一个执行者，负责完成**一个**子任务。

要求：
- 只做交给你的这一件事，不要顺手做别人的
- 需要事实时用工具查，不要编造
- 完成后把**结论**记到草稿纸上（write_note），写事实本身，不要写"我查到了"这类话
- 结论要写成一两句能被引用的话 —— 后面有人会只读你的结论来做汇总
"""


@dataclass
class WorkflowResult:
    """一次 Workflow 的完整结果。"""

    goal: str
    answer: str
    plan: dict[str, Any] | None = None
    notes: dict[str, str] = field(default_factory=dict)
    workers: list[dict[str, Any]] = field(default_factory=list)

    @property
    def finished(self) -> int:
        return sum(1 for w in self.workers if w["status"] in (DONE, FAILED))

    def render(self) -> str:
        lines = [f"目标：{self.goal}"]
        for w in self.workers:
            flag = "✓" if w["status"] == DONE else ("✗" if w["status"] == FAILED else "-")
            lines.append(f"  {flag} {w['id']} {w['title']}  （{w['steps']} 步 / {w['tool_calls']} 次调用）")
            if w.get("result"):
                lines.append(f"      → {w['result'][:120]}")
        if self.notes:
            lines.append("草稿纸：")
            for key, value in self.notes.items():
                lines.append(f"  · {key}：{value[:120]}")
        lines.append(f"汇总：{self.answer}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "answer": self.answer,
            "plan": self.plan,
            "notes": dict(self.notes),
            "workers": list(self.workers),
        }


class Workflow:
    """按 Plan 的依赖分批，把子任务派给独立 Worker，最后汇总。

    刻意不做的事：真正的并发（线程/进程）。
    ``batches()`` 已经把「谁可以并行」算出来了，并发只是执行方式的区别；
    这一章想证明的是**上下文隔离**带来的收益，串行也能看到。
    """

    def __init__(
        self,
        llm: LLM,
        registry: ToolRegistry,
        *,
        settings: AgentSettings | None = None,
        scratchpad: Scratchpad | None = None,
        plan: Plan | None = None,
        llm_factory: Callable[[], LLM] | None = None,
        verbose: bool = False,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.settings = settings or AgentSettings()
        self.pad = scratchpad if scratchpad is not None else Scratchpad()
        self.plan = plan if plan is not None else Plan()
        self.llm_factory = llm_factory
        self.verbose = verbose
        #: 每个子任务的开销统计。排查时最想知道的是「哪个子任务最贵」 ——
        #: 不能放在类属性上（那是共享的可变对象），必须每个实例一份。
        self._stats: dict[str, dict[str, int]] = {}

    # ---------------------------------------------------------------- 规划
    def make_plan(self, goal: str) -> Plan:
        """让模型自己拆计划。

        用一个**只带计划工具**的 Agent：它没必要看到检索工具，
        否则很容易一边拆一边就开始查了。
        """
        from .registry import ToolRegistry  # 局部导入，避免顶层循环依赖
        from .tools import plan_tools

        planner = ReActAgent(
            self._new_llm(),
            ToolRegistry(plan_tools(self.plan)),
            settings=self.settings.replace(max_steps=4),
            system_prompt=PLANNER_PROMPT,
            plan=self.plan,
        )
        planner.run(f"请把这个目标拆成子任务：{goal}")
        if not self.plan.tasks:
            raise RuntimeError("规划者没有产出任何子任务")
        return self.plan

    def _new_llm(self) -> LLM:
        """每个 Worker 用**独立的 LLM 实例**。

        为什么要独立：``RecordingLLM`` 会把每次请求的快照存在实例上。
        共用一个实例的话，所有 Worker 的轨迹会混在一起 —— 排查时
        就再也看不出「这一步是哪一个子任务发出的」。
        """
        return self.llm_factory() if self.llm_factory is not None else self.llm

    # ---------------------------------------------------------------- 执行
    def run(self, goal: str, tasks: str | None = None) -> WorkflowResult:
        """跑完整个 Workflow。

        ``tasks`` 给了就直接用（离线测试/确定性场景），不给就让模型拆。
        """
        self.plan.goal = goal
        if tasks is not None:
            self.plan.parse_tasks(tasks)
        elif not self.plan.tasks:
            self.make_plan(goal)

        # 执行必须**动态**取 ready()，不能一次性按 batches() 派完。
        #
        # batches() 是「开局时的并行度」；但跑起来之后某个子任务可能失败，
        # 它的下游会被 skip_downstream 标成 SKIPPED —— 如果按开局的批次派，
        # 这些已经没意义的任务照样会被派出去（真踩过：t1 失败了 t3 还在跑）。
        # 计划是静态的，执行是动态的。
        planned_batches = self.plan.batches()
        if self.verbose:
            print(
                f"计划 {self.plan.total} 个子任务，开局可分 {len(planned_batches)} 批："
                + "、".join("[" + ",".join(t.id for t in b) + "]" for b in planned_batches)
            )
        while True:
            ready = self.plan.ready()
            if not ready:
                break
            for task in ready:
                self._run_task(task)

        answer = self._summarize()
        return WorkflowResult(
            goal=goal,
            answer=answer,
            plan=self.plan.to_dict(),
            notes=self.pad.to_dict(),
            workers=[
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "result": t.result,
                    "steps": self._stats.get(t.id, {}).get("steps", 0),
                    "tool_calls": self._stats.get(t.id, {}).get("tool_calls", 0),
                }
                for t in self.plan.tasks
            ],
        )

    def _run_task(self, task: Any) -> None:
        """派一个 Worker 去做一个子任务。返回后 Plan 上的状态已经更新。"""
        self.plan.update(task.id, RUNNING)
        known = self.plan.by_id()
        deps = "\n".join(
            f"- {known[d].title}：{known[d].result}" for d in task.depends_on if d in known and known[d].result
        )
        question = f"子任务（{task.id}）：{task.title}"
        if deps:
            question += f"\n\n已经完成的依赖，结论如下：\n{deps}"
        if self.pad.to_dict():
            question += f"\n\n草稿纸上已有的笔记：\n{self.pad.render()}"

        worker = ReActAgent(
            self._new_llm(),
            self.registry,
            settings=self.settings,
            system_prompt=WORKER_PROMPT,
            scratchpad=self.pad,
        )
        try:
            result: AgentResult = worker.run(question)
            # Worker 自己可能忘了写笔记 —— 那就用它的最终答案当结论。
            # 结论要截短：它会被写进 Plan，而 Plan 每轮都要渲染进下游 Worker 的提示。
            conclusion = result.answer.strip()
            self.plan.update(task.id, DONE, conclusion[:400])
            self._record(task.id, result)
            if self.verbose:
                print(f"[worker {task.id}] {conclusion[:100]}")
        except Exception as exc:
            self.plan.update(task.id, FAILED, f"{type(exc).__name__}: {exc}")
            self._record(task.id, None)
            self.plan.skip_downstream(task.id)

    def _record(self, task_id: str, result: AgentResult | None) -> None:
        """记下这个子任务花了多少步、调了几次工具。"""
        self._stats[task_id] = {
            "steps": result.steps_used if result else 0,
            "tool_calls": len(result.tool_calls) if result else 0,
        }

    def _summarize(self) -> str:
        """汇总。汇总者只读草稿纸和计划，**看不到任何 Worker 的中间过程**。"""
        done = [t for t in self.plan.tasks if t.status == DONE]
        if not done:
            failed = [t for t in self.plan.tasks if t.status == FAILED]
            reason = failed[0].result if failed else "没有任何子任务完成"
            return f"任务未能完成：{reason}"

        body = "\n".join(f"- {t.title}：{t.result}" for t in done)
        notes = self.pad.render()
        question = f"目标：{self.plan.goal}\n\n各子任务的结论：\n{body}"
        if notes:
            question += f"\n\n草稿纸：\n{notes}"
        question += "\n\n请据此给出一段完整的回答。不要说'根据子任务'这类话，直接回答。"

        summarizer = ReActAgent(
            self._new_llm(),
            self.registry,
            settings=self.settings.replace(max_steps=3),
            system_prompt="你是汇总者。只能使用上面给出的结论，不要发起新的检索。",
        )
        return summarizer.run(question).answer


def build_workflow(
    llm: LLM | None = None,
    *,
    registry: ToolRegistry | None = None,
    settings: AgentSettings | None = None,
    scratchpad: Scratchpad | None = None,
    plan: Plan | None = None,
    use_mcp: bool = False,
) -> Workflow:
    """装配一个 Workflow。

    ``use_mcp=True`` 时工具全部来自 MCP 子进程 —— 这样 Worker 用的工具
    和主进程里的类没有任何关系，是 Milestone 09 成果的直接延续。
    """
    if llm is None:
        from .llm import FakeLLM

        llm = FakeLLM()
    if registry is None:
        if use_mcp:
            from .mcp.client import mcp_tools, spawn_default_server
            from .tools import ReadNotesTool, WriteNoteTool

            client = spawn_default_server()
            client.start()
            client.initialize()
            # **草稿纸工具必须留在本地**：它是 Agent 自己的状态，不是外部能力。
            # 全用 MCP 工具的话 Worker 会发现没有 write_note 可用 —— 真踩过，
            # 表现是模型反复调用一个不存在的工具直到步数耗尽，而错误信息
            # 只是「用了 N 步仍未给出最终答案」，完全看不出原因。
            registry = ToolRegistry(
                list(mcp_tools(client)) + [WriteNoteTool(scratchpad), ReadNotesTool(scratchpad)]
            )
        else:
            from .tools import default_tools

            registry = ToolRegistry(default_tools(scratchpad, plan))
    return Workflow(
        llm,
        registry,
        settings=settings,
        scratchpad=scratchpad,
        plan=plan,
    )
