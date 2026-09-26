"""llm.py：生成侧离线替身。

它替代不了真实模型，但要让「引用随答案一起产出」和「宁可拒答也不编」这两件事
在没有 API Key 的情况下也能被测到。
"""

from __future__ import annotations

from pathlib import Path

from rag.assembler import ContextAssembler
from rag.cli import build_components
from rag.llm import FakeLLMClient
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
