"""Project 05 —— 测试夹具。

一个重要决定：**测试目录不用 pytest 内置的 ``tmp_path``**。
本仓库的开发沙箱里 ``/private/var/.../pytest-of-unknown`` 不可写，
``tmp_path`` 会直接 PermissionError。所以统一用一个仓库内的临时工作目录，
跑完自动清理 —— 顺带也让"轨迹落盘"这类测试能看到真实的相对路径行为。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from agent.registry import ToolRegistry
from agent.settings import AgentSettings
from agent.tools import FunctionTool, Tool, function_schema


def _need(x: int) -> str:
    """必须给 x。"""
    return f"got {x}"


@pytest.fixture()
def workdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """仓库内的临时工作目录，返回 Path。"""
    return Path(tempfile.mkdtemp(prefix="agent-tests-"))


@pytest.fixture()
def settings() -> AgentSettings:
    return AgentSettings(max_steps=5, max_tool_failures=2)


@pytest.fixture()
def keyed_settings(monkeypatch: pytest.MonkeyPatch) -> AgentSettings:
    """一个「有 Key」的配置：单测不联网，只需要 DeepSeekLLM 构造能通过。"""
    monkeypatch.setenv("AGENT_TEST_KEY", "sk-test-not-a-real-key")
    return AgentSettings(api_key_env="AGENT_TEST_KEY")


@pytest.fixture()
def reg() -> ToolRegistry:
    """带自定义工具的注册表。默认内置表没有 add / _need。"""
    registry = ToolRegistry(tools=[])

    class _Add(Tool):
        """自定义工具：故意声明 schema 里的两个参数都是整数。"""
        name = "add"
        description = "两数相加（参数会被注册表按 schema 纠偏）"
        parameters = {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }

        def schema(self):  # type: ignore[override]
            return function_schema(self.name, self.description, self.parameters)

        def run(self, **kwargs) -> str:
            return str(int(kwargs["a"]) + int(kwargs["b"]))

    registry.register(_Add())
    registry.register(FunctionTool(_need, name="_need"))
    return registry


@pytest.fixture()
def clean_workdir() -> str:
    """一个干净的空目录字符串。"""
    return tempfile.mkdtemp(prefix="agent-clean-")


@pytest.fixture(autouse=True)
def _remove_tmpdirs():
    yield
    for path in list(Path(tempfile.gettempdir()).glob("agent-*-*")):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
