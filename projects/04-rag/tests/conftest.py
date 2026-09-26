"""pytest 的公共装置：把 src/ 加进 sys.path，并提供一批离线夹具。

关于临时目录（很重要）：
    沙箱里 pytest 自带的 `tmp_path` 会落到 /private/var 之类的路径，
    写不进去，所以这里自己在本项目内建 `tests/.tmp/<uuid>`。
    用 exists() 判断 + mkdir(exist_ok=True)，跑完由 fixture 负责清理，
    .tmp/ 也在 .gitignore 里，不会污染仓库。
"""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TMP_ROOT = Path(__file__).resolve().parent / ".tmp"

# 三个离线语料：内容取自 projects/04-rag/data/ 的真实知识，这里做成小样本，
# 避免单测依赖 data/ 目录（data/ 是给人读的样本库）。
MD_SAMPLE = """# Python 生成器：惰性计算与内存

## 生成器是什么

生成器（generator）是一种「边算边吐」的迭代器。函数体里出现 `yield`，
这个函数就不再是普通函数，而是返回一个生成器对象。

## 为什么能省内存

`range(1000000)` 和 `[i * 2 for i in range(1000000)]` 差得不是一点点：
列表推导式会一次性把 100 万个整数全部造出来放在内存里。

```python
def flat(nested):
    for item in nested:
        yield item
```

## 常见坑

1. 生成器只能遍历一次。
2. `yield` 里的异常不会凭空消失。
"""

TXT_SAMPLE = """GIL 是什么
GIL（Global Interpreter Lock，全局解释器锁）是 CPython 的一个互斥锁：
任何时刻只有一个线程能执行 Python 字节码。

CPU 密集任务：多线程「互相抢锁」，总耗时可能比单线程还慢
IO 密集任务：等待期间线程让出 GIL，多线程能显著提速
"""

CORPUS = {"python-generators.md": MD_SAMPLE, "python-gil.txt": TXT_SAMPLE}


@pytest.fixture()
def workdir():
    """每个用例一个独立目录，跑完清掉。"""
    d = TMP_ROOT / uuid.uuid4().hex
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def corpus_dir(workdir):
    """写入 2 个语料文件（1 个 md + 1 个 txt）的目录。"""
    for name, text in CORPUS.items():
        (workdir / name).write_text(text, encoding="utf-8")
    return workdir


@pytest.fixture()
def fake_client():
    """离线 embedding 替身。"""
    from rag.embedding import FakeEmbeddingClient

    return FakeEmbeddingClient()


@pytest.fixture()
def fake_store(fake_client, workdir):
    """「2 篇语料 → 向量库」的离线装置，retriever/service 测试共用。"""
    from rag.chunker import chunk_document
    from rag.embedding import run_sync
    from rag.parsing import parse_file
    from rag.store import InMemoryVectorStore

    # 先落到真实文件再解析（解析器要真的读盘），语料内容来自 CORPUS
    for name, text in CORPUS.items():
        (workdir / name).write_text(text, encoding="utf-8")

    store = InMemoryVectorStore()
    chunks = []
    for name in CORPUS:
        path = workdir / name
        for doc in parse_file(path):
            chunks.extend(chunk_document(doc, size=300, overlap=60))
    # FakeEmbeddingClient 的 embed() 是 async 的，测试里用 run_sync 收口
    vectors = run_sync(fake_client.embed([c.text for c in chunks]))
    store.add(chunks, vectors, fake_client.model_name)
    return store, chunks
