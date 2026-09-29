"""Project 08 —— 测试夹具。

三个决定（和 P06 保持一致）：
1. **不用 pytest 内置的 ``tmp_path``** —— 开发沙箱里 ``/private/var/...`` 不可写，
   统一用仓库内的 ``tests/.tmp/``，跑完自动清理。
2. 基座模型从 ``models/base_lm.npz`` **加载**（首次会自动训练并缓存），
   保证测试看到的基座和九个 demo 看到的是**同一份**。
3. 每个用例拿到的都是**新加载**的模型对象：注入 LoRA / 训练会改模型状态，
   共享同一个实例会让用例之间互相污染。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ft import (  # noqa: E402
    build_sft_examples,
    build_tokenizer,
    ensure_base_model,
    load_java_records,
)

TMP_ROOT = ROOT / "tests" / ".tmp"


@pytest.fixture(scope="session")
def tokenizer():
    """缓存好的 BPE 分词器（和 demo 同一份）。"""
    return build_tokenizer()


@pytest.fixture(scope="session")
def records():
    """P07 的 Java 面试数据（只读）。"""
    return load_java_records()


@pytest.fixture(scope="session")
def sft_examples(tokenizer, records):
    return build_sft_examples(records, tokenizer, max_len=256)


@pytest.fixture()
def fresh_model():
    """一份**新加载**的基座模型（不共享状态）。"""
    model, _tok, _info = ensure_base_model()
    return model


@pytest.fixture()
def workdir():
    """仓库内的临时目录，用例结束即删。"""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="case-", dir=TMP_ROOT))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def _cleanup_tmp_root():
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def _seed():
    """每个用例开局固定随机种子，保证可复现。"""
    np.random.seed(0)
    yield
