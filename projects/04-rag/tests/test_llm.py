"""llm.py：生成侧离线替身。

它替代不了真实模型，但要让「引用随答案一起产出」和「宁可拒答也不编」这两件事
在没有 API Key 的情况下也能被测到。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.assembler import ContextAssembler
from rag.cli import build_components
from rag.errors import RAGError
from rag.llm import DeepSeekLLMClient, FakeLLMClient, parse_answer_refs
from rag.pipeline import RAGService
from rag.retriever import Retriever
from rag.reranker import NoopReranker
from rag.settings import RAGSettings

DATA_DIR = str(Path(__file__).resolve().parents[1] / "data")


def _ask(question: str, max_sentences: int = 6):
    settings, _emb, store, retriever, _svc = build_components(
        profile="dev", fake=True, top_k=5, index_paths=[DATA_DIR])
    return RAGService(
        retriever=retriever,
        reranker=NoopReranker(),
        assembler=ContextAssembler(min_score=settings.min_score),
        llm=FakeLLMClient(max_sentences=max_sentences),
        settings=settings,
    ).ask(question)


def test_回答里带上引用编号与来源():
    answer = _ask("生成器为什么能省内存")
    assert "[1]" in answer.answer or "来源" in answer.answer
    assert "python-generators.md" in answer.answer


def test_不用标题行当答案():
    answer = _ask("生成器为什么能省内存")
    for line in answer.answer.split("："):
        assert not line.strip().startswith("#")     # "## 为什么能省内存" 不能出现在回答里


def test_资料与问题无关时拒答():
    answer = _ask("今天上海天气怎么样")
    assert answer.refused


def test_组装的参考资料被完整读到():          # 回归：正则只截到块的第一行时这里会挂
    settings, _emb, _store, retriever, _svc = build_components(
        profile="dev", fake=True, top_k=5, index_paths=[DATA_DIR])
    ctx = ContextAssembler().build("生成器", retriever.retrieve("生成器", top_k=3), 6000)
    answer = FakeLLMClient().chat(
        [{"role": "system", "content": ctx.context_text},
         {"role": "user", "content": "生成器"}])
    assert "yield" in answer                       # 正文第 6 行才有 yield，标题行没有


def test_空资料直接拒答():
    answer = FakeLLMClient().chat(
        [{"role": "system", "content": "【参考资料】\n（无）"},
         {"role": "user", "content": "生成器"}])
    assert "无法回答" in answer


# --------------------------------------------------------------------------
# 真实客户端：不联网，用假 httpx 顶替，只验证「请求怎么发的、结果怎么取的」
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """替换 httpx.Client，把请求体记下来再返回预设响应。"""

    instances: list["_FakeClient"] = []

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.payload: dict = {}
        _FakeClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def post(self, url, headers=None, json=None):     # noqa: A002 - 对齐 httpx 签名
        self.url = url
        self.headers = headers
        self.payload = json or {}
        if self.payload.get("__fail__"):
            return _FakeResponse({"error": "boom"}, status=500)
        return _FakeResponse({"choices": [{"message": {"role": "assistant",
                                                       "content": "WIN"}}],
                              "usage": {"prompt_tokens": 7,
                                        "completion_tokens": 2,
                                        "total_tokens": 9}})


@pytest.fixture
def fake_httpx(monkeypatch):
    _FakeClient.instances = []
    monkeypatch.setattr("httpx.Client", _FakeClient)
    return _FakeClient


def test_真实客户端_发出去的请求符合openai协议(fake_httpx):
    client = DeepSeekLLMClient(api_key="sk-test")
    out = client.chat([{"role": "user", "content": "hi"}])
    sent = _FakeClient.instances[0]
    assert out == "WIN"
    assert sent.url == "https://api.deepseek.com/chat/completions"
    assert sent.headers["Authorization"] == "Bearer sk-test"
    assert sent.payload["model"] == "deepseek-chat"
    assert sent.payload["temperature"] == 0.0      # RAG 默认要可复现
    assert sent.payload["stream"] is False


def test_超时必须显式设置():
    """httpx 默认 5s 对生成接口远远不够（12 章坑 1）。"""
    client = DeepSeekLLMClient(api_key="sk-test")
    assert client.timeout == 60.0
    with pytest.raises(RAGError):                  # 没 key 必须当场炸，不许糊默认值
        DeepSeekLLMClient(api_key="")


def test_usage_被记下来供日志与计费(fake_httpx):
    client = DeepSeekLLMClient(api_key="sk-test")
    client.chat([{"role": "user", "content": "hi"}])
    assert client.last_usage == {"prompt_tokens": 7, "completion_tokens": 2,
                                "total_tokens": 9}


def test_接口报错时抛RAGError而不是返回空串(fake_httpx, monkeypatch):
    class _Fail(_FakeClient):
        def post(self, url, headers=None, json=None):  # noqa: A002
            return _FakeResponse({"error": "boom"}, status=500)

    monkeypatch.setattr("httpx.Client", _Fail)
    with pytest.raises(RAGError):
        DeepSeekLLMClient(api_key="sk-test").chat(
            [{"role": "user", "content": "hi"}])
    # 契约：失败要抛，绝不能返回 "" —— 空串会让上层误以为模型答了「不知道」


def test_parse_answer_refs_去重并保持出现顺序():
    assert parse_answer_refs("[3] 这是一个 [1] 测试 [3]") == [3, 1]
    assert parse_answer_refs("没有编号的一句话") == []
    assert parse_answer_refs("") == []
