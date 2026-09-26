"""FastAPI 接入层（对应 milestones/04、09）。

职责边界：**零业务逻辑**。
只做三件事：校验入参 → 调 service → 包装响应。
业务逻辑全在 service / agent，所以 CLI 和 API 能复用同一套。
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from assistant.client import DeepSeekClient
from assistant.errors import LLMError
from assistant.logging_setup import setup_logging
from assistant.models import REGISTRY as MODEL_REGISTRY
from assistant.service import ChatService, build_service
from assistant.settings import Settings

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str = "default"
    profile: str | None = None


class StructuredRequest(ChatRequest):
    schema_name: str = "skill"


class ChatResponse(BaseModel):
    reply: str
    usage: dict[str, int] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：创建并复用一个客户端，退出时释放连接池。"""
    settings = Settings.from_env()
    setup_logging(settings.log_level, settings.json_logs)
    client = DeepSeekClient(settings)
    app.state.service = build_service(settings, client)
    try:
        yield
    finally:
        await client.aclose()


def get_service(request: Request) -> ChatService:
    """从 app.state 取 service。测试里用 dependency_overrides 换成 Fake。"""
    return request.app.state.service


def create_app() -> FastAPI:
    app = FastAPI(title="AI Application (Project 03)", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _handle(e: LLMError) -> None:
        logger.exception("业务异常")
        raise HTTPException(status_code=502, detail=str(e))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, service: ChatService = Depends(get_service)) -> Any:
        try:
            reply = await service.ask(req.message, req.session_id)
        except LLMError as e:
            return _handle(e)
        return {"reply": reply, "usage": service.usage.as_dict()}

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest, service: ChatService = Depends(get_service)):
        from fastapi.responses import StreamingResponse

        async def gen():
            try:
                async for delta in service.astream(req.message, req.session_id):
                    payload = json.dumps({"delta": delta}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            except LLMError as e:
                payload = json.dumps({"error": str(e)}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/chat/structured")
    async def chat_structured(
        req: StructuredRequest, service: ChatService = Depends(get_service)
    ) -> Any:
        model_cls = MODEL_REGISTRY.get(req.schema_name)
        if model_cls is None:
            raise HTTPException(
                status_code=400,
                detail=f"未知 schema {req.schema_name!r}，可选: {sorted(MODEL_REGISTRY)}",
            )
        try:
            result = await service.ask_structured(req.message, model_cls, req.session_id)
        except LLMError as e:
            return _handle(e)
        return {"data": result.model_dump(), "usage": service.usage.as_dict()}

    @app.post("/chat/agent", response_model=ChatResponse)
    async def chat_agent(req: ChatRequest, service: ChatService = Depends(get_service)) -> Any:
        try:
            reply = await service.run_agent(req.message, req.session_id)
        except LLMError as e:
            return _handle(e)
        return {"reply": reply, "usage": service.usage.as_dict()}

    @app.post("/reset")
    async def reset(session_id: str = "default", service: ChatService = Depends(get_service)) -> dict:
        service.reset(session_id)
        return {"reset": session_id}

    return app


app = create_app()
