"""pipeline.py：两条链路 + 三条失败语义（09 章）。

三条失败语义是最值得写测试的地方：它们决定的不是"功能对不对"，
而是"出故障时会不会悄悄给错答案"。
"""

from __future__ import annotations

import pytest

from rag.assembler import ContextAssembler
from rag.cli import build_components
from rag.embedding import FakeEmbeddingClient
from rag.errors import RAGError
from rag.llm import BaseLLMClient
from rag.pipeline import IngestionPipeline, RAGService
from rag.reranker import NoopReranker
from rag.retriever import Retriever
from rag.settings import RAGSettings
from rag.store import InMemoryVectorStore


class RecordingLLM(BaseLLMClient):
    """记录被调用的次数：用来验证「检索为空时不调 LLM」。"""

    model_name = "recording"

    def __init__(self, fail_times: int = 0):
        self.calls = 0
        self.fail_times = fail_times

    def chat(self, messages):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("模拟 LLM 超时")
        return "这是回答"


@pytest.fixture()
def offline(corpus_dir):
    """「建好索引的插件」装置：settings / embedding / store / retriever / 默认 settings。"""
    settings, embedding, store, retriever, _svc = build_components(
        profile="dev", fake=True, top_k=5, index_paths=[str(corpus_dir)])
    # build_components 只按 profile 给参数，ingest 会重新校验一次，这里补一份默认配置
    return settings, embedding, store, retriever, RAGSettings().validate()


def test_ingest_成功建索引并给出报告(offline, corpus_dir):
    settings, embedding, store, retriever, _ = offline
    from rag.parsing import PARSER_CLASSES, expand_paths

    store.clear()
    report = IngestionPipeline(list(PARSER_CLASSES), embedding, store,
                               retriever).ingest(expand_paths([str(corpus_dir)]))
    assert report.files_ok == 2 and not report.files_failed
    assert report.chunks_stored == store.count() > 0


def test_ingest_单文件失败不拖垮整批(offline, workdir, corpus_dir):
    settings, embedding, store, retriever, _default = offline
    bad = workdir / "broken.txt"
    bad.write_text("正常内容", encoding="utf-8")

    class BadParser:
        supported_extensions = (".txt",)

        def __init__(self):
            self.calls = 0

        def supports(self, path):
            return True

        def parse(self, path):
            self.calls += 1
            if str(path) == str(bad):
                raise RuntimeError("磁盘错误")
            from rag.parsing import get_parser

            return get_parser(path).parse(path)

    pipeline = IngestionPipeline([BadParser()], embedding, store, retriever)
    report = pipeline.ingest([bad, corpus_dir / "python-gil.txt"])
    assert report.files_failed and report.files_ok == 1       # 失败的被记下来，其余照走


def test_ingest_是幂等的_重复摄入不翻倍(offline, corpus_dir):
    settings, embedding, store, retriever, _ = offline
    before = store.count()
    from rag.parsing import expand_paths

    pipeline = IngestionPipeline([], embedding, store, retriever)
    files = expand_paths([str(corpus_dir)])
    pipeline.ingest(files)
    assert store.count() == before                            # doc_id 幂等覆盖


def test_ask_端到端给出回答与引用(offline):
    settings, embedding, store, retriever, _svc = offline
    llm = RecordingLLM()
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=0.2), llm=llm,
                         settings=settings)
    answer = service.ask("生成器省内存")
    assert answer.answer == "这是回答"
    assert answer.citations and answer.used_chunks
    assert answer.context_tokens > 0
    assert answer.retrieved_sources
    assert llm.calls == 1


def test_失败语义2_检索为空时不调llm(offline):
    settings, embedding, store, retriever, _svc = offline
    llm = RecordingLLM()
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=0.99),   # 全部被阈值筛掉
                         llm=llm, settings=settings)
    answer = service.ask("生成器省内存")
    assert llm.calls == 0                                    # 省下一整次 LLM 调用
    assert answer.refused
    assert answer.answer == "知识库中没有相关资料，无法回答这个问题。"


def test_失败语义3_llm失败重试一次仍失败要明确报错(offline):
    settings, embedding, store, retriever, _svc = offline
    llm = RecordingLLM(fail_times=2)                          # 两次都失败
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=0.2), llm=llm,
                         settings=settings)
    with pytest.raises(RAGError):
        service.ask("生成器省内存")
    assert llm.calls == 2                                    # 确实只重试了一次


def test_budget参数可覆盖settings(offline):
    settings, embedding, store, retriever, _svc = offline
    llm = RecordingLLM()
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=0.2), llm=llm,
                         settings=settings)
    big = service.ask("生成器省内存", budget=10_000)
    small = service.ask("生成器省内存", budget=1)
    assert big.context_tokens >= small.context_tokens


def test_离线装置本身可用(offline):                             # 保护 demo 依赖的组合
    settings, embedding, store, retriever, _svc = offline
    assert isinstance(embedding, FakeEmbeddingClient)
    assert isinstance(store, InMemoryVectorStore)
    assert isinstance(retriever, Retriever)
    assert store.count() > 0
