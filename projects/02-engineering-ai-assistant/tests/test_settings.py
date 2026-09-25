"""Settings 的单元测试（对应 milestones/05 与挑战 1、2）。"""

import os

import pytest

from assistant.errors import LLMConfigError
from assistant.settings import Settings, load_dotenv


def test_defaults_are_usable():
    s = Settings(api_key="k")
    assert s.base_url == "https://api.deepseek.com"
    assert s.model == "deepseek-chat"
    assert s.timeout == 30.0
    assert s.max_retries == 2


def test_frozen_cannot_be_modified():
    s = Settings(api_key="k")
    with pytest.raises(Exception):
        s.timeout = 99   # type: ignore[misc]


def test_api_key_hidden_in_repr():
    """坑 5 的回归测试：repr 不能泄露 Key。"""
    s = Settings(api_key="sk-super-secret")
    assert "sk-super-secret" not in repr(s)


def test_validate_rejects_bad_values():
    with pytest.raises(LLMConfigError, match="api_key"):
        Settings(api_key="").validate()
    with pytest.raises(LLMConfigError, match="base_url"):
        Settings(api_key="k", base_url="not-a-url").validate()
    with pytest.raises(LLMConfigError, match="timeout"):
        Settings(api_key="k", timeout=0).validate()
    with pytest.raises(LLMConfigError, match="max_retries"):
        Settings(api_key="k", max_retries=-1).validate()


def test_from_env_requires_key(monkeypatch):
    """没有 Key 时必须报清晰的错误（而不是 None 一路传下去）。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="DEEPSEEK_API_KEY"):
        Settings.from_env(dotenv_path=None)


def test_from_env_reads_values(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT", "12.5")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    s = Settings.from_env(dotenv_path=None)

    assert s.api_key == "sk-test"
    assert s.timeout == 12.5              # 字符串被正确转成 float
    assert isinstance(s.timeout, float)
    assert s.model == "deepseek-reasoner"


def test_env_var_wins_over_dotenv_file(monkeypatch, tmp_dir):
    """核心规则：真实环境变量优先于 .env（load_dotenv 用 setdefault）。"""
    dotenv = tmp_dir / ".env"
    dotenv.write_text("DEEPSEEK_API_KEY=from-file\nDEEPSEEK_MODEL=from-file\n", encoding="utf-8")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    s = Settings.from_env(dotenv_path=str(dotenv))

    assert s.api_key == "from-env"        # 环境变量赢
    assert s.model == "from-file"         # .env 补充没被覆盖的


def test_load_dotenv_ignores_comments_and_blank_lines(tmp_dir):
    dotenv = tmp_dir / ".env"
    dotenv.write_text("# 这是注释\n\nDEEPSEEK_MODEL=from-file\n", encoding="utf-8")

    os.environ.pop("DEEPSEEK_MODEL", None)
    try:
        load_dotenv(str(dotenv))
        assert os.environ.get("DEEPSEEK_MODEL") == "from-file"
    finally:
        os.environ.pop("DEEPSEEK_MODEL", None)
