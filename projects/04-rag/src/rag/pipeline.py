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
        return NO_RESULT_ANSWER in self.answer


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

    def ask(self, query: str, budget: int | None = None) -> RAGAnswer:
        settings = self.settings
        budget = budget if budget is not None else settings.budget_tokens

        mode = "hybrid" if settings.hybrid else "vector"
        scored = self._retriever.retrieve(
            query, top_k=settings.fetch_k, mode=mode, mmr=settings.mmr)

        if settings.enable_rerank and self._reranker is not None:
            scored = self._reranker.rerank(query, scored, top_n=settings.rerank_top_n)
        scored = scored[: settings.top_k]

        ctx: AssembledContext = self._assembler.build(query, scored, budget)

        # 失败语义 2：检索为空（分数全低于 min_score 或被预算截断）→ 不调 LLM
        if not ctx.used_chunks:
            return RAGAnswer(answer=NO_RESULT_ANSWER, citations=[],
                             context_tokens=ctx.context_tokens, retrieved_sources=[],
                             used_chunks=[])

        system = RAG_SYSTEM_RULES + "【参考资料】\n" + ctx.context_text
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]
        # 失败语义 3：生成失败重试一次，仍失败要报错，绝不返回空字符串
        try:
            answer = self._llm.chat(messages)
        except RAGError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 调用失败，重试一次: %s", e)
            try:
                answer = self._llm.chat(messages)
            except Exception as e2:  # noqa: BLE001
                raise RAGError(f"LLM 调用失败（已重试一次）: {e2}") from e2

        return RAGAnswer(
            answer=answer,
            citations=ctx.citations,
            context_tokens=ctx.context_tokens,
            retrieved_sources=[sc.chunk.source for sc in ctx.used_chunks],
            used_chunks=ctx.used_chunks,
            system_prompt=system,
        )
