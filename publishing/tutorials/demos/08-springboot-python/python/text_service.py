"""用 FastAPI 把 Python 能力暴露成 HTTP 服务，供 Spring Boot 调用。

运行：
    uvicorn text_service:app --host 127.0.0.1 --port 8000

自测：
    curl -s http://127.0.0.1:8000/health
    curl -s -X POST http://127.0.0.1:8000/v1/analyze \
         -H 'Content-Type: application/json' \
         -d '{"text":"Spring Boot calls Python. Python answers.","top_k":3}'

这个 demo 刻意只用标准库做文本统计，不依赖任何模型，
目的是让「Java → HTTP → Python」这条链路本身可跑、可观测、无外部依赖。
真实场景里把 analyze() 换成你的 embedding / 推理 / 数据处理函数即可。
"""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="text-service", version="1.0.0")

# 英文停用词，避免 top_words 全是 the / is / and
STOP_WORDS = {
    "the", "is", "a", "an", "and", "or", "of", "to", "in", "on", "it",
    "that", "this", "for", "with", "as", "be", "are", "was", "were",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    top_k: int = Field(default=5, ge=1, le=50)


class AnalyzeResponse(BaseModel):
    chars: int
    words: int
    sentences: int
    top_words: list[list[Any]]
    elapsed_ms: float
    engine: str


def analyze_text(text: str, top_k: int) -> dict[str, Any]:
    """纯 Python 实现：字数 / 词频 / 句数。真实项目里换成你的模型调用。"""
    started = time.perf_counter()

    words = TOKEN_RE.findall(text)
    counter = Counter(w.lower() for w in words if w.lower() not in STOP_WORDS)
    sentences = len([s for s in re.split(r"[.!?。！？]+", text) if s.strip()])

    return {
        "chars": len(text),
        "words": len(words),
        "sentences": sentences,
        "top_words": [[w, c] for w, c in counter.most_common(top_k)],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "engine": "python-fastapi",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Java 侧做健康检查 / 容器探针就用这个端点。"""
    return {"status": "ok", "engine": "python-fastapi", "version": "1.0.0"}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    return analyze_text(req.text, req.top_k)
