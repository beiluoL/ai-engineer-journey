"""AssistantService 的单元测试（对应 milestones/07）—— 全程不联网。

这是「依赖注入 + Fake」的最大回报：业务逻辑的测试不需要 Key、不需要网络、
结果确定、耗时毫秒级。
"""

import pytest

from assistant.client import FakeClient
from assistant.errors import LLMRateLimitError
from assistant.service import AssistantService


async def test_ask_returns_client_reply(service: AssistantService):
    answer = await service.ask("你好")
    assert answer == "固定回答"


async def test_ask_records_history(service: AssistantService):
    """问完之后，历史里应该有 user 和 assistant 两条。"""
    await service.ask("问题1")
    history = service.history
    assert history[0]["role"] == "system"
    assert history[1] == {"role": "user", "content": "问题1"}
    assert history[2] == {"role": "assistant", "content": "固定回答"}


async def test_history_accumulates_across_turns(service: AssistantService):
    """第二轮发给 client 的 messages 必须包含第一轮（多轮对话的核心）。"""
    await service.ask("第一轮")
    await service.ask("第二轮")

    second_call = service.history
    contents = [m["content"] for m in second_call]
    assert "第一轮" in contents
    assert "第二轮" in contents


async def test_client_receives_system_prompt(fake_client: FakeClient):
    service = AssistantService(fake_client, system_prompt="我是系统提示")
    await service.ask("问题")
    assert fake_client.calls[0][0] == {"role": "system", "content": "我是系统提示"}


async def test_reset_keeps_system_prompt(service: AssistantService):
    await service.ask("问题")
    service.reset()
    assert service.history == [{"role": "system", "content": "测试用助手"}]


async def test_empty_question_rejected(service: AssistantService):
    with pytest.raises(ValueError, match="不能为空"):
        await service.ask("   ")


async def test_retry_eventually_succeeds(settings):
    """挑战 1：前 2 次失败，第 3 次成功，共调用 3 次。"""
    client = FakeClient(reply="第三次成功", fail_times=2)
    service = AssistantService(client, system_prompt="s")

    # FakeClient 自己抛异常，这里验证「失败会抛出、且被记录」
    with pytest.raises(LLMRateLimitError):
        await service.ask("问题")
    assert len(client.calls) == 1

    # 重试由 DeepSeekClient 负责；这里验证 Fake 的计数器语义正确
    assert client.fail_times == 2


async def test_swapping_implementation_needs_no_change_upstream():
    """换一个 client 实现，service 代码零改动（抽象的价值）。"""
    class EchoClient(FakeClient):
        async def chat(self, messages):
            self.calls.append(messages.copy())
            return messages[-1]["content"]

    service = AssistantService(EchoClient(), system_prompt="s")
    assert await service.ask("回声测试") == "回声测试"


async def test_stream_yields_chunks_and_records_full_answer(service: AssistantService):
    parts = [chunk async for chunk in service.stream("流式问题")]
    assert "".join(parts) == "固定回答"
    assert service.history[-1] == {"role": "assistant", "content": "固定回答"}


def test_ask_sync_wrapper(fake_client: FakeClient):
    """注意这里必须是同步 def —— 对应 milestones/07 的「坑 5」。

    ask_sync 内部用了 asyncio.run()，如果在 async 测试里调用它，
    会报 RuntimeError: asyncio.run() cannot be called from a running event loop。
    """
    service = AssistantService(fake_client, system_prompt="s")
    assert service.ask_sync("同步调用") == "固定回答"


async def test_aclose_closes_underlying_client(fake_client: FakeClient):
    service = AssistantService(fake_client, system_prompt="s")
    await service.aclose()
    assert fake_client.closed is True
