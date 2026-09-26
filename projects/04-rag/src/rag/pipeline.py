"""两条链路（对应 milestone 09）。

RAG = 多了索引链路的 chat 应用。这两条链的触发时机、失败语义、性能要求全都不一样：

    离线索引链路（可以慢，可以定时跑）：
        ingest(paths) → parse → chunk_document → embed → store
    在线问答链路（每次请求都要快）：
        ask(query) → retrieve → rerank → assemble → llm → answer + citations

失败语义必须分开定义（09 §3.3）：
    1. 索引失败 → 捕获、记日志、跳过该文件继续处理其余文件；问答服务不受影响
    2. 检索为空 → 不调 LLM，直接返回「知识库中没有相关资料」（省钱 + 防幻觉）
    3. LLM 失败 → 重试一次，仍失败则明确报错，绝不返回空字符串
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .assembler import RAG_SYSTEM_RULES, AssembledContext, ContextAssembler
from .chunker import chunk_document
from .embedding import BaseEmbeddingClient, run_sync
from .errors import RAGError
from .models import Chunk
from .parsing import BaseParser
from .retriever import Retriever
from .reranker import BaseReranker
from .settings import RAGSettings
from .store import BaseVectorStore

logger = logging.getLogger(__name__)

NO_RESULT_ANSWER = "知识库中没有相关资料，无法回答这个问题。"

# 拒答判据用「关键词命中」而不是「等于某个字符串」。
# 真实模型不会原样复述拒答话术 —— 它更常回一句「知识库中没有相关资料。」
# （只有半句）。字符串完全匹配会漏掉这类改写，于是前端拿到 refused=False，
# 却已经把「我不知道」当答案展示出去了。宁可放宽匹配，也不要漏判。
REFUSAL_MARKERS = ("无法回答", "知识库中没有相关资料", "没有相关资料",
                   "没有找到相关资料", "资料中没有")


def looks_refused(text: str) -> bool:
    return any(marker in (text or "") for marker in REFUSAL_MARKERS)


@dataclass(frozen=True)
class IngestReport:
    """一次索引的战果报告。files_failed 非空代表有文件被跳过。"""

    files_total: int = 0
    files_ok: int = 0
    files_failed: list[str] = field(default_factory=list)
    chunks_stored: int = 0
    docs_total: int = 0
    docs_skipped: int = 0


class IngestionPipeline:
    """离线索引链路。"""

    def __init__(
        self,
        parsers: list[BaseParser],
        embedding_client: BaseEmbeddingClient,
        vector_store: BaseVectorStore,
        retriever: Retriever | None = None,
    ) -> None:
        self._parsers = parsers
        self._embedding = embedding_client
        self._store = vector_store
        self._retriever = retriever

    @classmethod
    def from_settings(cls, settings: RAGSettings, embedding_client, vector_store,
                      retriever=None) -> "IngestionPipeline":
        from .parsing import PARSER_CLASSES  # 注册表：默认支持全部格式

        return cls(list(PARSER_CLASSES), embedding_client, vector_store, retriever)

    def ingest(self, paths: list[Path], size: int | None = None,
               overlap: int | None = None) -> IngestReport:
        """把一批文件建进向量库。单文件失败不拖垮整批。"""
        settings = RAGSettings().validate()
        size = size if size is not None else settings.chunk_size
        overlap = overlap if overlap is not None else settings.chunk_overlap

        all_chunks: list[Chunk] = []
        docs_total = docs_ok = 0
        failed: list[str] = []
        for path in paths:
            parser = self._find_parser(path)
            if parser is None:
                failed.append(f"{path}: 无可用 parser")
                continue
            try:
                docs = parser.parse(path)
            except Exception as e:  # noqa: BLE001 - 09 章失败语义 1
                logger.warning("解析失败，跳过文件: %s (%s)", path, e)
                failed.append(str(path))
                continue
            docs_total += len(docs)
            docs_ok += 1
            for doc in docs:
                try:
                    all_chunks.extend(chunk_document(doc, size=size, overlap=overlap))
                except Exception as e:  # noqa: BLE001
                    logger.warning("切分失败，跳过文档: %s (%s)", doc.source, e)

        if not all_chunks:
            return IngestReport(files_total=len(paths), files_ok=len(paths) - len(failed),
                                files_failed=failed, chunks_stored=0,
                                docs_total=docs_total, docs_skipped=docs_ok)

        # 批量嵌入：一次 HTTP 往返处理全部 chunk（03 §3.2）
        vectors = run_sync(self._embedding.embed([c.text for c in all_chunks]))
        for chunk, vec in zip(all_chunks, vectors):    # 主键 = chunk_id → 重复 ingest 幂等
            self._store.add([chunk], [vec], model=self._embedding.model_name)
        if self._retriever is not None:
            self._retriever.index(all_chunks)          # 顺手建关键词索引（hybrid 用）

        return IngestReport(
            files_total=len(paths),
            files_ok=len(paths) - len(failed),
            files_failed=failed,
            chunks_stored=len(all_chunks),
            docs_total=docs_total,
            docs_skipped=docs_total - docs_ok,
        )

    def _find_parser(self, path: Path) -> BaseParser | None:
        """注册表里存的是类，这里统一实例化后再返回（支持的判断是 classmethod）。"""
        holder = next((p for p in self._parsers if p.supports(path)), None)
        if holder is None:
            return None
        return holder() if isinstance(holder, type) else holder


@dataclass(frozen=True)
class RAGAnswer:
    """一次问答的结果。10 章的评估只依赖这个对象的公开字段。"""

    answer: str
    citations: list = field(default_factory=list)
    context_tokens: int = 0
    retrieved_sources: list[str] = field(default_factory=list)
    used_chunks: list = field(default_factory=list)
    # 12 章：把真正发给模型的 system 内容留档。RAG 最难复现的 bug 是
    # 「模型答的不是我喂给它的那段」，留档之后可以原样回放给模型自己判。
    system_prompt: str = ""

    @property
    def refused(self) -> bool:
        return looks_refused(self.answer)


@dataclass(frozen=True)
class _PreparedQuery:
    """ask() 与 stream_answer() 的中间产物，两者共用同一段检索 + 组装。"""

    query: str
    messages: list
    context: AssembledContext
    system: str
    retrieved: list = field(default_factory=list)


@dataclass(frozen=True)
class AnswerEvent:
    """流式问答的一次事件 —— 它就是 SSE 每帧的 payload（13 章的接口契约）。

    kind 取值固定四种：
        "retrieved"  检索完成，带上来源与引用（前端可以先把「已找到资料」显示出来）
        "delta"      增量文本，前端往缓冲区里追加
        "done"       完整答案 + citations，前端一次性提交
        "error"      生成失败，前端按错误提示兜底
    """

    kind: str
    payload: dict = field(default_factory=dict)


class RAGService:
    """在线问答链路。构造时注入的依赖决定「有没有 rerank / 用哪个向量库」，
    pipeline 代码本身不感知（依赖倒置）。"""

    def __init__(self, retriever: Retriever, reranker: BaseReranker,
                 assembler: ContextAssembler, llm, settings: RAGSettings | None = None
                 ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._assembler = assembler
        self._llm = llm
        self.settings = settings or RAGSettings()

    def _prepare(self, query: str, budget: int | None = None) -> _PreparedQuery:
        """ask() 与 stream_answer() 共用的「检索 + 组装」段。

        拆出来是为了让两条出路（一次性、流式）的**前置行为完全一致**：
        同样是 top_k、同样过 min_score、同样受 token 预算约束。一旦有人改了
        其中一条路而忘了另一条，必然出现「流式答的和一次性答的不是一回事」。
        """
        settings = self.settings
        budget = budget if budget is not None else settings.budget_tokens

        mode = "hybrid" if settings.hybrid else "vector"
        scored = self._retriever.retrieve(
            query, top_k=settings.fetch_k, mode=mode, mmr=settings.mmr)

        if settings.enable_rerank and self._reranker is not None:
            scored = self._reranker.rerank(query, scored, top_n=settings.rerank_top_n)
        scored = scored[: settings.top_k]

        ctx: AssembledContext = self._assembler.build(query, scored, budget)

        system = RAG_SYSTEM_RULES + "【参考资料】\n" + ctx.context_text
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]
        return _PreparedQuery(query=query, messages=messages, context=ctx,
                              system=system, retrieved=scored)

    @staticmethod
    def _refused_answer(ctx: AssembledContext) -> RAGAnswer:
        """失败语义 2：检索为空 → 不调 LLM，直接拒答（省钱 + 防幻觉）。"""
        return RAGAnswer(answer=NO_RESULT_ANSWER, citations=[],
                         context_tokens=ctx.context_tokens, retrieved_sources=[],
                         used_chunks=[])

    def ask(self, query: str, budget: int | None = None) -> RAGAnswer:
        prepared = self._prepare(query, budget)
        ctx = prepared.context
        # 失败语义 2
        if not ctx.used_chunks:
            return self._refused_answer(ctx)

        # 失败语义 3：生成失败重试一次，仍失败要报错，绝不返回空字符串
        try:
            answer = self._llm.chat(prepared.messages)
        except RAGError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 调用失败，重试一次: %s", e)
            try:
                answer = self._llm.chat(prepared.messages)
            except Exception as e2:  # noqa: BLE001
                raise RAGError(f"LLM 调用失败（已重试一次）: {e2}") from e2

        return RAGAnswer(
            answer=answer,
            citations=ctx.citations,
            context_tokens=ctx.context_tokens,
            retrieved_sources=[sc.chunk.source for sc in ctx.used_chunks],
            used_chunks=ctx.used_chunks,
            system_prompt=prepared.system,
        )

    def stream_answer(self, query: str, budget: int | None = None,
                      ) -> Iterator[AnswerEvent]:
        """流式版 ask()：产出一串事件，交给 API 层封装成 SSE（13 章）。

        事件顺序是契约，前端照着消费即可：
            retrieved → (delta * N) → done
            检索为空        → 直接 done(refused=True)，一次 LLM 都不调
            生成中途失败     → error，然后结束
        """
        prepared = self._prepare(query, budget)
        ctx = prepared.context
        sources = [sc.chunk.source for sc in ctx.used_chunks]

        if not ctx.used_chunks:
            yield AnswerEvent("done", {"answer": NO_RESULT_ANSWER, "refused": True,
                                       "citations": [], "sources": [],
                                       "context_tokens": ctx.context_tokens})
            return

        yield AnswerEvent("retrieved", {
            "query": query,
            "context_tokens": ctx.context_tokens,
            "sources": sources,
            "citations": [c.anchor() for c in ctx.citations],
        })

        buf: list[str] = []
        sent_any = False
        try:
            for tok in self._llm.iter_tokens(prepared.messages):
                if not tok:
                    continue
                buf.append(tok)
                sent_any = True
                yield AnswerEvent("delta", {"text": tok})
        except RAGError:
            raise
        except Exception as e:  # noqa: BLE001
            # 失败语义 3 在流式下的特殊之处：已经吐出去的 delta 收不回来。
            # 此时再「重试一次」只会让前端拿到两段拼起来的内容，
            # 所以只在「一个字都没吐」时才重试。
            if sent_any:
                logger.warning("LLM 流式生成中断（已发出部分内容）: %s", e)
            else:
                logger.warning("LLM 调用失败，重试一次: %s", e)
                try:
                    for tok in self._llm.iter_tokens(prepared.messages):
                        if not tok:
                            continue
                        buf.append(tok)
                        yield AnswerEvent("delta", {"text": tok})
                except Exception as e2:  # noqa: BLE001
                    yield AnswerEvent("error", {"message": str(e2)})
                    return

        answer = "".join(buf)
        yield AnswerEvent("done", {
            "answer": answer,
            "refused": looks_refused(answer),
            "citations": [c.anchor() for c in ctx.citations],
            "sources": sources,
            "context_tokens": ctx.context_tokens,
        })
