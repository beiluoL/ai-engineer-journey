"""FastAPI 接入层（对应 milestone 13）。

职责边界和 P03 的 `assistant/api.py` 完全一致：**零业务逻辑**。
只做三件事：校验入参 → 调 service → 包装响应。
业务逻辑全在 `RAGService`，所以 CLI 与 Web API 复用同一套链路
（同一问法在两边得到的答案，逐字相同）。

端的划分：

    POST /ask         一次性返回答案 + 引用（脚本 / 移动端友好）
    POST /ask/stream  SSE 逐字推送（前端打字机效果）
    GET  /health      存活探针
    GET  /stats       当前索引规模（chunks / 模型名）
    POST /index       临时补建索引（内存向量库不跨进程，见 04 章坑 2）

SSE 信封沿用 P03 的写法：`data: {json}\\n\\n`，json 里用 kind 字段区分事件类型。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .assembler import ContextAssembler
from .cli import build_components
from .errors import RAGError
from .llm import FakeLLMClient
from .pipeline import RAGService

logger = logging.getLogger(__name__)

# 默认只索引 data/ 下的示例语料；想要别的目录在 /index 里显式传 paths
DEFAULT_INDEX_PATHS = ["data/"]


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    budget: int | None = None      # 覆盖本次的【参考资料】token 预算
    top_k: int | None = None       # 非 None 时按指定条数重跑检索


class AskResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    context_tokens: int = 0
    refused: bool = False


class IndexRequest(BaseModel):
    paths: list[str] = Field(default_factory=lambda: list(DEFAULT_INDEX_PATHS))


def _build_llm(fake: bool):
    """生成侧：fake 用离线替身，否则用 DeepSeek 真实模型。"""
    if fake:
        return FakeLLMClient()
    from .llm import DeepSeekLLMClient          # 真实 key 缺失时在这里才炸
    return DeepSeekLLMClient(api_key=os.environ.get("DEEPSEEK_API_KEY", ""))


def _make_lifespan(paths: list[str]):
    """启动建索引、关停清状态的生命周期。

    用工厂而不是直接写 async def lifespan()，因为是否需要预建索引取决于
    调用参数；内存向量库每次冷启动都是空的（04 章坑 2），所以这里默认先建。
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        fake = os.getenv("RAG_FAKE", "1") == "1"
        # fake 同时决定检索侧与生成侧：默认全离线，跑通了再把 RAG_FAKE=0
        # 换成真实 embedding + 真实 DeepSeek（环境变量一改即可，代码不动）。
        #
        # 坑：真实 embedding 客户端内部用 asyncio.run() 驱动 async httpx，
        # 而 uvicorn 的 lifespan 本身就跑在事件循环里 —— 直接调用会抛
        #     RuntimeError: asyncio.run() cannot be called from a running event loop
        # 把整段同步装配丢进线程池：线程里没有 running loop，asyncio.run 才合法。
        settings, embedding_client, store, retriever, service = await asyncio.to_thread(
            build_components, profile="dev", fake=fake, index_paths=paths,
            quiet=True, llm=_build_llm(fake),
        )
        app.state.store = store
        app.state.embedding_client = embedding_client
        app.state.settings = settings
        app.state.retriever = retriever
        app.state.service = service
        logger.info("RAG 服务启动：fake=%s，索引 %d 个路径 → %d chunks",
                    fake, len(paths), store.count())
        try:
            yield
        finally:
            app.state.service = None

    return lifespan


def create_app(index_paths: list[str] | None = None) -> FastAPI:
    """构造应用。`index_paths` 传给 lifespan，决定是否启动时先建索引。"""
    paths = list(index_paths if index_paths is not None else DEFAULT_INDEX_PATHS)
    app = FastAPI(title="Personal RAG API (Project 04)", version="0.1.0",
                  lifespan=_make_lifespan(paths))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_service(request: Request) -> RAGService:
        """从 app.state 取 service。测试里用 dependency_overrides 换成 Fake。

        参数类型必须写 `Request` —— 这是个踩过的坑：漏了注解时 FastAPI 会把
        `request` 当成**一个必需的 query 参数**，于是每个端点都开始要求
        `?request=xxx`，GET /stats 这种无参接口直接 422。
        """
        service = getattr(request.app.state, "service", None)
        if service is None:
            raise HTTPException(status_code=503, detail="服务尚未就绪")
        return service

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/stats")
    async def stats(request: Request) -> dict:
        store = getattr(request.app.state, "store", None)
        settings = getattr(request.app.state, "settings", None)
        return {
            "chunks": store.count() if store else 0,
            "embedding_model": (store.model_name if store else "") or settings.embedding_model,
            "top_k": settings.top_k if settings else 0,
        }

    @app.post("/ask", response_model=AskResponse)
    async def ask(req: AskRequest, service: RAGService = Depends(get_service)) -> AskResponse:
        # 同步链路 + 同步的 embedding 客户端（内部 run_sync → asyncio.run），
        # 在 async 端点里直接调用就会撞
        #     RuntimeError: asyncio.run() cannot be called from a running event loop
        # 所以整段丢线程池：线程里没有 running loop，且 I/O 等待也不会堵住事件循环。
        try:
            answer = await asyncio.to_thread(service.ask, req.query, req.budget)
        except RAGError as e:
            logger.warning("问答失败: %s", e)
            raise HTTPException(status_code=502, detail=str(e)) from e
        return AskResponse(
            answer=answer.answer,
            citations=[c.anchor() for c in answer.citations],
            sources=answer.retrieved_sources,
            context_tokens=answer.context_tokens,
            refused=answer.refused,
        )

    @app.post("/ask/stream")
    async def ask_stream(req: AskRequest,
                         service: RAGService = Depends(get_service)) -> StreamingResponse:
        async def gen() -> AsyncIterator[str]:
            try:
                async for event in _to_async(service.stream_answer(req.query, budget=req.budget)):
                    payload = json.dumps({"kind": event.kind, **event.payload},
                                         ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            except RAGError as e:
                payload = json.dumps({"kind": "error", "message": str(e)}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    @app.post("/index")
    async def index(req: IndexRequest, request: Request) -> dict:
        """临时补建索引。内存向量库每次进程启动都是空的，所以 API 侧留了这个口。"""
        from .parsing import PARSER_CLASSES, expand_paths
        from .pipeline import IngestionPipeline

        files = expand_paths(req.paths)
        if not files:
            raise HTTPException(status_code=400, detail=f"没有找到任何文件：{req.paths}")
        store = getattr(request.app.state, "store")
        embedding_client = getattr(request.app.state, "embedding_client")
        retriever = getattr(request.app.state, "retriever")

        def _ingest():
            pipeline = IngestionPipeline(list(PARSER_CLASSES), embedding_client,
                                         store, retriever)
            return pipeline.ingest(files)

        report = await asyncio.to_thread(_ingest)   # 同上：同步入库丢线程池
        return {
            "files_total": report.files_total, "files_ok": report.files_ok,
            "chunks_stored": report.chunks_stored,
            "failed": len(report.files_failed), "chunks": store.count(),
        }

    return app


def _to_async(gen: Iterator) -> AsyncIterator:
    """把同步生成器桥成 async 生成器 —— 13 章最容易被忽略的一处。

    `RAGService.stream_answer` 和 `httpx.Client` 都是**同步**的。在 FastAPI 的
    async 端点里直接 for 循环去拉，会把整个事件循环堵死：此时同一个进程里
    其他请求的 /health 都会超时，而你的服务其实只是等着一个 HTTP 响应。

    所以每个 `next()` 都丢进线程池执行，事件循环该转还转。
    代价是一次一线程切换；token 特别碎时（真实模型一帧几字节）可以改成
    「整体丢一个线程 + 队列」的版本，取舍写在 13 章。
    """
    loop = asyncio.get_running_loop()
    sentinel = object()

    def _next():
        return next(gen, sentinel)

    async def wrapper() -> AsyncIterator:
        while True:
            item = await loop.run_in_executor(None, _next)
            if item is sentinel:
                break
            yield item

    return wrapper()


app = create_app()
