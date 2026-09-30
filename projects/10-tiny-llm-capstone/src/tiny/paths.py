"""Project 10 —— 路径与跨项目依赖导入。

Capstone 的定位是「**把前面 9 个项目重新串起来**」，所以它刻意**不重写**
任何一块已经被证明过的实现：

- ``model`` / ``tokenizer`` —— P06 手写（含从零 autograd）
- ``ft`` —— P08 手写（LoRA / QLoRA / 确定性补丁）
- ``ie`` —— P09 手写（评估指标 / 量化 / KV Cache / PagedAttention / OpenAI 兼容服务）

本模块负责把这三个 ``src`` 目录挂进 ``sys.path``。两处刻意的设计：

1. **路径从 ``__file__`` 逐级往上推**，不硬编码绝对路径，仓库换机器 clone 下来照样能跑；
2. **先校验再插入** —— 缺依赖时抛带完整路径的清晰错误，而不是让后面某行
   ``from model import ...`` 抛一个看不懂的 ``ModuleNotFoundError``。

另外必须在**任何 Tensor 被创建之前**启用 P08 的确定性 autograd 补丁
（原因见 ``ft.paths``：P06 的 ``Tensor._prev`` 是 ``set``，迭代顺序依赖对象地址，
跨进程不可复现）。P10 要拿真实数字下结论，所以这里就地打补丁。
"""

from __future__ import annotations

import sys
from pathlib import Path

# src/tiny/paths.py → parents[0]=src/tiny → [1]=src → [2]=projects/10-tiny-llm-capstone
P10_ROOT: Path = Path(__file__).resolve().parents[2]
P10_SRC: Path = P10_ROOT / "src"
P10_DATA: Path = P10_ROOT / "data"
P10_MODELS: Path = P10_ROOT / "models"
P10_DEMOS: Path = P10_ROOT / "demos"

#: 三个只读依赖，都是 projects/ 下的同级目录
P06_ROOT: Path = P10_ROOT.parent / "06-mini-transformer-llm"
P08_ROOT: Path = P10_ROOT.parent / "08-fine-tuning"
P09_ROOT: Path = P10_ROOT.parent / "09-evaluation-inference"
P06_SRC: Path = P06_ROOT / "src"
P08_SRC: Path = P08_ROOT / "src"
P09_SRC: Path = P09_ROOT / "src"

#: 本项目自带的领域语料（AI 工程主题，146 行）
CORPUS_TXT: Path = P10_DATA / "corpus.txt"


def ensure_deps_importable() -> tuple[Path, Path, Path]:
    """校验 P06 / P08 / P09 源码存在并挂进 ``sys.path``，返回三个 ``src`` 路径。

    幂等：已经插入过的目录不会重复插入。
    """
    missing = [p for p in (P06_SRC, P08_SRC, P09_SRC) if not p.is_dir()]
    if missing:
        rendered = "\n".join(f"  - {p}" for p in missing)
        raise FileNotFoundError(
            "Project 10（Capstone）缺少只读依赖的源码目录：\n"
            f"{rendered}\n"
            "本项目的模型 / 分词器来自 P06，确定性补丁来自 P08，"
            "评估与推理组件来自 P09，请先确认仓库完整。"
        )
    for path in (P06_SRC, P08_SRC, P09_SRC):
        text = str(path)
        if text not in sys.path:
            # 插到最前面，保证 import model / tokenizer 命中的是 P06 的那份
            sys.path.insert(0, text)
    from ft.paths import enable_deterministic_autograd

    enable_deterministic_autograd()
    return P06_SRC, P08_SRC, P09_SRC


def ensure_dir(path: "str | Path") -> Path:
    """``mkdir -p`` 的 Path 版，返回该目录。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_models_dir() -> Path:
    return ensure_dir(P10_MODELS)


def ensure_corpus() -> Path:
    """校验本项目语料存在（只读使用）。"""
    if not CORPUS_TXT.is_file():
        raise FileNotFoundError(f"找不到领域语料：{CORPUS_TXT}")
    return CORPUS_TXT


__all__ = [
    "CORPUS_TXT",
    "P06_ROOT",
    "P06_SRC",
    "P08_ROOT",
    "P08_SRC",
    "P09_ROOT",
    "P09_SRC",
    "P10_DATA",
    "P10_DEMOS",
    "P10_MODELS",
    "P10_ROOT",
    "P10_SRC",
    "ensure_corpus",
    "ensure_deps_importable",
    "ensure_dir",
    "ensure_models_dir",
]

# ⚠ 必须在任何 Tensor 被创建**之前**生效。tiny 的每个子模块第一行都是
#   ``from .paths import ...``，所以在 paths 里就地调用是唯一可靠的时机。
ensure_deps_importable()
