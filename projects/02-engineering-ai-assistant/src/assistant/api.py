"""FastAPI 入口（对应 milestones/09-fastapi.md）。

设计约束：

- **本文件没有任何业务逻辑**：只做入参校验、调 service、包装响应
- HTTP client 在 lifespan 里创建一次并复用，退出时释放
- 所有路由都是 async，且内部没有同步阻塞调用
- 测试时用 dependency_overrides 换成 Fake，不联网

启动：

    uvicorn assistant.api:app --port 8000
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from assistant.client import DeepSeekClient
from assistant.errors import LLMError
from assistant.logging_setup import setup_logging
from assistant.service import AssistantService
from assistant.settings import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动时建 client（含连接池），关闭时释放 —— 对应 09 章 3.4。"""
    settings = Settings.from_env()
    setup_logging(settings.log_level, settings.json_logs)
    client = DeepSeekClient(settings)
    app.state.service = AssistantService(client, system_prompt=settings.system_prompt)
    app.state.settings = settings
    logger.info("服务启动完成: model=%s", settings.model)
    yield
    await app.state.service.aclose()
    logger.info("服务已关闭")


app = FastAPI(
    title="Engineering AI Assistant",
    description="Project 02 —— 把 AI CLI 工程化为异步、类型安全、可测试的 Python 应用",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],  # 前端 dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 依赖注入（测试时用 dependency_overrides 替换） ----


def get_service(request: Request) -> AssistantService:
    return request.app.state.service


# ---- 请求 / 响应模型（Pydantic 自动校验） ----


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="用户问题")
    session_id: str | None = Field(None, max_length=64, description="会话 ID（预留）")


class ChatResponse(BaseModel):
    reply: str
    model: str


# ---- 路由 ----


@app.get("/health")
async def health() -> dict[str, str]:
    """给 Docker / K8s 探活用。"""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    service: AssistantService = Depends(get_service),
) -> ChatResponse:
    try:
        reply = await service.ask(req.message)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    model = getattr(service._client, "settings", None)  # noqa: SLF001
    return ChatResponse(reply=reply, model=getattr(model, "model", "unknown"))


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    service: AssistantService = Depends(get_service),
) -> StreamingResponse:
    """SSE 流式输出：每段一个 data: 事件，最后 data: [DONE]。"""

    async def event_gen() -> AsyncIterator[str]:
        try:
            async for chunk in service.stream(req.message):
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except LLMError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/reset")
async def reset(service: AssistantService = Depends(get_service)) -> dict[str, str]:
    """清空对话历史。"""
    service.reset()
    return {"status": "reset"}
