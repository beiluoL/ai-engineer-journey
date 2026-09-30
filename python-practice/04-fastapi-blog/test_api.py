#!/usr/bin/env python3
"""FastAPI 博客 API 的接口测试 —— python-practice/04-fastapi-blog

任务卡：python-practice/04-fastapi-blog/README.md

用 `TestClient` 直接打 ASGI 应用，**不需要真的起一个端口**，所以测试快且稳定。
对应 Java 世界的 `@SpringBootTest` + `MockMvc`，但轻得多。

    pytest -q
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 关键：必须在 import app 之前设好数据库路径，因为 app.py 在模块加载时就定了 DB_PATH
os.environ["BLOG_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")

from app import app  # noqa: E402


@pytest.fixture()
def client():
    """with 进入会触发 lifespan，从而创建 store；退出时关闭连接。"""
    with TestClient(app) as c:
        c.app.state.store.clear()   # 用例之间互不干扰
        yield c


SAMPLE = {
    "title": "为什么要把重复的周报自动化",
    "content": "每周一手工合并三个门店的 CSV，两小时。",
    "author": "阿罗",
    "tags": ["自动化", "pandas"],
}


def test_root_and_health(client: TestClient) -> None:
    assert client.get("/").status_code == 200
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["posts"] == 0


def test_create_returns_201_and_location(client: TestClient) -> None:
    resp = client.post("/posts", json=SAMPLE)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert body["title"] == SAMPLE["title"]
    assert resp.headers["Location"] == "/posts/1"


def test_created_post_can_be_read_back(client: TestClient) -> None:
    new_id = client.post("/posts", json=SAMPLE).json()["id"]
    got = client.get(f"/posts/{new_id}").json()
    assert got["content"] == SAMPLE["content"]
    assert got["tags"] == SAMPLE["tags"]


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"title": "", "content": "正文"},                 # 标题为空
        {"title": "标题", "content": ""},                 # 正文为空
        {"title": "标题", "content": "正文", "tags": ["a", "b", "c", "d", "e", "f"]},  # 标签超 5 个
        {"content": "正文"},                              # 缺 title
    ],
)
def test_invalid_payload_returns_422(client: TestClient, bad_payload: dict) -> None:
    assert client.post("/posts", json=bad_payload).status_code == 422


def test_list_and_search(client: TestClient) -> None:
    client.post("/posts", json=SAMPLE)
    client.post("/posts", json={**SAMPLE, "title": "爬虫与礼貌", "content": "先看 robots.txt"})

    all_posts = client.get("/posts").json()
    assert len(all_posts) == 2
    assert client.get("/posts").headers["X-Total-Count"] == "2"
    # 列表按 id 倒序，最新的在最前
    assert all_posts[0]["title"] == "爬虫与礼貌"

    hit = client.get("/posts", params={"q": "爬虫"}).json()
    assert len(hit) == 1 and hit[0]["title"] == "爬虫与礼貌"

    assert client.get("/posts", params={"q": "不存在的词"}).json() == []


def test_partial_update_only_changes_given_fields(client: TestClient) -> None:
    new_id = client.post("/posts", json=SAMPLE).json()["id"]
    updated = client.put(f"/posts/{new_id}", json={"title": "改过的标题"}).json()
    assert updated["title"] == "改过的标题"
    assert updated["content"] == SAMPLE["content"]      # 没传的字段保持原样
    assert updated["author"] == SAMPLE["author"]


def test_delete_then_get_returns_404(client: TestClient) -> None:
    new_id = client.post("/posts", json=SAMPLE).json()["id"]
    assert client.delete(f"/posts/{new_id}").status_code == 204
    assert client.get(f"/posts/{new_id}").status_code == 404
    # 再删一次应该 404 而不是静默成功
    assert client.delete(f"/posts/{new_id}").status_code == 404


def test_missing_post_returns_friendly_404(client: TestClient) -> None:
    resp = client.get("/posts/9999")
    assert resp.status_code == 404
    assert "没有 id=9999 的文章" in resp.json()["detail"]


def test_openapi_schema_is_generated(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "山间书局博客 API"
    for path in ("/posts", "/posts/{post_id}", "/health"):
        assert path in schema["paths"]
