#!/usr/bin/env python3
"""FastAPI 博客 API —— python-practice/04-fastapi-blog

任务卡：python-practice/04-fastapi-blog/README.md

如果你写 Java / Spring Boot，这个文件几乎是逐条对得上的：

    Spring Boot                      FastAPI
    ───────────────────────────────  ──────────────────────────────────────
    @RestController                  app = FastAPI(...)
    @GetMapping("/posts/{id}")       @app.get("/posts/{post_id}")
    @PathVariable Long id            def read(post_id: int)   ← 类型即校验
    @RequestBody @Valid PostDTO      def create(payload: PostCreate)
    @ResponseStatus(CREATED)         status_code=201
    @ExceptionHandler + 404          raise HTTPException(404, ...)
    @Autowired PostRepository        store: PostStore = Depends(get_store)
    springdoc-openapi / Swagger UI   /docs（自带，无需引依赖）

启动：
    python3 -m uvicorn app:app --reload --port 8130
    # 打开 http://127.0.0.1:8130/docs 就是可交互的 API 文档
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from store import Post, PostStore

DB_PATH = Path(os.environ.get("BLOG_DB") or Path(__file__).with_name("blog.db"))

TAGS_MAX = 5


# ---------------------------------------------------------------------------
# 数据模型（= DTO）。pydantic 负责校验，校验失败 FastAPI 自动返回 422。
# ---------------------------------------------------------------------------


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120, description="标题，1~120 字")
    content: str = Field(min_length=1, description="正文，不能为空")
    author: str = Field(default="匿名", max_length=40, description="作者")
    tags: list[str] = Field(default_factory=list, max_length=TAGS_MAX, description="标签")


class PostUpdate(BaseModel):
    """局部更新：字段全部可选，只改传进来的那些。"""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1)
    author: str | None = Field(default=None, max_length=40)
    tags: list[str] | None = Field(default=None, max_length=TAGS_MAX)


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    author: str
    tags: list[str]
    created_at: str
    updated_at: str

    @classmethod
    def of(cls, post: Post) -> "PostOut":
        return cls(
            id=post.id,
            title=post.title,
            content=post.content,
            author=post.author,
            tags=post.tags,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )


class HealthOut(BaseModel):
    status: str
    posts: int


# ---------------------------------------------------------------------------
# 依赖注入：把「仓库」挂在 app.state 上，请求处理函数通过 Depends 拿
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用启动/关闭钩子 —— 相当于 Spring 的 @PostConstruct / @PreDestroy。"""
    app.state.store = PostStore(DB_PATH)
    yield
    app.state.store.close()


app = FastAPI(
    title="山间书局博客 API",
    version="1.0.0",
    description="一个用来练手的 REST API：文章增删改查 + 校验 + 搜索。",
    lifespan=lifespan,
)


def get_store(request: Request) -> PostStore:
    return request.app.state.store


StoreDep = Depends(get_store)


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@app.get("/", summary="服务简介")
def root() -> dict[str, str]:
    return {"service": "山间书局博客 API", "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/health", response_model=HealthOut, summary="健康检查")
def health(store: PostStore = StoreDep) -> HealthOut:
    return HealthOut(status="ok", posts=store.count())


@app.post(
    "/posts",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    summary="新建文章",
)
def create_post(
    payload: PostCreate,
    response: Response,
    store: PostStore = StoreDep,
) -> PostOut:
    post = store.create(payload.title, payload.content, payload.author, payload.tags)
    # 201 的正确配套：告诉客户端「新资源在哪」
    response.headers["Location"] = f"/posts/{post.id}"
    return PostOut.of(post)


@app.get("/posts", response_model=list[PostOut], summary="文章列表（支持搜索）")
def list_posts(
    response: Response,
    q: str | None = Query(default=None, description="按标题/正文模糊搜索"),
    limit: int = Query(default=20, ge=1, le=100, description="每页条数"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    store: PostStore = StoreDep,
) -> list[PostOut]:
    posts = store.list(q=q, limit=limit, offset=offset)
    total = store.count(q=q)
    response.headers["X-Total-Count"] = str(total)
    return [PostOut.of(p) for p in posts]


@app.get("/posts/{post_id}", response_model=PostOut, summary="查看文章")
def read_post(post_id: int, store: PostStore = StoreDep) -> PostOut:
    post = store.get(post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"没有 id={post_id} 的文章"
        )
    return PostOut.of(post)


@app.put("/posts/{post_id}", response_model=PostOut, summary="更新文章（局部）")
def update_post(
    post_id: int, payload: PostUpdate, store: PostStore = StoreDep
) -> PostOut:
    post = store.update(
        post_id,
        title=payload.title,
        content=payload.content,
        author=payload.author,
        tags=payload.tags,
    )
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"没有 id={post_id} 的文章"
        )
    return PostOut.of(post)


@app.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除文章",
)
def delete_post(post_id: int, store: PostStore = StoreDep) -> Response:
    if not store.delete(post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"没有 id={post_id} 的文章"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
