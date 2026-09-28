"""Project 05 —— 任务计划与依赖拓扑（Milestone 06）。

Milestone 05 解决了「中间结论往哪放」：草稿纸。
但草稿纸里记的是**结论**（key → value），它回答不了多步骤任务真正的问题：

    「这件事拆成几步？哪几步可以同时做？哪一步要等别的步先出结果？」

把拆解留在模型每轮的 thought 里是够用的 —— 只要任务够短。
一旦步骤超过三四步，模型的「计划」就开始漂移：
它会忘记自己列过什么、重复做已经做完的、或者在依赖没满足时硬做。

所以这一章把计划从**模型的临时想法**变成**显式的、可检查的数据结构**：

    Plan（目标 + 一组 SubTask）
      └── SubTask: id / title / depends_on / status / result

有了显式结构，循环之外的代码就能做三件模型做不到的事：

1. **求可并行批次**（``Plan.batches()``）：依赖都满足的子任务可以一起派出去，
   不用串行等。模型在 thought 里想出来的计划没有这个信息。
2. **依赖失败自动跳过下游**（``Plan.skip_downstream``）：上游失败了，
   下游做下去也没有意义 —— 而且每步都重试一遍只会烧 token。
3. **环检测**：模型写出来的依赖偶尔会成环（A 等 B、B 等 A）。
   人看一眼就知道不对，但代码如果不查会直接死循环。

一个容易混的点：``Plan`` 和 ``Scratchpad``（Milestone 05）不是一回事。

    Scratchpad 存**结论** ——「P01 用 JSON 落盘」这种已经查到的东西
    Plan       存**待办** ——「还要查 P04 怎么落盘」这种没做的事

前者会被读回来用，后者会被推进状态。别把它们合成一个。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "PENDING",
    "RUNNING",
    "DONE",
    "FAILED",
    "SKIPPED",
    "TERMINAL_STATES",
    "SubTask",
    "Plan",
    "PlanError",
    "UnknownTaskError",
    "CircularDependencyError",
]

PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
SKIPPED = "skipped"

#: 已经不会再变的状态。判断是否「还有事可做」时用它。
TERMINAL_STATES = (DONE, FAILED, SKIPPED)

_MARK = {
    PENDING: "[ ]",
    RUNNING: "[>]",
    DONE: "[x]",
    FAILED: "[!]",
    SKIPPED: "[-]",
}


class PlanError(Exception):
    """计划层面的错误基类。"""


class UnknownTaskError(PlanError):
    """引用了不存在的子任务 id。"""


class CircularDependencyError(PlanError):
    """依赖成环，或者依赖指向了不存在的任务 —— 两种情况都会卡死推进。"""


@dataclass
class SubTask:
    """一个子任务。

    ``depends_on`` 存的是**别人**的 id：这个任务要等它们都 DONE 才能开始。
    空元组表示「现在就能做」。

    ``result`` 只放**结论**，别放完整工具输出 —— 那会把上下文重新撑大，
    正好抵消 Milestone 05 好不容易省下来的 token。放一两句话就够。
    """

    id: str
    title: str
    depends_on: tuple[str, ...] = ()
    status: str = PENDING
    result: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise PlanError("SubTask 的 id 不能为空")
        if not self.title.strip():
            raise PlanError(f"SubTask {self.id!r} 的 title 不能为空")
        if self.status not in (PENDING, RUNNING, DONE, FAILED, SKIPPED):
            raise PlanError(f"SubTask {self.id!r} 的状态非法：{self.status}")
        # 依赖去重但保留顺序：模型偶尔会把同一个 id 写两遍
        seen: list[str] = []
        for dep in self.depends_on:
            if dep and dep not in seen:
                seen.append(dep)
        self.depends_on = tuple(seen)
        if self.id in self.depends_on:
            raise CircularDependencyError(f"SubTask {self.id!r} 依赖了自己")

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def render(self, tasks_by_id: dict[str, "SubTask"] | None = None) -> str:
        """渲染成一行。``tasks_by_id`` 给了就把依赖标上对方的状态。"""
        line = f"{_MARK[self.status]} {self.id}  {self.title}"
        if self.depends_on:
            if tasks_by_id is None:
                line += f"  (等 {', '.join(self.depends_on)})"
            else:
                parts = []
                for dep in self.depends_on:
                    other = tasks_by_id.get(dep)
                    flag = "?" if other is None else other.status
                    parts.append(f"{dep}:{flag}")
                line += f"  (等 {', '.join(parts)})"
        if self.result:
            line += f"\n      → {self.result}"
        return line


@dataclass
class Plan:
    """一份任务计划。

    为什么不用 dict 存子任务：``batches()`` 和渲染都要**稳定顺序**，
    list 天然保序，而且是模型写计划时的自然顺序（第一步先会被写下来）。
    """

    goal: str = ""
    tasks: list[SubTask] = field(default_factory=list)

    # ---------------------------------------------------------------- 增删查
    def add(
        self,
        task_id: str,
        title: str,
        *,
        depends_on: tuple[str, ...] = (),
        result: str = "",
    ) -> SubTask:
        if self.find(task_id) is not None:
            raise PlanError(f"子任务 id 重复：{task_id}")
        task = SubTask(id=task_id, title=title, depends_on=depends_on, result=result)
        self.tasks.append(task)
        return task

    def find(self, task_id: str) -> SubTask | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def require(self, task_id: str) -> SubTask:
        """取任务，取不到就抛 —— 更新一个不存在的任务是模型写错 id 的信号，
        静默忽略会让它以为自己推进成功了。"""
        task = self.find(task_id)
        if task is None:
            raise UnknownTaskError(
                f"没有 id 为 {task_id!r} 的子任务。已有：{', '.join(t.id for t in self.tasks) or '（空）'}"
            )
        return task

    def by_id(self) -> dict[str, SubTask]:
        return {t.id: t for t in self.tasks}

    # ---------------------------------------------------------------- 校验
    def validate(self) -> None:
        """检查依赖是否都指向真实存在的任务。

        这一步必须在**派活之前**做：模型写出 `depends_on=["t9"]` 而 t9 不存在时，
        ``batches()`` 会因为这个依赖永远不满足而卡住，错误信息会非常难懂。
        """
        known = self.by_id()
        for t in self.tasks:
            for dep in t.depends_on:
                if dep not in known:
                    raise CircularDependencyError(
                        f"SubTask {t.id!r} 依赖了不存在的 {dep!r}。"
                        f"已有子任务：{', '.join(known) or '（空）'}"
                    )

    # ---------------------------------------------------------------- 推进
    def update(self, task_id: str, status: str, result: str | None = None) -> SubTask:
        task = self.require(task_id)
        task.status = status
        if result is not None:
            task.result = result
        return task

    def skip_downstream(self, failed_id: str) -> list[str]:
        """把失败任务的**所有下游**标成 SKIPPED，返回被跳过的 id。

        为什么不是让它们各自重试：上游失败了，下游的输入根本不存在，
        重试只会再失败一次。主动跳过还能让 ``render()`` 把原因显示出来。
        """
        skipped: list[str] = []
        changed = True
        while changed:  # 传递闭包：A 失败 → B 跳过 → C（依赖 B）也要跳过
            changed = False
            for t in self.tasks:
                if t.is_terminal:
                    continue
                if failed_id in t.depends_on or any(
                    s in t.depends_on for s in skipped
                ):
                    t.status = SKIPPED
                    t.result = f"上游 {failed_id} 未完成，跳过"
                    skipped.append(t.id)
                    changed = True
        return skipped

    # ---------------------------------------------------------------- 拓扑
    def ready(self) -> list[SubTask]:
        """当前**依赖已满足、自己还没做**的任务。"""
        known = self.by_id()
        out = []
        for t in self.tasks:
            if t.status != PENDING:
                continue
            if all(known.get(d) is not None and known[d].status == DONE for d in t.depends_on):
                out.append(t)
        return out

    def batches(self) -> list[list[SubTask]]:
        """按依赖切成一批批**可以并行做**的任务（Kahn 分层）。

        第 0 批是现在就能做的全部任务；第 1 批要等第 0 批做完……依此类推。
        同一批内部**互不依赖**，所以可以安全地同时派给多个 worker。

        成环时会抛 ``CircularDependencyError`` —— 剩下的任务凑不出新的一层，
        说明它们互相等对方，永远推进不了。
        """
        self.validate()
        remaining = [t for t in self.tasks if not t.is_terminal]
        remaining_ids = {t.id for t in remaining}
        layers: list[list[SubTask]] = []
        done: set[str] = {t.id for t in self.tasks if t.status == DONE}

        while remaining_ids:
            layer = [
                t
                for t in remaining
                if t.id in remaining_ids and all(d in done for d in t.depends_on)
            ]
            if not layer:
                stuck = ", ".join(sorted(remaining_ids))
                raise CircularDependencyError(
                    f"依赖无法推进（成环或依赖未满足），卡住的：{stuck}"
                )
            layers.append(layer)
            for t in layer:
                remaining_ids.discard(t.id)
                done.add(t.id)  # 假设这一批会做完，才能算出下一批

        return layers

    # ---------------------------------------------------------------- 视图
    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def finished(self) -> int:
        return sum(1 for t in self.tasks if t.is_terminal)

    @property
    def done_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == DONE)

    @property
    def is_complete(self) -> bool:
        return bool(self.tasks) and all(t.is_terminal for t in self.tasks)

    def render(self) -> str:
        known = self.by_id()
        head = f"目标：{self.goal}" if self.goal else "目标：（未设定）"
        body = [t.render(known) for t in self.tasks]
        tail = f"进度 {self.finished}/{self.total}（完成 {self.done_count}）"
        return "\n".join([head, *body, tail])

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "depends_on": list(t.depends_on),
                    "status": t.status,
                    "result": t.result,
                }
                for t in self.tasks
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Plan":
        plan = cls(goal=str(payload.get("goal", "")))
        for raw in payload.get("tasks", []):
            plan.add(
                str(raw["id"]),
                str(raw["title"]),
                depends_on=tuple(str(d) for d in raw.get("depends_on", ())),
                result=str(raw.get("result", "")),
            )
            if "status" in raw:
                plan.update(str(raw["id"]), str(raw["status"]))
        return plan

    def parse_tasks(self, payload: str) -> "Plan":
        """从模型给的一段 JSON 里重建计划，并返回 self 方便链式调用。

        模型经常把 JSON 包在 ```json 代码块里，或者多写一句解释 ——
        这里做一次宽容的提取，失败时把原文一起抛出来方便排查。
        """
        import json
        import re

        text = payload.strip()
        fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
        if fence:
            text = fence.group(1).strip()
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            text = text[start : end + 1]
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PlanError(
                f"计划不是合法 JSON（{exc}）。原文前 200 字：{payload[:200]}"
            ) from exc
        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            raise PlanError(f"计划需要是一个列表，收到的是 {type(raw).__name__}")

        self.tasks.clear()
        for item in raw:
            if not isinstance(item, dict):
                raise PlanError(f"计划里有一项不是对象：{item!r}")
            if "id" not in item or "title" not in item:
                raise PlanError(f"计划的每一项都要有 id 和 title，收到：{item}")
            self.add(
                str(item["id"]),
                str(item["title"]),
                depends_on=tuple(str(d) for d in item.get("depends_on", ())),
            )
        self.validate()
        return self
