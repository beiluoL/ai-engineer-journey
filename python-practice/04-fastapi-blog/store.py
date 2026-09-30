#!/usr/bin/env python3
"""SQLite 数据层 —— python-practice/04-fastapi-blog

任务卡：python-practice/04-fastapi-blog/README.md

刻意不用 ORM（SQLAlchemy），直接用标准库 `sqlite3`：
1. 零额外依赖，你能看清「一条 SQL 是怎么发出去的」
2. 顺便把**参数化查询**这件事学会 —— 拼接 SQL 字符串是注入漏洞的源头
3. 它就是一个真实的磁盘文件，进程重启数据还在（不像内存字典）

如果你来自 Java：这一层大致相当于 `Repository`，`app.py` 相当于 `Controller`，
`PostCreate` / `PostOut` 相当于 DTO。
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    author     TEXT NOT NULL DEFAULT '匿名',
    tags       TEXT NOT NULL DEFAULT '[]',   -- 存 JSON 字符串（SQLite 没有数组类型）
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
"""


@dataclass(frozen=True)
class Post:
    """一条文章记录。frozen=True：改内容要整条替换，避免「偷偷改了字段忘记落盘」。"""

    id: int
    title: str
    content: str
    author: str
    tags: list[str]
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_post(row: sqlite3.Row) -> Post:
    return Post(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        author=row["author"],
        tags=json.loads(row["tags"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostStore:
    """文章仓库。所有 SQL 都在这里，别的地方不出现 SQL 字符串。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        # check_same_thread=False：uvicorn 的 worker 与 TestClient 可能不在同一个线程里
        # 打开这个连接。练习项目用单连接没问题；生产要换成连接池。
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---------- 写 ----------

    def create(self, title: str, content: str, author: str, tags: list[str]) -> Post:
        now = _now()
        # 问号占位 + 参数元组 = 参数化查询。绝不要写 f"... VALUES ('{title}')"，
        # 那等于把数据库的门钥匙交给任何一个输入标题的人。
        cur = self._conn.execute(
            "INSERT INTO posts (title, content, author, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, content, author, json.dumps(tags, ensure_ascii=False), now, now),
        )
        self._conn.commit()
        post = self.get(int(cur.lastrowid))
        assert post is not None  # 刚插入必然存在；真为 None 说明数据库坏了，该炸
        return post

    def update(
        self,
        post_id: int,
        title: str | None = None,
        content: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
    ) -> Post | None:
        """局部更新：只更新传进来的字段。返回 None 表示这条记录不存在。"""
        existing = self.get(post_id)
        if existing is None:
            return None

        fields: dict[str, object] = {}
        if title is not None:
            fields["title"] = title
        if content is not None:
            fields["content"] = content
        if author is not None:
            fields["author"] = author
        if tags is not None:
            fields["tags"] = json.dumps(tags, ensure_ascii=False)

        if fields:
            fields["updated_at"] = _now()
            assignments = ", ".join(f"{k} = ?" for k in fields)
            self._conn.execute(
                f"UPDATE posts SET {assignments} WHERE id = ?",
                (*fields.values(), post_id),
            )
            self._conn.commit()
        return self.get(post_id)

    def delete(self, post_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ---------- 读 ----------

    def get(self, post_id: int) -> Post | None:
        row = self._conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return _row_to_post(row) if row else None

    def list(self, q: str | None = None, limit: int = 20, offset: int = 0) -> list[Post]:
        sql = "SELECT * FROM posts"
        params: list[object] = []
        if q:
            # LIKE 的通配符也由参数传，别拼进 SQL
            sql += " WHERE title LIKE ? OR content LIKE ?"
            like = f"%{q}%"
            params += [like, like]
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_post(r) for r in rows]

    def clear(self) -> None:
        """清空表。只给测试用 —— 让每个用例从干净的状态开始。"""
        self._conn.execute("DELETE FROM posts")
        self._conn.execute("DELETE FROM sqlite_sequence WHERE name = 'posts'")
        self._conn.commit()

    def count(self, q: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS n FROM posts"
        params: list[object] = []
        if q:
            sql += " WHERE title LIKE ? OR content LIKE ?"
            like = f"%{q}%"
            params += [like, like]
        return int(self._conn.execute(sql, params).fetchone()["n"])
