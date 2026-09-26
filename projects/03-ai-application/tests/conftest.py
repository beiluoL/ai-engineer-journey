"""共享 fixture。

两条原则：
    1. 全部离线 —— 用 FakeClient，不联网、不花钱、不需要 Key
    2. 临时目录放项目内 —— 沙箱里 pytest 内置的 tmp_path 不可用
       （见 Project 02 踩坑记录：/private/var 下的 mkdir 会被拦）
"""

import shutil
import uuid
from pathlib import Path

import pytest

from assistant.client import FakeClient
from assistant.memory import Conversation
from assistant.service import ChatService
from assistant.settings import Settings


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def tmp_dir():
    """项目内的临时目录（沙箱 / 本机 / CI 都能用）。"""
    base = Path(__file__).parent / ".tmp"
    if not base.exists():
        base.mkdir(parents=True)
    d = base / uuid.uuid4().hex[:8]
    d.mkdir(parents=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def settings() -> Settings:
    return Settings(api_key="test-key")


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient(reply="固定回答")


@pytest.fixture
def service(fake_client, settings) -> ChatService:
    return ChatService(client=fake_client, settings=settings, system_prompt="你是测试助手。")
