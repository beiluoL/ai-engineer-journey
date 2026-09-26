"""settings.py：frozen 配置 + profile + validate（09 §3.2）。"""

from __future__ import annotations

import pytest

from rag.errors import ConfigurationError
from rag.settings import PROFILES, RAGSettings


def test_默认值可用():
    s = RAGSettings()
    assert s.chunk_size == 500 and s.top_k == 5 and s.embedding_model


def test_frozen_改不动():
    s = RAGSettings()
    with pytest.raises(Exception):                        # frozen dataclass → FrozenInstanceError
        s.top_k = 3                                       # type: ignore[misc]


def test_replace_产出新对象_原对象不动():
    s = RAGSettings()
    s2 = s.replace(top_k=3, enable_rerank=False)
    assert (s.top_k, s.enable_rerank) == (5, True)
    assert (s2.top_k, s2.enable_rerank) == (3, False)


def test_for_profile_未知profile报错():
    assert RAGSettings.for_profile("test").enable_rerank is False   # 测试档关 rerank
    assert RAGSettings.for_profile("dev").budget_tokens == 6000
    with pytest.raises(ConfigurationError):
        RAGSettings.for_profile("prod")


def test_validate_拦住会死循环的组合():
    RAGSettings().validate()
    with pytest.raises(ConfigurationError):
        RAGSettings(chunk_size=500, chunk_overlap=500).validate()
    with pytest.raises(ConfigurationError):
        RAGSettings(chunk_size=0).validate()
    with pytest.raises(ConfigurationError):
        RAGSettings(top_k=0).validate()


def test_effective_budget_不会超过窗口减输出预留():
    s = RAGSettings()
    assert s.effective_budget() == min(6000, 64000 - 2048)
    assert RAGSettings(budget_tokens=99_999, context_window=10_000,
                       reserved_output=2_048).effective_budget() == 7_952


def test_profiles表是已知的几个():
    assert set(PROFILES) == {"dev", "test"}
