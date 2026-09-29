"""Project 09 的跨项目路径与导入初始化。"""

from __future__ import annotations

import sys
from pathlib import Path

P09_ROOT = Path(__file__).resolve().parents[2]
P09_SRC = P09_ROOT / "src"
P09_MODELS = P09_ROOT / "models"
P06_ROOT = P09_ROOT.parent / "06-mini-transformer-llm"
P08_ROOT = P09_ROOT.parent / "08-fine-tuning"
P06_SRC = P06_ROOT / "src"
P08_SRC = P08_ROOT / "src"


def ensure_deps_importable() -> tuple[Path, Path]:
    """校验并导入 P06/P08，同时启用 P08 的确定性 autograd 补丁。"""
    missing = [path for path in (P06_SRC, P08_SRC) if not path.is_dir()]
    if missing:
        rendered = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Project 09 缺少只读依赖源码目录：\n{rendered}")
    for path in (P06_SRC, P08_SRC):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    from ft.paths import enable_deterministic_autograd

    enable_deterministic_autograd()
    return P06_SRC, P08_SRC


def ensure_models_dir() -> Path:
    P09_MODELS.mkdir(parents=True, exist_ok=True)
    return P09_MODELS


__all__ = [
    "P06_ROOT", "P06_SRC", "P08_ROOT", "P08_SRC", "P09_MODELS", "P09_ROOT",
    "P09_SRC", "ensure_deps_importable", "ensure_models_dir",
]
