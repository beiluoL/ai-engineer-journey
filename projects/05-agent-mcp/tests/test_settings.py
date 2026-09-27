"""Project 05 —— 配置测试。沿用 Project 04 的那套约定。"""

from __future__ import annotations

import dataclasses

import pytest

from agent.settings import AGENT_SYSTEM_PROMPT, AgentSettings


def test_defaults_are_offline_safe() -> None:
    s = AgentSettings()
    assert s.max_steps > 0 and s.max_tool_failures > 0
    assert "deepseek" in s.model


def test_settings_are_frozen() -> None:
    s = AgentSettings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.model = "other"  # type: ignore[misc]


def test_replace_derives_new_settings() -> None:
    s = AgentSettings(max_steps=8).replace(max_steps=2, model="deepseek-reasoner")
    assert (s.max_steps, s.model) == (2, "deepseek-reasoner")
    assert AgentSettings().max_steps == 8, "replace 不能影响原对象"


def test_from_env_reads_agent_prefix(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MAX_STEPS", "3")
    monkeypatch.setenv("AGENT_MODEL", "deepseek-chat")
    monkeypatch.delenv("AGENT_TRACE_DIR", raising=False)
    s = AgentSettings.from_env()
    assert s.max_steps == 3 and isinstance(s.max_steps, int)
    assert s.model == "deepseek-chat"


def test_from_env_coerces_types(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.7")
    assert AgentSettings.from_env().temperature == 0.7


def test_from_env_overrides_win(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MAX_STEPS", "9")
    assert AgentSettings.from_env(max_steps=1).max_steps == 1


def test_system_prompt_forbids_guessing() -> None:
    assert "不要编造" in AGENT_SYSTEM_PROMPT
    assert "先调用工具" in AGENT_SYSTEM_PROMPT
