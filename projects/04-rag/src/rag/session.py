"""会话与历史（对应 milestone 17）。

产品化之后，RAG 从「问一句答一句」变成「可以连续聊」。这件事看起来前端做得最多，
其实一半以上的坑在后端：

    1. 历史是**不可变**的：追加一条 Turn 要产出一个新的 Session，
       否则并发两个请求写到同一个列表，谁先写完由运气决定。
    2. 历史**不能直接当消息喂给模型**：要丢掉 sources/refused 这些展示字段，
       只留 role + content，而且 cross 一轮的上下文会吃掉 token 预算。
    3. 存储**必须可插拔**：单测用内存、生产落 JSON 文件、以后换 SQLite，
       调用方写的都只有 `SessionStore` 那几个方法。

所以这里模型（Turn / Session）与存储（SessionStore 的两个实现）分成两层，
service 只依赖抽象。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import SessionError, SessionNotFoundError

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLES = (ROLE_USER, ROLE_ASSISTANT)

# 标题生成策略：用第一条用户提问的前 N 个字，超了截断加省略号
TITLE_MAX = 24


def new_id() -> str:
    """会话 id 用 8 位十六进制，够短（能和时间戳对齐肉眼读）也够不撞。"""
    return uuid.uuid4().hex[:8]


def _now() -> float:
    return datetime.now().timestamp()


@dataclass(frozen=True)
class Turn:
    """一轮问答。content 是模型最终看到的文本，sources 只是展示用。"""

    role: str
    content: str
    turn_id: str = field(default_factory=new_id)
    created_at: float = field(default_factory=_now)
    sources: list[str] = field(default_factory=list)
    refused: bool = False

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise SessionError(f"非法角色 {self.role!r}（只允许 {ROLES}）")
        if not self.content.strip():
            raise SessionError("Turn 内容不能为空")

    def to_message(self) -> dict[str, str]:
        """转成给 LLM 的消息（17 章§3.2：只留 role + content）。

        引用来源、拒答标记都是**给人看的**，塞进 messages 里只会在真模型上出现
        「模型引用自己上一轮给的编号」这种假象。
        """
        return {"role": self.role, "content": self.content}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.turn_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "sources": list(self.sources),
            "refused": self.refused,
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Turn":
        return Turn(
            role=raw["role"],
            content=raw["content"],
            turn_id=raw.get("id") or new_id(),
            created_at=raw.get("created_at", 0.0),
            sources=list(raw.get("sources") or []),
            refused=bool(raw.get("refused")),
        )


@dataclass(frozen=True)
class Session:
    """一个会话。`turns` 用 tuple —— 不可变，追加只能靠 replace()。"""

    session_id: str = field(default_factory=new_id)
    title: str = "新对话"
    turns: tuple[Turn, ...] = ()
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)

    # —— 读取侧 ——

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def last_turn(self) -> Turn | None:
        return self.turns[-1] if self.turns else None

    def messages(self) -> list[dict[str, str]]:
        """全部历史转成 messages（不含本次 query）。"""
        return [t.to_message() for t in self.turns]

    # —— 写入侧：都返回新对象 ——

    def with_turn(self, turn: Turn) -> "Session":
        """追加一轮。返回**新** Session，原对象不变。"""
        if turn.role not in ROLES:
            raise SessionError(f"非法角色 {turn.role!r}")
        now = _now()
        return replace(
            self,
            turns=self.turns + (turn,),
            updated_at=now,
            # 第一条用户提问作为标题：超过 TITLE_MAX 就截断（前端再补省略号）
            title=(turn.content[:TITLE_MAX] if not self.turns and turn.role == ROLE_USER
                   else self.title),
        )

    def renamed(self, title: str) -> "Session":
        title = (title or "").strip()
        if not title:
            raise SessionError("标题不能为空")
        return replace(self, title=title[:TITLE_MAX], updated_at=_now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turns": [t.to_dict() for t in self.turns],
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Session":
        turns = tuple(Turn.from_dict(t) for t in (raw.get("turns") or []))
        return Session(
            session_id=raw.get("id") or new_id(),
            title=raw.get("title") or "新对话",
            turns=turns,
            created_at=raw.get("created_at", 0.0),
            updated_at=raw.get("updated_at", 0.0),
        )


class SessionStore(ABC):
    """会话存储的抽象。调用方只认这 6 个方法，换实现不动业务代码。"""

    @abstractmethod
    def create(self, title: str = "新对话") -> Session:
        ...

    @abstractmethod
    def get(self, session_id: str) -> Session:
        ...

    @abstractmethod
    def append_turn(self, session_id: str, turn: Turn) -> Session:
        ...

    @abstractmethod
    def rename(self, session_id: str, title: str) -> Session:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...

    @abstractmethod
    def list(self) -> list[Session]:
        ...


class InMemorySessionStore(SessionStore):
    """进程内存储。单测与「关掉浏览器就什么都不留」的场景用它。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}

    def create(self, title: str = "新对话") -> Session:
        with self._lock:
            session = Session(title=title or "新对话")
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"会话不存在: {session_id}")
        return session

    def append_turn(self, session_id: str, turn: Turn) -> Session:
        # 读-改-写整个都在锁里：两步之间有并发请求就会丢轮次
        with self._lock:
            session = self.get(session_id)
            updated = session.with_turn(turn)
            self._sessions[session_id] = updated
            return updated

    def rename(self, session_id: str, title: str) -> Session:
        with self._lock:
            session = self.get(session_id)
            updated = session.renamed(title)
            self._sessions[session_id] = updated
            return updated

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def list(self) -> list[Session]:
        with self._lock:
            # 按最近更新排序：列表页最重要的信息是「哪条还在动」
            return sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)


class JsonFileSessionStore(SessionStore):
    """落 JSON 文件的存储。重启不丢历史，一个人用完全够（生产上换 SQLite/PG）。

    两个细节值得写下来：

    * **原子写**：先写临时文件再 os.replace()。否则进程在写一半被 kill，
        你会得到一个截断的 JSON —— 而会话目录里的东西用户是当记忆看的。
    * **每个会话一个文件**：并发创建时不会互相覆盖，代价是不能一次整体导出。
    """

    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        if "/" in session_id or "\\" in session_id or session_id in (".", ".."):
            raise SessionError(f"非法会话 id: {session_id!r}")
        return self.dir / f"{session_id}.json"

    def create(self, title: str = "新对话") -> Session:
        # 先创建再落盘：拿到 id 之后才写文件，避免「文件里没有 id」的中间态
        session = Session(title=title or "新对话")
        self._write(session)
        return session

    def get(self, session_id: str) -> Session:
        path = self._path(session_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise SessionNotFoundError(f"会话不存在: {session_id}") from e
        except (OSError, json.JSONDecodeError) as e:
            raise SessionError(f"会话文件损坏: {path}") from e
        return Session.from_dict(json.loads(raw))

    def append_turn(self, session_id: str, turn: Turn) -> Session:
        # 文件存储没有全局锁，用「读完立刻写回」+ 校验 turns 数量来降低覆盖概率
        session = self.get(session_id)
        updated = session.with_turn(turn)
        self._write(updated)
        return updated

    def rename(self, session_id: str, title: str) -> Session:
        session = self.get(session_id)
        updated = session.renamed(title)
        self._write(updated)
        return updated

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if not path.exists():
            raise SessionNotFoundError(f"会话不存在: {session_id}")
        path.unlink()

    def list(self) -> list[Session]:
        out: list[Session] = []
        for path in sorted(self.dir.glob("*.json")):
            try:
                out.append(Session.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):   # 坏文件跳过，不拖垮列表页
                continue
        return sorted(out, key=lambda s: s.updated_at, reverse=True)

    def _write(self, session: Session) -> None:
        path = self._path(session.session_id)
        try:
            fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as e:
            raise SessionError(f"会话写入失败: {path}") from e


def fit_history(turns: list[Turn] | tuple[Turn, ...], max_turns: int,
                max_chars: int) -> list[Turn]:
    """把历史裁剪到「模型付得起」的规模（17 章§3.3）。

    两步裁剪，顺序不能反：

        1. 先按条数：`turns[-max_turns:]`。用户连续聊 50 轮时，
           早期轮次的边际价值极低，没必要让它吃掉上下文。
        2. 再按字符：仍然超预算就从**最旧**的一轮开始丢。

    为什么不是「从中间丢」：中间丢会让「A 问 → B 答 → A 追问」的指代链断掉，
    模型看到两段没头没尾的话，比少看几轮更早的历史更容易答错。
    """
    kept = list(turns)[-max_turns:] if max_turns > 0 else []
    while kept and sum(len(t.content) for t in kept) > max_chars:
        kept.pop(0)          # 丢最旧的
    return kept


def build_session_store(directory: str | None = None) -> SessionStore:
    """默认实现：给个目录就落 JSON，不给就纯内存。

    环境变量 `RAG_SESSIONS_DIR` 是唯一开关（和 embedding 的 provider 探测同一套思路：
    改环境变量而不是改代码）。
    """
    directory = directory or os.getenv("RAG_SESSIONS_DIR") or ""
    return JsonFileSessionStore(directory) if directory else InMemorySessionStore()
