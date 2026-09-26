"""Personal RAG（对应 projects/04-rag 的 10 章 milestone）。

分层（09 §3.1）：

    接入层  cli.py                                 命令行
    编排层  IngestionPipeline / RAGService         两条链路
    能力层  Retriever / BaseReranker / Assembler    Ch05-08 的零件
    模型层  BaseEmbeddingClient / BaseVectorStore   Ch03-04 的零件
    数据层  BaseParser / chunk_document / Chunk     Ch01-02 的零件

离线运行（不需要 API Key、不联网）：

    python -m rag.cli --index data/ --fake
    python -m rag.cli --ask "生成器为什么能省内存" --fake
"""

from .assembler import AssembledContext, Citation, ContextAssembler, RAG_SYSTEM_RULES
from .chunker import chunk_document, chunk_text, estimate_tokens, recursive_split
from .embedding import BaseEmbeddingClient, FakeEmbeddingClient, SiliconFlowEmbeddingClient
from .errors import (
    ConfigurationError,
    DependencyMissingError,
    EmbeddingError,
    EmbeddingRateLimitError,
    IngestionError,
    RAGError,
    RetrievalError,
    RerankError,
)
from .evaluation import EvalCase, EvalReport, evaluate
from .llm import BaseLLMClient, FakeLLMClient
from .models import Chunk, Document, ScoredChunk
from .parsing import BaseParser, MdParser, PdfParser, TxtParser, get_parser, parse_file
from .pipeline import IngestionPipeline, RAGAnswer, RAGService
from .retriever import Retriever, rrf_fuse
from .reranker import BaseReranker, FakeReranker, NoopReranker, SiliconFlowReranker
from .settings import RAGSettings
from .similarity import cosine_similarity, cosine_similarity_matrix, l2_distance
from .store import BaseVectorStore, InMemoryVectorStore

__version__ = "0.1.0"

__all__ = [
    # 数据模型
    "Document", "Chunk", "ScoredChunk",
    # 异常
    "RAGError", "IngestionError", "EmbeddingError", "EmbeddingRateLimitError",
    "RetrievalError", "RerankError", "ConfigurationError", "DependencyMissingError",
    # 配置
    "RAGSettings",
    # 01 摄入
    "BaseParser", "TxtParser", "MdParser", "PdfParser", "get_parser", "parse_file",
    # 02 切分
    "chunk_text", "chunk_document", "recursive_split", "estimate_tokens",
    # 03 向量化
    "BaseEmbeddingClient", "FakeEmbeddingClient", "SiliconFlowEmbeddingClient",
    # 04 向量库
    "BaseVectorStore", "InMemoryVectorStore",
    # 06 相似度
    "cosine_similarity", "cosine_similarity_matrix", "l2_distance",
    # 05 检索
    "Retriever", "rrf_fuse",
    # 07 精排
    "BaseReranker", "NoopReranker", "FakeReranker", "SiliconFlowReranker",
    # 08 组装
    "ContextAssembler", "AssembledContext", "Citation", "RAG_SYSTEM_RULES",
    # 09 流水线
    "IngestionPipeline", "RAGService", "RAGAnswer", "FakeLLMClient", "BaseLLMClient",
    # 10 评估
    "EvalCase", "EvalReport", "evaluate",
]
