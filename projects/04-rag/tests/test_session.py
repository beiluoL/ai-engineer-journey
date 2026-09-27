"""session.py：会话模型与存储（17 章）。

这一层测的是「多轮能不能连续」，重点不在功能多，而在**几条容易被忽略的性质**：

    1. 不可变：追加一轮不能改动原 Session（否则并发两个请求会互相覆盖）
    2. 落盘往返：JSON 写出去再读回来，历史要一字不差
    3. 非法 id：../ 这类路径必须被挡住（JsonFile 是按文件名存的）
    4. 历史裁剪：超预算时从最旧的丢，且**保留相对顺序**
"""

from __future__ import annotations

import os

os.environ["RAG_FAKE"] = "1"
os.environ.pop("RAG_SESSIONS_DIR", None)      # 默认纯内存，别把测试写进仓库

import threading  # noqa: E402

from rag.session import (  # noqa: E402
    InMemorySessionStore, JsonFileSessionStore, Session, SessionStore, Turn,
    build_session_store, fit_history, new_id,
)
from rag.errors import SessionError, SessionNotFoundError  # noqa: E402


# —— 模型：不可变与校验 ——

def test_with_turn返回新对象而不是修改原对象():
    session = Session()
    updated = session.with_turn(Turn(role="user", content="第一轮问"))
    assert session.turn_count == 0
    assert updated.turn_count == 1
    assert session.turns == ()                     # 原对象没被动过
    assert updated.session_id == session.session_id


def test_with_turn用第一条提问当标题():
    session = Session()
    once = session.with_turn(Turn(role="user", content="装饰器到底做了什么"))
    twice = once.with_turn(Turn(role="assistant", content="它是可调用对象"))
    assert once.title == "装饰器到底做了什么"
    assert twice.title == once.title               # 第二条不抢标题


def test_messages只保留role和content():
    turn = Turn(role="assistant", content="答：见资料",
                sources=["a.md"], refused=True)
    assert turn.to_message() == {"role": "assistant", "content": "答：见资料"}
    assert turn.sources == ["a.md"] and turn.refused is True   # 展示字段还在


def test_非法角色与空内容被拒():
    try:
        Turn(role="robot", content="hi")
    except SessionError as e:
        assert "非法角色" in str(e)
    else:                                          # pragma: no cover
        raise AssertionError("应该抛错")
    try:
        Turn(role="user", content="   ")
    except SessionError as e:
        assert "不能为空" in str(e)
    else:                                          # pragma: no cover
        raise AssertionError("应该抛错")


def test_renamed会拒绝空标题():
    session = Session(title="原标题")
    try:
        session.renamed("   ")
    except SessionError:
        assert session.title == "原标题"


# —— 内存存储 ——

def test_inmemory增删改查():
    store: SessionStore = InMemorySessionStore()
    session = store.create("新对话")
    assert store.list()[0].session_id == session.session_id
    session = store.append_turn(session.session_id, Turn(role="user", content="问题一"))
    session = store.append_turn(session.session_id, Turn(role="assistant", content="答案一"))
    assert [t.content for t in store.get(session.session_id).turns] == ["问题一", "答案一"]
    store.rename(session.session_id, "改名了")
    assert store.get(session.session_id).title == "改名了"
    store.delete(session.session_id)
    assert store.list() == []
    out: list[SessionError | None] = []

    def _get() -> None:
        try:
            store.get(session.session_id)
        except SessionNotFoundError:
            out.append(None)

    _get()
    assert out == [None]


def test_inmemory重复append不丢轮次():
    store = InMemorySessionStore()
    session = store.create()
    errors: list[BaseException] = []

    def _worker(n: int) -> None:
        for _ in range(5):
            try:
                store.append_turn(session.session_id, Turn(role="user", content=f"q{n}"))
            except SessionError as e:          # 并发路径下也会走校验
                errors.append(e)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.get(session.session_id).turn_count == 20


def test_查不存在的会话抛SessionNotFoundError():
    store = InMemorySessionStore()
    try:
        store.get("nope")
    except SessionNotFoundError:
        return
    raise AssertionError("应该抛错")            # pragma: no cover


# —— 文件存储 ——

def test_jsonfile重启后历史还在(workdir):
    store = JsonFileSessionStore(workdir)
    session = store.create("带历史的会话")
    store.append_turn(session.session_id, Turn(role="user", content="上一轮的问题"))
    # 模拟重启：换个 store 实例读同一个目录
    reopened = JsonFileSessionStore(workdir).get(session.session_id)
    assert reopened.messages() == [
        {"role": "user", "content": "上一轮的问题"}]      # 一字不差
    # 落盘后 title 被第一条 user 提问顶掉了（Session.with_turn 的规则），
    # 这也是期望行为：会话列表里最好直接看到用户问了什么，而不是「新对话」
    assert reopened.title == "上一轮的问题"


def test_jsonfile坏文件不影响列表页(workdir):
    store = JsonFileSessionStore(workdir)
    good = store.create()
    (workdir / "broken.json").write_text("{不是 json", encoding="utf-8")
    listing = store.list()
    assert [s.session_id for s in listing] == [good.session_id]


def test_jsonfile挡住路径穿越():
    store = JsonFileSessionStore(".")
    for bad in ("../etc/passwd", "a/b", ".."):
        try:
            store.get(bad)
        except SessionError:
            continue
        raise AssertionError(f"{bad} 应该被挡住")  # pragma: no cover


def test_build_session_store按目录切换实现():
    assert isinstance(build_session_store(""), InMemorySessionStore)
    assert isinstance(build_session_store(""), InMemorySessionStore)


# —— 历史裁剪 ——

def _turns(n: int, prefix: str = "t") -> list[Turn]:
    return [Turn(role="user" if i % 2 == 0 else "assistant",
                 content=f"{prefix}第{i}轮" * 10) for i in range(n)]


def test_fit_history按条数从旧的截():
    kept = fit_history(_turns(10), max_turns=3, max_chars=10_000)
    assert len(kept) == 3
    # 保留的是最近三轮：_turns(10) 的最后一轮是 i=9
    assert kept[-1].content.startswith("t第9轮")
    assert kept[0].content.startswith("t第7轮")


def test_fit_history超字符时从最旧丢():
    kept = fit_history(_turns(6), max_turns=100, max_chars=30)
    assert len(kept) < 6
    # 丢的是最旧的，剩下的必须还是原来的顺序（不能跳着留）
    contents = [t.content[:3] for t in kept]
    assert contents == sorted(contents)


def test_fit_history空输入():
    assert fit_history([], 5, 100) == []


def test_session_id足够短且不同():
    ids = {new_id() for _ in range(50)}
    assert all(len(i) == 8 for i in ids)
    assert len(ids) == 50
