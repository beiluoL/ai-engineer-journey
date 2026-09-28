"""Project 06 —— 测试夹具。

一个重要决定：**测试目录不用 pytest 内置的 ``tmp_path``**。
本仓库的开发沙箱里 ``/private/var/.../pytest-of-unknown`` 不可写，
``tmp_path`` 会直接 PermissionError。所以统一用**仓库内**的临时目录
（``tests/.tmp/``），每个用例独立子目录，跑完自动清理 —— 顺带也让
「词表落盘」这类测试看到的是仓库内相对路径，和 demo 真实运行的环境一致。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from tokenizer import BPETokenizer, CharTokenizer
from tokenizer.sample_corpus import MIXED_TEXT, SAMPLE_CORPUS

REPO_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = REPO_ROOT / "tests" / ".tmp"

#: 离线语料直接取自 ``src/tokenizer/sample_corpus.py`` —— 测试和 demo 用同一份，
#: 免得「测试里能跑、demo 里换了个语料就变了」。
CORPUS = SAMPLE_CORPUS


@pytest.fixture()
def workdir() -> Path:
    """仓库内的临时目录，用例结束即删。"""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="case-", dir=TMP_ROOT))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def _cleanup_tmp_root():
    """收尾把 tests/.tmp 整个删掉，不往仓库里留垃圾。"""
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


@pytest.fixture()
def corpus() -> str:
    return CORPUS


@pytest.fixture()
def mixed_text() -> str:
    return MIXED_TEXT


@pytest.fixture()
def char_tok(corpus: str) -> CharTokenizer:
    return CharTokenizer.build(corpus)


@pytest.fixture()
def bpe_tok(corpus: str) -> BPETokenizer:
    # 500 = 基础字符 299 + 201 次合并，正好能学到「注意力」「分词器」这类中文合并
    return BPETokenizer.train(corpus, 500)
