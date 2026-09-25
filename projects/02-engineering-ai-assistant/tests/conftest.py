"""共享 fixture（对应 milestones/07-testing-and-debugging.md）。

所有 fixture 都是 Fake，不联网、不花钱、不依赖真实 Key。
"""

import shutil
import uuid
from pathlib import Path

import pytest

from assistant.client import FakeClient
from assistant.service import AssistantService
from assistant.settings import Settings


@pytest.fixture
def tmp_dir():
    """测试用的临时目录，用完自动删除。

    标准写法是 pytest 内置的 tmp_path，但它在某些受限环境（容器 / 沙箱）下
    会在系统临时目录创建失败。这里退回到项目内的 tests/.tmp/，
    本机、CI、受限环境都能跑。
    """
    base = Path(__file__).parent / ".tmp"
    if not base.exists():          # 不用 mkdir(exist_ok=True)：部分环境会报 EEXIST
        base.mkdir()
    d = base / uuid.uuid4().hex[:8]
    d.mkdir(parents=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def settings() -> Settings:
    """一个假的但合法的配置。"""
    return Settings(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        timeout=5.0,
        max_retries=2,
        log_level="WARNING",   # 测试时少输出噪音
        system_prompt="测试用助手",
    )


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient(reply="固定回答")


@pytest.fixture
def service(fake_client: FakeClient) -> AssistantService:
    return AssistantService(fake_client, system_prompt="测试用助手")
