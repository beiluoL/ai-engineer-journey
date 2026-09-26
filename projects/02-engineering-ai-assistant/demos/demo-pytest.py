"""Chapter 07 演示 —— 真实跑一次 pytest：先有一个失败，修完再全绿。

这个脚本自己搭台子：

    1. 在临时目录写一个 7 用例的测试文件（其中 1 个是故意写错的断言）
    2. 跑 `pytest -q`        → 看到 FAILED + pytest 展开的断言细节
    3. 把被测函数的常量修掉（这是真实的「改代码」动作）
    4. 再跑 `pytest -q`      → 7 passed

脚本里打印的每一行都是子进程真实 stdout，没有编排。

运行：

    python3 demos/demo-pytest.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 被测代码：故意把「2 字符 ≈ 1 token」写成了「3 字符 ≈ 1 token」
SOURCE_BUGGY = '''"""本章演示用的小工具。"""


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。"""
    return len(text) // 3


def normalize_question(text: str) -> str:
    """去首尾空白，并把连续空白压成一个空格。"""
    return " ".join(text.split())


def ask_summary(question: str) -> str:
    if not question.strip():
        raise ValueError("问题不能为空")
    return f"关于「{normalize_question(question)}」的回答"
'''

# 同一份代码，只修 estimate_tokens 的除数
SOURCE_FIXED = SOURCE_BUGGY.replace("len(text) // 3", "len(text) // 2")

TESTS = '''"""测试：跑在临时目录里，完全离线、不需要 API Key。"""
import pytest

from ch07_calc import ask_summary, estimate_tokens, normalize_question


def test_normalize_strips_whitespace():
    assert normalize_question("  什么是 RAG？  ") == "什么是 RAG？"


def test_normalize_collapses_spaces():
    assert normalize_question("RAG  是  什么") == "RAG 是 什么"


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_returns_int():
    # 结构性断言：不看具体数值，这样换估算算法也不会红
    value = estimate_tokens("RAG 是什么")
    assert isinstance(value, int) and value > 0


def test_estimate_tokens_two_chars_per_token():
    assert estimate_tokens("RAG 是什么") == 3  # 7 字符 // 2 = 3


def test_ask_summary_builds_answer():
    assert ask_summary("什么是 RAG？") == "关于「什么是 RAG？」的回答"


def test_ask_summary_rejects_empty():
    with pytest.raises(ValueError, match="问题不能为空"):
        ask_summary("   ")
'''


def run_pytest(workdir: Path) -> str:
    """跑一次 pytest -q，返回真实输出。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=short", "test_ch07_calc.py"],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def main() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="ch07-pytest-demo-"))
    try:
        (workdir / "ch07_calc.py").write_text(SOURCE_BUGGY, encoding="utf-8")
        (workdir / "test_ch07_calc.py").write_text(TESTS, encoding="utf-8")

        print("$ cd <临时目录> && python3 -m pytest -q --tb=short")
        print(run_pytest(workdir))

        print("# estimate_tokens 里 // 3 是笔误，改成 // 2（真实的改动发生在下一行）")
        (workdir / "ch07_calc.py").write_text(SOURCE_FIXED, encoding="utf-8")

        print("$ python3 -m pytest -q --tb=short   # 改完之后")
        print(run_pytest(workdir))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
