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
from rag.pipeline import IngestionPipeline, RAGService, looks_refused
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


# ---------------------------------------------------------------------------
# 流式问答（13 章）：一次性与流式必须共用同一段检索
# ---------------------------------------------------------------------------

def _stream_events(comp, llm, query="生成器为什么能省内存？", min_score=None, **kw):
    """comp = offline 夹具的返回值（不能在这里解包，会比 pytest 先执行）。

    min_score 可以单独抬高 —— 因为 FakeEmbeddingClient 对任何查询都召回东西，
    "检索为空"在离线下只能靠把阈值抬到不可能达到来构造（11 章的发现）。
    """
    settings, embedding, store, retriever, _svc = comp
    threshold = settings.min_score if min_score is None else min_score
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=threshold),
                         llm=llm, settings=settings)
    return [ev for ev in service.stream_answer(query, **kw)]


def test_stream事件序列为retrieved_delta_done(offline):
    llm = RecordingLLM()
    kinds = [ev.kind for ev in _stream_events(offline, llm)]
    assert kinds[0] == "retrieved"
    assert kinds[-1] == "done"
    assert set(kinds[1:-1]) == {"delta"}


def test_流式与一次性拿到同一份参考资料(offline):
    """两条路共用 _prepare()：system_prompt 必须逐字相同。"""
    settings, embedding, store, retriever, _svc = offline
    llm = RecordingLLM()
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=settings.min_score),
                         llm=llm, settings=settings)
    q = "生成器为什么能省内存？"
    once = service.ask(q)
    streamed = [ev for ev in service.stream_answer(q)]
    meta = next(ev for ev in streamed if ev.kind == "retrieved")
    done = next(ev for ev in streamed if ev.kind == "done")
    assert meta.payload["context_tokens"] == once.context_tokens
    assert meta.payload["sources"] == once.retrieved_sources
    assert done.payload["answer"] == once.answer


def test_逐帧增量累加等于最终答案(offline):
    from rag.llm import FakeLLMClient   # 它按句产出多帧，才能验证「一帧一句」
    llm = FakeLLMClient()
    parts = [ev.payload["text"] for ev in _stream_events(offline, llm) if ev.kind == "delta"]
    done = next(ev for ev in _stream_events(offline, llm) if ev.kind == "done")
    assert len(parts) > 1                      # 确实分成了多帧
    assert "".join(parts) == done.payload["answer"]
    # 帧与帧之间不能是重复内容（累积前缀会让前端读到同一段两遍）


def test_检索为空时流式直接拒答且不吐delta(offline):
    class SilentLLM(RecordingLLM):
        def chat(self, messages):          # 被调用就说明闸门漏了
            self.calls += 1
            return "我不该被调用"

    llm = SilentLLM()
    events = _stream_events(offline, llm, query="生成器省内存", min_score=1.01)
    kinds = [ev.kind for ev in events]
    assert kinds == ["done"]
    assert events[0].payload["refused"] is True
    assert llm.calls == 0


def test_拒答判据能认出被改写的话术():
    """真实模型不会原样复述拒答话术（实测它只回「知识库中没有相关资料。」）。"""
    assert looks_refused("知识库中没有相关资料。")
    assert looks_refused("抱歉，我无法回答这个问题。")
    assert not looks_refused("生成器是边算边吐的 [1]。")
    assert not looks_refused("")


def test_流式done的refused与一次性答案一致(offline):
    settings, embedding, store, retriever, _svc = offline
    llm = RecordingLLM()
    service = RAGService(retriever=retriever, reranker=NoopReranker(),
                         assembler=ContextAssembler(min_score=settings.min_score),
                         llm=llm, settings=settings)
    q = "生成器为什么能省内存？"
    once = service.ask(q)
    events = list(service.stream_answer(q))
    assert events[-1].payload["refused"] == once.refused
