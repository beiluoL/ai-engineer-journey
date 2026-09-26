"""embedding.py：Fake 替身的契约 —— 确定性是它的全部价值。"""

from __future__ import annotations

import asyncio

import pytest

from rag.embedding import (BaseEmbeddingClient, FakeEmbeddingClient, run_sync,
                          SiliconFlowEmbeddingClient, create_embedding_client)
from rag.errors import EmbeddingError
from rag.similarity import cosine_similarity, l2_norm


def test_fake_是两个实例也给出同一向量():
    a, b = FakeEmbeddingClient(), FakeEmbeddingClient()
    va = run_sync(a.embed(["生成器为什么能省内存"]))
    vb = run_sync(b.embed(["生成器为什么能省内存"]))
    assert va == vb                                        # 同样输入必须同样向量


def test_embed_是异步批量接口():
    assert asyncio.iscoroutinefunction(FakeEmbeddingClient.embed)
    vectors = run_sync(FakeEmbeddingClient().embed(["第一个", "第二个", "第三个"]))
    assert len(vectors) == 3
    assert all(len(v) == 64 for v in vectors)
    assert vectors[0] != vectors[1]                        # 不同文本不能给同一向量


def test_embed_one_是单条便捷方法():
    vec = run_sync(FakeEmbeddingClient().embed_one("生成器"))
    assert len(vec) == 64
    assert vec == run_sync(FakeEmbeddingClient().embed(["生成器"]))[0]


def test_向量是单位向量():
    v = run_sync(FakeEmbeddingClient().embed_one("生成器"))
    assert abs(l2_norm(v) - 1.0) < 1e-9                    # 归一化后点积才能当余弦用


def test_字面越像余弦越大():
    c = FakeEmbeddingClient()
    near = cosine_similarity(run_sync(c.embed_one("生成器为什么能省内存")),
                             run_sync(c.embed_one("生成器让内存占用是常量级")))
    far = cosine_similarity(run_sync(c.embed_one("生成器为什么能省内存")),
                            run_sync(c.embed_one("GIL 是 CPython 的一把全局锁")))
    assert near > far                                      # 替身只要做到「相关就更近」


def test_base_是抽象类():
    with pytest.raises(TypeError):
        BaseEmbeddingClient()                              # 抽象方法不许绕过


def test_siliconflow_没有key直接报错():
    with pytest.raises(EmbeddingError):
        SiliconFlowEmbeddingClient(api_key="")


def test_create_embedding_client_工厂():
    assert isinstance(create_embedding_client("fake"), FakeEmbeddingClient)
