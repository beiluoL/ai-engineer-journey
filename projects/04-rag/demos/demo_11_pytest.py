"""09 & 10 章：把离线测试套件真的跑一遍，把结果打在终端上。

为什么单独做一个 demo：单测全绿 ≠ 链路正确。这一屏是「这套离线装置到底能不能
兜住回归」的证据 —— 它跑的就是 src/rag/ 自己的 tests/，不联网、不写系统临时目录。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from common import head, note, rule

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def main() -> int:
    head(f"cd projects/04-rag && {Path(PY).name} -m pytest -q")
    proc = subprocess.run([PY, "-m", "pytest", "-q"], cwd=ROOT,
                          capture_output=True, text=True, check=False)
    out = (proc.stdout + proc.stderr).rstrip()
    print(out)
    tail = [ln for ln in out.splitlines() if ln.strip()][-1]
    print(f"\n退出码：{proc.returncode}（0 = 全部通过）")
    if proc.returncode == 0 and (" passed" in tail or " passed," in tail):
        note("这一步没有任何 mock 美化：FakeEmbeddingClient + InMemoryVectorStore + "
             "NoopReranker 真的跑完了 14 个测试文件")
    else:
        note("有测试挂了 —— 先修测试再谈效果")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
