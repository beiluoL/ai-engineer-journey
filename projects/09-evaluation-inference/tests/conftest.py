from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ie.paths import ensure_deps_importable

ensure_deps_importable()


@pytest.fixture
def tiny_model():
    from model import TransformerLM

    np.random.seed(123)
    return TransformerLM(vocab_size=64, d_model=16, n_heads=4, d_ff=32, n_layers=2, max_len=128)
