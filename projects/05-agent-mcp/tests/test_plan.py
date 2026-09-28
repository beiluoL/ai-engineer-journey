"""Milestone 06 —— 任务计划与依赖拓扑的测试。

这章最值得测的不是「能不能存下任务」，而是三件模型做不到的事：

1. **拓扑分层对不对** —— 分错了就会把有依赖的任务并行派出去，结果串味。
2. **成环能不能查出来** —— 模型真会写出 A→B→A，人一眼看出，代码不查就死循环。
3. **下游跳不跳得干净** —— 上游失败后的传递闭包，漏一个就会拿不存在的输入继续跑。
"""

from __future__ import annotations

import pytest

from agent.plan import (
    DONE,
    FAILED,
    PENDING,
    SKIPPED,
    CircularDependencyError,
    Plan,
    PlanError,
    SubTask,
    UnknownTaskError,
)
from agent.tools import PlanSetTool, PlanUpdateTool, PlanViewTool, plan_tools


# --------------------------------------------------------------------------- 装配
def _linear() -> Plan:
    """t1 → t2 → t3 的链。"""
    p = Plan(goal="链式任务")
    p.add("t1", "第一步")
    p.add("t2", "第二步", depends_on=("t1",))
    p.add("t3", "第三步", depends_on=("t2",))
    return p


def _diamond() -> Plan:
    """菱形：t1 完成 → t2 和 t3 可并行 → t4 等两者。"""
    p = Plan(goal="菱形依赖")
    p.add("t1", "取数据")
    p.add("t2", "算 A", depends_on=("t1",))
    p.add("t3", "算 B", depends_on=("t1",))
    p.add("t4", "汇总", depends_on=("t2", "t3"))
    return p


class TestSubTask:
    def test_empty_id_rejected(self):
        with pytest.raises(PlanError, match="id 不能为空"):
            SubTask(id="  ", title="有事")

    def test_empty_title_rejected(self):
        with pytest.raises(PlanError, match="title 不能为空"):
            SubTask(id="t1", title="")

    def test_bad_status_rejected(self):
        with pytest.raises(PlanError, match="状态非法"):
            SubTask(id="t1", title="有事", status="maybe")

    def test_self_dependency_rejected(self):
        with pytest.raises(CircularDependencyError, match="依赖了自己"):
            SubTask(id="t1", title="有事", depends_on=("t1",))

    def test_duplicate_dependency_deduped(self):
        t = SubTask(id="t1", title="有事", depends_on=("a", "a", "b"))
        assert t.depends_on == ("a", "b")

    def test_terminal_states(self):
        assert not SubTask(id="t", title="x", status=PENDING).is_terminal
        for status in (DONE, FAILED, SKIPPED):
            assert SubTask(id="t", title="x", status=status).is_terminal

    def test_render_shows_dependency_status(self):
        p = _linear()
        line = p.require("t2").render(p.by_id())
        assert "t1:pending" in line


class TestPlanCrud:
    def test_duplicate_id_rejected(self):
        p = Plan()
        p.add("t1", "第一")
        with pytest.raises(PlanError, match="id 重复"):
            p.add("t1", "又来")

    def test_require_unknown_raises(self):
        p = _linear()
        with pytest.raises(UnknownTaskError, match="没有 id 为 'zz'") as exc:
            p.require("zz")
        # 错误信息要把已有 id 列出来，模型才能自己纠正
        assert "t1" in str(exc.value)

    def test_find_returns_none_when_missing(self):
        assert _linear().find("nope") is None

    def test_update_sets_status_and_result(self):
        p = _linear()
        p.update("t1", DONE, "查到了")
        assert p.require("t1").status == DONE
        assert p.require("t1").result == "查到了"

    def test_update_without_result_keeps_old(self):
        p = _linear()
        p.update("t1", DONE, "结论")
        p.update("t1", "running")
        assert p.require("t1").result == "结论"


class TestValidate:
    def test_unknown_dependency_rejected(self):
        p = Plan()
        p.add("t1", "有事", depends_on=("ghost",))
        with pytest.raises(CircularDependencyError, match="不存在的 'ghost'"):
            p.validate()

    def test_valid_plan_passes(self):
        _diamond().validate()  # 不抛即通过


class TestBatches:
    def test_independent_tasks_in_one_batch(self):
        p = Plan()
        p.add("a", "A")
        p.add("b", "B")
        batches = p.batches()
        assert len(batches) == 1
        assert {t.id for t in batches[0]} == {"a", "b"}

    def test_chain_is_fully_serial(self):
        batches = _linear().batches()
        assert [[t.id for t in layer] for layer in batches] == [["t1"], ["t2"], ["t3"]]

    def test_diamond_groups_parallel_middle(self):
        """菱形的关键：中间那批必须是**两个**，否则并行性就丢了。"""
        batches = _diamond().batches()
        assert [[t.id for t in layer] for layer in batches] == [
            ["t1"],
            ["t2", "t3"],
            ["t4"],
        ]

    def test_cycle_is_detected(self):
        """A 等 B、B 等 A —— 人不难看出，代码不查就会一直空转。"""
        p = Plan()
        p.add("a", "A", depends_on=("b",))
        p.add("b", "B", depends_on=("a",))
        with pytest.raises(CircularDependencyError, match="依赖无法推进"):
            p.batches()

    def test_finished_tasks_excluded(self):
        p = _linear()
        p.update("t1", DONE, "好了")
        batches = p.batches()
        assert [t.id for t in batches[0]] == ["t2"]

    def test_failed_task_blocks_downstream_batch(self):
        p = _linear()
        p.update("t1", FAILED, "查不到")
        # t1 已终态，剩 t2/t3；t2 的依赖不是 DONE，所以它进不了第一批
        with pytest.raises(CircularDependencyError):
            p.batches()

    def test_ready_only_returns_satisfied(self):
        p = _diamond()
        assert [t.id for t in p.ready()] == ["t1"]
        p.update("t1", DONE)
        assert {t.id for t in p.ready()} == {"t2", "t3"}


class TestSkipDownstream:
    def test_direct_downstream_skipped(self):
        p = _linear()
        p.update("t1", FAILED)
        skipped = p.skip_downstream("t1")
        assert skipped == ["t2", "t3"]  # 传递闭包，不是只有 t2
        assert p.require("t3").status == SKIPPED

    def test_skip_reason_recorded(self):
        p = _linear()
        p.update("t1", FAILED)
        p.skip_downstream("t1")
        assert "t1" in p.require("t2").result

    def test_done_tasks_not_touched(self):
        p = _linear()
        p.update("t1", DONE)
        p.update("t2", FAILED)
        p.skip_downstream("t2")
        assert p.require("t1").status == DONE
        assert p.require("t3").status == SKIPPED

    def test_diamond_partial_failure(self):
        """t2 失败只该影响 t4，t3 不受影响 —— 这正是显式依赖换来的好处。"""
        p = _diamond()
        p.update("t1", DONE)
        p.update("t2", FAILED)
        p.skip_downstream("t2")
        assert p.require("t3").status == PENDING
        assert p.require("t4").status == SKIPPED


class TestRenderAndSerialization:
    def test_render_contains_goal_and_progress(self):
        text = _diamond().render()
        assert "菱形依赖" in text
        assert "进度 0/4" in text

    def test_render_marks_progress(self):
        p = _diamond()
        p.update("t1", DONE)
        p.update("t2", DONE)
        p.update("t3", FAILED)
        p.skip_downstream("t3")
        assert "进度 4/4（完成 2）" in p.render()

    def test_roundtrip_dict(self):
        p = _diamond()
        p.update("t1", DONE, "原始数据")
        restored = Plan.from_dict(p.to_dict())
        assert restored.goal == p.goal
        assert [t.id for t in restored.tasks] == [t.id for t in p.tasks]
        assert restored.require("t1").status == DONE
        assert restored.require("t1").result == "原始数据"

    def test_is_complete(self):
        p = _linear()
        assert not p.is_complete
        for tid in ("t1", "t2", "t3"):
            p.update(tid, DONE)
        assert p.is_complete


class TestParseTasks:
    def test_plain_json_array(self):
        p = Plan()
        p.parse_tasks('[{"id":"t1","title":"查 P01"},{"id":"t2","title":"汇总","depends_on":["t1"]}]')
        assert [t.id for t in p.tasks] == ["t1", "t2"]
        assert p.require("t2").depends_on == ("t1",)

    def test_fenced_json_block(self):
        """模型十次有八次会把 JSON 包在 ```json 里。"""
        p = Plan()
        p.parse_tasks('好，这是我的计划：\n```json\n[{"id":"t1","title":"A"}]\n```\n')
        assert [t.id for t in p.tasks] == ["t1"]

    def test_bad_json_raises_with_original(self):
        p = Plan()
        with pytest.raises(PlanError, match="不是合法 JSON") as exc:
            p.parse_tasks("这不是 JSON")
        assert "这不是 JSON" in str(exc.value)

    def test_missing_fields_raises(self):
        p = Plan()
        with pytest.raises(PlanError, match="都要有 id 和 title"):
            p.parse_tasks('[{"id":"t1"}]')

    def test_parse_replaces_previous_plan(self):
        p = _linear()
        p.parse_tasks('[{"id":"new","title":"全新"}]')
        assert [t.id for t in p.tasks] == ["new"]

    def test_parse_validates_dependencies(self):
        p = Plan()
        with pytest.raises(CircularDependencyError):
            p.parse_tasks('[{"id":"t1","title":"A","depends_on":["zz"]}]')


class TestPlanTools:
    def test_tools_share_one_plan(self):
        """各建各的 = 三份互不相通的计划，这是最容易写错的坑。"""
        plan = Plan()
        set_tool, update_tool, view_tool = plan_tools(plan)
        set_tool.run(goal="对比两个项目", tasks='[{"id":"t1","title":"查 P01"}]')
        assert plan.goal == "对比两个项目"
        assert "t1" in view_tool.run()

    def test_plan_set_reports_batches(self):
        tool = PlanSetTool()
        out = tool.run(
            tasks='[{"id":"t1","title":"A"},{"id":"t2","title":"B"},{"id":"t3","title":"汇总","depends_on":["t1","t2"]}]'
        )
        assert "3 个子任务" in out
        assert "2 批" in out
        assert "并行" in out

    def test_plan_set_reports_bad_json_as_text(self):
        """工具层不抛异常 —— 和别处一样，错误要变成模型看得见的文本。"""
        tool = PlanSetTool()
        out = tool.run(tasks="天书")
        assert out.startswith("[计划建立失败]")

    def test_update_unknown_id_returns_error_text(self):
        tool = PlanUpdateTool()
        out = tool.run(id="zz", status=DONE)
        assert "[更新失败]" in out

    def test_failed_update_skips_downstream(self):
        plan = _linear()
        tool = PlanUpdateTool(plan)
        out = tool.run(id="t1", status=FAILED, result="查不到")
        assert "下游已自动跳过" in out
        assert plan.require("t3").status == SKIPPED

    def test_view_without_plan(self):
        assert "没有计划" in PlanViewTool().run()
