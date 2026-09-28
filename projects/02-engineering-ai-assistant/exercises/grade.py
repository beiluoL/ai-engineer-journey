#!/usr/bin/env python3
"""Project 02 Exercise 判卷脚本（stdlib only，无任何第三方依赖）。

用法:
    .venv/bin/python exercises/grade.py                # 人读的输出
    .venv/bin/python exercises/grade.py --json         # 机器可读（CI 用）

判卷规则（四条，缺一不可）:
    1. 每个 NN-*/answers.py 都套着 `_offline_guard.py` 跑一遍，必须 exit code 为 0
    2. 每题必须真的打印出 "[PASS] <题号>" 标记，缺一个算 FAIL
        预期题号从**同目录的 README.md** 扫出来（`- [ ] **A1**` 这种行）——
        文档是题源，答案只是答案；这样「README 里写了一道题但答案里没解」也会被判 FAIL
    3. socket 层熔断：answers.py 只要试图连出本机就被 NetworkAccessDenied 打断
        （比符号黑名单可靠——构造 DeepSeekClient 检查脱敏是正当操作，黑名单会误报）
    4. 静态提醒：出现真实 Key 读取 / 硬编码 api 域名时打一行 [WARN] 提示（不代表判 FAIL）

退出码: 全过 = 0；有任何 FAIL（或子进程非零退出）= 1。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXERCISES_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXERCISES_DIR.parent

# 子进程里打印出来的标记：[PASS] A1 xxx
RUN_MARK_RE = re.compile(r"^\[PASS\]\s+([A-Za-z]\d+)\b(.*)$", re.M)
# README 里承诺要解的题号：`- [ ] **A1** xxx` / `- [ ] **A3（核心）** xxx`
README_TASK_RE = re.compile(r"^-\s*\[[ xX]\]\s*\*\*([A-Za-z]\d+)", re.M)

# 静态提醒：这些符号不代表一定在联网，只是「值得看一眼是不是依赖了真环境」。
# 注意只看**读取**：`os.environ["X"] = "sk-test"` 是给测试准备假 Key，属正当操作，别误报。
NOTE_PATTERNS: list[tuple[str, str]] = [
    ("读取真实 API Key", r"os\.environ\s*\[[^\]]*API_KEY[^\]]*\]\s*(?!=)(?!\s*=)"),
    ("读取真实 API Key", r"os\.environ\.get\s*\(\s*[\"'][^\"']*API_KEY"),
    ("读取真实 API Key", r"os\.getenv\s*\(\s*[\"'][^\"']*API_KEY"),
    ("硬编码 api 域名", r"https?://api\.\S+"),
]

GUARD_MODULE = EXERCISES_DIR / "_offline_guard.py"


@dataclass
class Question:
    qid: str
    ok: bool
    note: str = ""


@dataclass
class FileResult:
    path: str                    # 相对项目根的展示名
    script: str
    exit_code: int | None = None
    questions: list[Question] = field(default_factory=list)
    extra_fail: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for q in self.questions if q.ok)

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def ok(self) -> bool:
        return not self.extra_fail and all(q.ok for q in self.questions) and len(self.questions) > 0


def discover_scripts() -> list[Path]:
    """按目录名排序遍历 exercises/NN-*/answers.py。"""
    scripts: list[Path] = []
    for d in sorted(EXERCISES_DIR.glob("[0-9]*")):
        if not d.is_dir():
            continue
        script = d / "answers.py"
        if script.exists():
            scripts.append(script)
    return scripts


def expected_ids(script: Path) -> list[str]:
    """从**同目录 README.md** 里取这篇练习题声明要解的题号。

    故意不从 answers.py 源码里扫：源码里的标记是 `f"[PASS] {qid} {note}"` 拼出来的，
    扫不到题号；而且题目写在 README 里才是事实源——
    文档说了 A1~D3 有这些题，答案就必须一道不落地解决。
    """
    readme = script.parent / "README.md"
    if not readme.exists():
        return []
    text = readme.read_text(encoding="utf-8", errors="ignore")
    seen: list[str] = []
    for qid in README_TASK_RE.findall(text):
        if qid not in seen:
            seen.append(qid)
    return seen


def scan_notes(script: Path) -> list[str]:
    """静态提醒（不参与判成败）：这份答案有没有依赖真实环境的迹象。"""
    try:
        src = script.read_text(encoding="utf-8", errors="ignore")
    except OSError:  # pragma: no cover
        return []
    hits = []
    for name, pattern in NOTE_PATTERNS:
        if re.search(pattern, src, re.M):
            hits.append(name)
    return hits


def run_one(script: Path) -> FileResult:
    rel = os.path.relpath(script, PROJECT_ROOT)
    result = FileResult(path=rel, script=str(script))

    try:
        proc = subprocess.run(
            # 注意这里是 `-c`：先 import 离线哨兵，再由它 runpy 跑目标脚本，
            # 这样 socket 层的熔断在目标脚本执行「之前」就已经装好了。
            [
                sys.executable,
                "-u",
                "-c",
                (
                    "import sys; sys.path.insert(0, %r);\n"
                    "import _offline_guard as g;\n"
                    "g.run_guarded(%r)\n"
                )
                % (str(GUARD_MODULE.parent), str(script.resolve())),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        result.exit_code = proc.returncode
        result.stdout = proc.stdout
        result.stderr = proc.stderr
    except subprocess.TimeoutExpired as e:  # pragma: no cover
        result.exit_code = None
        result.extra_fail.append(f"超时（跑超过 300s），已按 FAIL 处理：{e}")
        result.stderr = str(e)
        return result

    marks = {m.group(1): m.group(2).strip() for m in RUN_MARK_RE.finditer(proc.stdout or "")}
    for qid in expected_ids(script):
        note = marks.get(qid, "")
        if qid in marks:
            result.questions.append(Question(qid=qid, ok=True, note=note))
        else:
            result.questions.append(
                Question(qid=qid, ok=False, note=f"stdout 里没有 [PASS] {qid} 标记")
            )

    if result.exit_code != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-1:] or ["(无输出)"]
        result.extra_fail.append(
            f"进程退出码 {result.exit_code}（{tail[0]}）"
        )

    result.warnings = scan_notes(script)
    return result


def report_human(results: list[FileResult]) -> int:
    total_pass = 0
    total_all = 0

    for r in results:
        print(f"=== {r.path} ===")
        for q in r.questions:
            flag = "PASS" if q.ok else "FAIL"
            print(f"[{flag}] {q.qid} {q.note}")
            if q.ok:
                total_pass += 1
            total_all += 1
        for msg in r.extra_fail:
            print(f"[FAIL] (文件级) {msg}")
        for w in r.warnings:
            print(f"[NOTE] {r.path} 出现真实环境依赖迹象（{w}）——不判 FAIL，但答案必须能离线复现")
        if r.exit_code is not None and r.exit_code != 0 and r.stderr:
            print("----- 子进程 stderr 末尾 -----")
            for line in (r.stderr.strip().splitlines()[-6:] or []):
                print(f"  {line}")
        print(f"--> {r.path}: {r.passed}/{r.total} 题通过\n")

    print(f"总结：{total_pass}/{total_all} 通过")
    return 0 if total_pass == total_all and total_all > 0 else 1


def report_json(results: list[FileResult]) -> int:
    total_pass = sum(q.ok for r in results for q in r.questions)
    total_all = sum(len(r.questions) for r in results)
    payload = {
        "root": str(PROJECT_ROOT),
        "files": [
            {
                "path": r.path,
                "exit_code": r.exit_code,
                "passed": r.passed,
                "total": r.total,
                "ok": r.ok,
                "questions": [{"id": q.qid, "ok": q.ok, "note": q.note} for q in r.questions],
                "failures": r.extra_fail,
                "warnings": r.warnings,
            }
            for r in results
        ],
        "summary": {"passed": total_pass, "total": total_all},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if total_pass == total_all and total_all > 0 else 1


def selftest() -> int:
    """自测：证明「离线判卷」不是一句口号 —— 拿一个真的想联网的脚本试试哨兵。

    这条之所以必须写进来：判卷脚本本身也可能串味。
    如果哪天 `_offline_guard` 被人改坏（比如忘了 install），
    所有答案还会照常「通过」，但约束已经失效了。自测就是给判卷脚本自己上的一道锁。
    """
    import tempfile
    from contextlib import redirect_stderr, redirect_stdout

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
        proc = subprocess.run(
            [
                sys.executable,
                "-u",
                "-c",
                "import sys; sys.path.insert(0, %r); import _offline_guard as g; g.run_guarded(%r)"
                % (str(GUARD_MODULE.parent), str(script)),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    denied = "NetworkAccessDenied" in (proc.stderr or "")
    marked_ok = "[PASS] Z9" in (proc.stdout or "")
    print(f"[{'PASS' if denied else 'FAIL'}] 想联网的答案进程被 socket 层拦下（退出码 {proc.returncode}）")
    print(f"[{'PASS' if marked_ok else 'FAIL'}] 它在被拦下前确实打印了假的 [PASS] 标记 —— 说明只看标记不够")
    ok = denied and marked_ok and proc.returncode != 0
    print(f"--> 自测：{'通过（离线约束真的生效）' if ok else '失败（哨兵没起作用，判卷结果不可信）'}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Project 02 练习题判卷（纯离线）")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    parser.add_argument("--quiet", action="store_true", help="只显示 FAIL 与总结")
    parser.add_argument("--selftest", action="store_true", help="验证离线哨兵是否真的生效")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    scripts = discover_scripts()
    if not scripts:
        print("没找到 exercises/NN-*/answers.py")
        return 1

    results = [run_one(s) for s in scripts]

    if args.json:
        return report_json(results)

    if args.quiet:
        for r in results:
            for q in r.questions:
                if not q.ok:
                    print(f"[FAIL] {r.path} {q.qid} {q.note}")
            for msg in r.extra_fail:
                print(f"[FAIL] {r.path} {msg}")
            for w in r.warnings:
                print(f"[NOTE] {r.path} 出现真实环境依赖迹象（{w}）——不判 FAIL，但答案必须能离线复现")
    else:
        return report_human(results)

    total_pass = sum(q.ok for r in results for q in r.questions)
    total_all = sum(len(r.questions) for r in results)
    print(f"总结：{total_pass}/{total_all} 通过")
    return 0 if total_pass == total_all and total_all > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
