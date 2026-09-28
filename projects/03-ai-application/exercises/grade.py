#!/usr/bin/env python3
"""Project 03 练习判卷器：题号以 README 为准，答案在 socket 离线哨兵下执行。

用法:
    .venv/bin/python exercises/grade.py                # 人读的输出
    .venv/bin/python exercises/grade.py --selftest     # 验证离线哨兵还灵不灵

判卷规则（三条，缺一不可）:
    1. 每个 NN-*/answers.py 都套着 `_offline_guard.py` 跑，退出码必须为 0
    2. 每题必须真的打印 "[PASS] <题号>"；预期题号从**同目录 README.md** 扫出来 ——
       文档是题源，答案只是答案，"README 写了但答案没解"也算 FAIL
    3. socket 层熔断：答案脚本只要试图连出本机就被 NetworkAccessDenied 打断

为什么不用「符号黑名单」判联网：
    黑名单会误报（构造真实客户端检查脱敏并不发请求），也拦不住偷偷连内网。
    直接在 socket 层装闸门才是真约束 —— `--selftest` 就是这个约束的自证。
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXERCISES_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXERCISES_DIR.parent
GUARD_DIR = EXERCISES_DIR
README_TASK_RE = re.compile(r"^- \[ \] \*\*([A-Z]\d+)\*\*", re.MULTILINE)
PASS_RE = re.compile(r"^\[PASS\]\s+([A-Z]\d+)\b(.*)$", re.MULTILINE)


@dataclass
class Result:
    script: Path
    expected: list[str] = field(default_factory=list)
    passed: dict[str, str] = field(default_factory=dict)
    exit_code: int = 1
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and bool(self.expected) and all(qid in self.passed for qid in self.expected)


def discover() -> list[Path]:
    return sorted(EXERCISES_DIR.glob("[0-9][0-9]-*/answers.py"))


def expected_ids(script: Path) -> list[str]:
    readme = script.with_name("README.md")
    if not readme.exists():
        return []
    return README_TASK_RE.findall(readme.read_text(encoding="utf-8"))


def guarded_run(script: Path) -> subprocess.CompletedProcess[str]:
    """把目标脚本装在离线哨兵里跑。"""
    command = (
        "import sys; "
        f"sys.path.insert(0, {str(GUARD_DIR)!r}); "
        "import _offline_guard as guard; "
        f"guard.run_guarded({str(script.resolve())!r})"
    )
    return subprocess.run(
        [sys.executable, "-u", "-c", command],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def selftest() -> int:
    """自测：证明"离线判卷"不是一句口号 —— 拿一个真的想联网的脚本试试哨兵。

    这条之所以必须写进来：判卷器自身也可能失效。
    万一 `_offline_guard` 被人改坏，所有答案照样"通过"，但约束早就没了。
    自测就是给判卷器自己上的一道锁。
    """
    import tempfile

    cheater = (
        "import socket\n"
        'print("[PASS] Z9 假装这一题过了")\n'
        'socket.create_connection(("223.5.5.5", 443), timeout=2)\n'
        'print("联网成功")\n'
    )
    print("=== 自测：离线哨兵 ===")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "cheater.py"
        script.write_text(cheater, encoding="utf-8")
        proc = guarded_run(script)
    denied = "NetworkAccessDenied" in (proc.stderr or "")
    marked_ok = "[PASS] Z9" in (proc.stdout or "")
    print(f"[{'PASS' if denied else 'FAIL'}] 想联网的答案进程被 socket 层拦下（退出码 {proc.returncode}）")
    print(f"[{'PASS' if marked_ok else 'FAIL'}] 它在被拦下前确实打印了假的 [PASS] 标记 —— 说明只看标记不够")
    ok = denied and marked_ok and proc.returncode != 0
    print(f"--> 自测：{'通过（离线约束真的生效）' if ok else '失败（哨兵没起作用，判卷结果不可信）'}")
    return 0 if ok else 1


def run_one(script: Path) -> Result:
    result = Result(script=script, expected=expected_ids(script))
    proc = guarded_run(script)
    result.exit_code = proc.returncode
    result.stderr = proc.stderr
    result.passed = {match.group(1): match.group(2).strip() for match in PASS_RE.finditer(proc.stdout)}
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Project 03 练习题判卷（纯离线）")
    parser.add_argument("--selftest", action="store_true", help="验证离线哨兵是否真的生效")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    scripts = discover()
    if not scripts:
        print("[FAIL] 未找到 exercises/NN-*/answers.py")
        return 1

    results = [run_one(script) for script in scripts]
    passed_count = 0
    total_count = 0
    for result in results:
        rel = result.script.relative_to(PROJECT_ROOT)
        print(f"=== {rel} ===")
        if not result.expected:
            print("[FAIL] README.md 没有可识别的题号行")
        for qid in result.expected:
            total_count += 1
            if qid in result.passed:
                passed_count += 1
                print(f"[PASS] {qid} {result.passed[qid]}")
            else:
                print(f"[FAIL] {qid} stdout 缺少对应 PASS 标记")
        if result.exit_code != 0:
            tail = (result.stderr.strip().splitlines() or ["无 stderr"])[-1]
            print(f"[FAIL] 文件退出码 {result.exit_code}：{tail}")
        print(f"--> {'通过' if result.ok else '未通过'}\n")

    print(f"总结：{passed_count}/{total_count} 题通过")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
