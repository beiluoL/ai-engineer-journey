#!/usr/bin/env python3
"""仓库健康体检 —— 结构完整性 / 证据链 / 配图 / 死链 / 密钥。

为什么需要它
------------
`check_links.py` 只回答一个问题：「链接指向的文件在不在」。
它**不会**发现下面这些同样会让人误判项目状态的问题：

- 项目缺 README / 缺依赖声明 / 缺 .env.example（克隆后跑不起来）
- demo 的 stdout 存在本地但没入库（文档里的数字失去可复现的证据链）
  覆盖两套约定：projects/*/demos/out/ 与 python-practice/*/assets/run*.txt
- 图片躺在 assets/ 里但没有任何文档引用（孤儿图，白占体积）
- 文档**一个图都没有**（违反「所有文档必须配图」的约定）
- PROGRESS 里写的「assets 共 NN 张」与实际文件数不一致（文档漂移）
- 硬编码的 API Key 混进仓库

本脚本把这些检查合并成一次可读的体检报告，退出码非 0 表示有 ERROR 级问题。

用法
----
    python3 scripts/audit.py            # 全部检查
    python3 scripts/audit.py --quick    # 跳过死链检查（该检查较慢）

设计约定
--------
- 只读：本脚本绝不修改任何文件
- 输出宽度控制在 78 字符内，便于直接渲染成终端截图
- 结果按 ERROR / WARN / INFO 三级，方便 CI 或人工判断优先级
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 76

# 天然不需要配图的文档：根导航、索引页、题库、RAG 语料、自测清单
# 注意：projects/*/README.md（项目主页）**故意不在此列** —— 它是项目门面，
# 本来就该有一张架构/能力图，属于需要补的缺口。
IMAGE_EXEMPT = {
    "README.md",
    "PROGRESS.md",
    "ROADMAP.md",
    "KNOWLEDGE-MAP.md",
    "CONTRIBUTING.md",
    "mistakes/README.md",
    "publishing/README.md",
    "publishing/tutorials/README.md",
    "publishing/articles/README.md",
    "publishing/finetune-series/README.md",
    "audit/README.md",  # 体检档案索引，本身是导航页
}
IMAGE_EXEMPT_DIRS = ("/exercises/", "/data/")
IMAGE_EXEMPT_NAMES = {"LEARNING.md", "OVERVIEW.md"}


def needs_no_image(path: str) -> bool:
    if path in IMAGE_EXEMPT:
        return True
    if any(d in path for d in IMAGE_EXEMPT_DIRS):
        return True
    return os.path.basename(path) in IMAGE_EXEMPT_NAMES


errors: list[str] = []
warnings: list[str] = []
infos: list[str] = []


# ---------------------------------------------------------------- 基础工具


def tracked_files() -> list[str]:
    """返回 git 跟踪的文件列表。

    必须用 -z：默认模式下 git 会把含非 ASCII 的路径用双引号转义成
    ``"publishing/finetune-series/Day1-\\345\\244..."``，既读不到文件也会让
    后缀判断（.endswith(".md")）失效——本仓库有 33 篇中文名文档会因此凭空消失。
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [f for f in out.split("\0") if f]


def read(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rule(title: str) -> None:
    pad = WIDTH - len(title) - 4
    print(f"\n── {title} " + "─" * max(pad, 2))


def say(level: str, msg: str) -> None:
    tag = {"E": "ERROR", "W": "WARN ", "I": "INFO "}[level]
    print(f"  [{tag}] {msg}")
    {"E": errors, "W": warnings, "I": infos}[level].append(msg)


def count_lines(paths: list[str], suffix: str) -> tuple[int, int]:
    files = [p for p in paths if p.endswith(suffix)]
    total = 0
    for p in files:
        try:
            with open(ROOT / p, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return len(files), total


# ---------------------------------------------------------------- 各项检查


def check_scale(files: list[str]) -> None:
    rule("规模概览")
    md_n, md_l = count_lines(files, ".md")
    py_n, py_l = count_lines(files, ".py")
    png = [f for f in files if f.endswith(".png")]
    svg = [f for f in files if f.endswith(".svg")]
    print(f"  跟踪文件 {len(files)} 个")
    print(f"  Markdown {md_n} 篇 / {md_l:,} 行")
    print(f"  Python   {py_n} 个 / {py_l:,} 行")
    print(f"  配图     {len(png)} PNG + {len(svg)} SVG")
    infos.append(f"md={md_n} py={py_n} img={len(png)+len(svg)}")


STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {
    "__future__",
    "typing",
    "typing_extensions",  # 保守起见当标准库处理
}


def third_party_imports(files: list[str], base: str) -> set[str]:
    """项目真正 import 的第三方顶层包名（排除标准库与本项目自身模块）。

    用于判断「没有 pyproject.toml」到底是缺陷还是合理：
    纯标准库项目（如 P01）不需要依赖声明，有第三方依赖却没声明才是问题。
    """
    found: set[str] = set()
    local: set[str] = set()
    # 本地模块的可靠信号：项目内任何含 __init__.py 的目录名。
    # 这样无论包放在 src/、demos/ 还是 pipelines/ 下都能识别
    # （P01 的 demos/pkgdemo、P07 的 pipelines/llm_client 都属此列）。
    for f in files:
        if f.startswith(f"{base}/") and f.endswith("/__init__.py"):
            local.add(f.split("/")[-2])
    for f in files:
        if not f.startswith(f"{base}/") or not f.endswith(".py") or "/tests/" in f:
            continue
        for m in re.finditer(
            r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", read(f), re.MULTILINE
        ):
            mod = m.group(1)
            if mod in STDLIB or mod in local or mod.startswith("_"):
                continue
            found.add(mod)
    return found


def project_needs_key(files: list[str], base: str) -> bool:
    """项目是否真的需要外部凭据：看代码里有没有读 KEY / TOKEN 类环境变量。

    只对**读取**告警；``os.environ["X"] = "sk-test"`` 是测试准备假 Key，不算。
    """
    pat = re.compile(r"os\.(?:environ|getenv)[\.\[\(]\s*[\"']([A-Z_]+)[\"']")
    write_pat = re.compile(r"os\.environ\[\s*[\"'][A-Z_]+[\"']\s*\]\s*=")
    for f in files:
        if not f.startswith(f"{base}/") or not f.endswith(".py"):
            continue
        if "/tests/" in f or "/.venv/" in f:
            continue
        txt = read(f)
        for m in pat.finditer(txt):
            if not re.search(r"KEY|TOKEN|SECRET", m.group(1)):
                continue
            if write_pat.search(txt[max(0, m.start() - 40) : m.end() + 5]):
                continue
            return True
    return False


def check_projects(files: list[str]) -> None:
    rule("项目骨架完整性")
    print(f"  {'项目':<34}{'MD':>3}{'MI':>4}{'SRC':>5}{'TST':>5}{'DEP':>5}{'ENV':>5}")
    proj_dirs = sorted(
        {f.split("/")[1] for f in files if f.startswith("projects/") and f.count("/") > 1}
    )
    for name in proj_dirs:
        base = f"projects/{name}"
        has_readme = f"{base}/README.md" in files
        miles = [f for f in files if f.startswith(f"{base}/milestones/") and f.endswith(".md")]
        has_src = any(f.startswith(f"{base}/src/") for f in files)
        tests = [f for f in files if f.startswith(f"{base}/tests/") and f.endswith(".py")]
        # P01 的测试在 src/tests 下，兼容两种布局
        if not tests:
            tests = [f for f in files if re.search(rf"^{base}/src/tests/.*\.py$", f)]
        dep = (ROOT / base / "pyproject.toml").exists() or (
            ROOT / base / "requirements.txt"
        ).exists()
        env = any(f.endswith(".env.example") for f in files if f.startswith(base))
        needs_key = project_needs_key(files, base)
        print(
            f"  {name:<34}{'Y' if has_readme else '-':>3}{len(miles):>4}"
            f"{'Y' if has_src else '-':>5}{len(tests):>5}"
            f"{'Y' if dep else '-':>5}{'Y' if env else '-':>5}"
        )
        if not miles:
            say("E", f"{name}: milestones/ 为空 —— 项目没有正文")
        if not tests:
            say("W", f"{name}: 未发现单元测试")
        if not dep:
            tpi = third_party_imports(files, base)
            if tpi:
                say("W", f"{name}: import 了第三方包 {sorted(tpi)} 却无依赖声明文件")
            else:
                say("I", f"{name}: 纯标准库实现，无需依赖声明")
        if needs_key and not env:
            say("W", f"{name}: 代码读环境变量却无 .env.example（克隆后不知道要配什么）")


def check_evidence(files: list[str]) -> None:
    rule("证据链：demo 输出是否入库")
    proj_dirs = sorted(
        {f.split("/")[1] for f in files if f.startswith("projects/") and f.count("/") > 1}
    )
    for name in proj_dirs:
        base = ROOT / "projects" / name
        out_dirs = [p for p in base.rglob("out") if p.is_dir() and "site-packages" not in str(p)]
        local = 0
        for d in out_dirs:
            local += sum(1 for p in d.iterdir() if p.is_file())
        tracked = sum(1 for f in files if f.startswith(f"projects/{name}/") and "/out/" in f)
        if local and not tracked:
            say("W", f"{name}: 本地有 {local} 个 demo 输出，但一个都没入库（证据链断了）")
        elif local > tracked:
            say("I", f"{name}: demo 输出 本地 {local} / 入库 {tracked}")

    # 练手层（python-practice/）用的是「<项目>/assets/run*.txt」这一约定 ——
    # 它既是终端截图的原素材，也是「文档里的数字确实来自一次真实运行」的证据。
    # 和 projects/ 的 demos/out/ 指向同一件事，只是路径约定不同，所以单列一段。
    practice = sorted(
        {
            f.split("/")[1]
            for f in files
            if f.startswith("python-practice/") and f.count("/") > 1
        }
    )
    if practice:
        broken, checked = [], 0
        for name in practice:
            assets = ROOT / "python-practice" / name / "assets"
            if not assets.is_dir():
                continue
            checked += 1
            if not any(assets.glob("run*.txt")):  # 没有本地运行输出，无从谈起
                continue
            tracked = sum(
                1
                for f in files
                if f.startswith(f"python-practice/{name}/assets/") and f.endswith(".txt")
            )
            if not tracked:
                broken.append(name)
        if broken:
            say("W", f"练手层证据链断了（运行输出未入库）: {', '.join(broken)}")
        elif checked:
            print(f"  练手层 {checked} 个项目：运行输出已随项目入库 ✓")


def check_images(files: list[str]) -> None:
    rule("配图：孤儿图 + 零配图文档")
    images = [f for f in files if re.search(r"assets/.*\.(png|svg|jpg)$", f)]
    referenced: set[str] = set()
    # 只在「文档与代码」里找引用。**不要扫 .txt**：
    # demos/out/*.txt 与体检归档会把图片路径当普通文本抄一遍，
    # 那会让「孤儿图检测」自我欺骗——工具报告说某张图没人引用，
    # 而它自己的输出存档里恰好写了这张图的名字，于是所有孤儿图凭空消失。
    scannable = (".md", ".html", ".htm", ".py", ".yml", ".yaml", ".json", ".ipynb")
    for f in files:
        if not f.endswith(scannable):
            continue
        for m in re.findall(r"[\w./-]*assets/[\w.\-]+\.(?:png|svg|jpg)", read(f)):
            referenced.add(os.path.basename(m))
    orphans = [f for f in images if os.path.basename(f) not in referenced]
    print(f"  配图 {len(images)} 张，被引用 {len(images) - len(orphans)} 张")
    for f in orphans:
        say("I", f"孤儿图（无文档引用）: {f}")

    zero = []
    for f in files:
        if not f.endswith(".md") or needs_no_image(f):
            continue
        if not re.search(r"!\[[^\]]*\]\([^)]+\)", read(f)):
            zero.append(f)
    drafts = [f for f in zero if f.startswith("publishing/finetune-series/")]
    zero = [f for f in zero if f not in drafts]
    print(f"  零配图文档 {len(zero)} 篇（已排除索引页 / 题库 / 语料 / 自测清单）")
    print(f"  另有 {len(drafts)} 篇草稿库文档零配图（📝 草稿，未纳入要求）")
    project_readmes = [f for f in zero if re.fullmatch(r"projects/[^/]+/README\.md", f)]
    for f in project_readmes:
        say("W", f"项目主页零配图: {f}")
    rest = [f for f in zero if f not in project_readmes]
    print(f"  其余零配图文档 {len(rest)} 篇：")
    for f in rest:
        print(f"        · {f}")
    infos.append(f"零配图（不含草稿）{len(zero)} 篇")


def check_progress_drift(files: list[str]) -> None:
    rule("文档漂移：PROGRESS 声明的图数 vs 实际")
    txt = read("PROGRESS.md")
    if not txt:
        say("E", "PROGRESS.md 读不到")
        return
    # 形如 "assets 共 44 张" / "assets 共 22 张" 出现在 Project NN 的行里
    checked = 0
    for line in txt.split("\n"):
        m = re.search(r"\|\s*Project\s+(\d{2})\b.*?assets\s*共\s*(\d+)\s*张", line)
        if not m:
            continue
        num, claimed = m.group(1), int(m.group(2))
        actual = len(
            [f for f in files if re.match(rf"projects/{num}-[^/]+/assets/.*\.png$", f)]
        )
        checked += 1
        if actual != claimed:
            say("W", f"P{num}: PROGRESS 写 {claimed} 张，实际 {actual} 张")
        else:
            print(f"  P{num}: {claimed} 张 ✓")
    if not checked:
        say("I", "未找到可解析的 assets 声明")


def check_keys(files: list[str]) -> None:
    rule("安全：密钥与敏感文件")
    patterns = {
        "OpenAI 风格 Key": r"sk-[A-Za-z0-9]{20,}",
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "GitHub Token": r"ghp_[A-Za-z0-9]{30,}",
        "Slack Token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    }
    hits = []
    for f in files:
        if f.endswith((".png", ".svg", ".jpg")):
            continue
        txt = read(f)
        for label, pat in patterns.items():
            for m in re.finditer(pat, txt):
                # 显式忽略测试用的假 Key
                frag = m.group(0)
                if any(k in frag.lower() for k in ("test", "demo", "fake", "example")):
                    continue
                hits.append((f, label, frag[:12] + "..."))
    for f, label, frag in hits:
        say("E", f"{f}: 疑似 {label} {frag}")
    if not hits:
        print("  未发现硬编码密钥 ✓")

    sensitive = [
        f for f in files if re.search(r"(^|/)\.env$|\.key$|credential|secret", f, re.I)
    ]
    for f in sensitive:
        say("E", f"疑似敏感文件入库: {f}")
    if not sensitive:
        print("  未发现 .env / .key 类文件入库 ✓")


def check_cross_refs(files: list[str]) -> None:
    rule("知识层交叉引用")
    fwd = 0  # llm-fundamentals -> projects/
    for f in files:
        if f.startswith("llm-fundamentals/"):
            fwd += len(re.findall(r"\.\./projects/", read(f)))
    back = 0  # projects/ -> llm-fundamentals/
    for f in files:
        if f.startswith("projects/") and f.endswith(".md"):
            back += len(re.findall(r"llm-fundamentals/", read(f)))
    print(f"  llm-fundamentals → projects/ 链接 {fwd} 条")
    print(f"  projects/ → llm-fundamentals/ 链接 {back} 条")
    if fwd == 0 and back == 0:
        say("W", "两个知识层之间没有任何真实相对链接（README 声称『互相引用』需修正）")
    elif fwd and back:
        print("  双向引用正常 ✓")


def run_all_tests(files: list[str]) -> None:
    """实跑每个项目的测试套件并打印汇总表（可选，较慢）。

    为什么要做这件事：CI 只门禁了其中两个项目，仓库里其余 1100+ 项测试
    没有任何地方会「定期实跑一次」。本函数把「实跑」变成一条可复现命令，
    也让「全绿」这个说法有当场证据，而不是引用记忆。
    """
    rule("测试实跑（--tests）")
    fallback = os.environ.get("AUDIT_PYTHON", sys.executable)
    proj_dirs = sorted(
        {f.split("/")[1] for f in files if f.startswith("projects/") and f.count("/") > 1}
    )
    print(f"  {'项目':<32}{'测试数':>8}  结果")
    total = 0
    failed = []
    for name in proj_dirs:
        base = ROOT / "projects" / name
        tests = list(base.glob("tests/test_*.py")) + list(base.glob("src/tests/test_*.py"))
        if not tests:
            print(f"  {name:<32}{'-':>8}  无测试")
            warnings.append(f"{name}: 无测试")
            continue
        venv_py = base / ".venv" / "bin" / "python"
        py = str(venv_py) if venv_py.exists() else fallback
        if (base / "src" / "tests").is_dir() and not (base / "tests").is_dir():
            cmd = [py, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
            cwd = base / "src"
        else:
            cmd = [py, "-m", "pytest", "--tb=short"]
            cwd = base
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        blob = r.stdout + r.stderr
        m = re.search(r"(\d+) (passed|tests?)", blob)
        n = int(m.group(1)) if m else 0
        ok = r.returncode == 0
        print(f"  {name:<32}{n:>8}  {'passed' if ok else 'FAILED'}")
        total += n
        if not ok:
            failed.append(name)
    print(f"  {'合计':<32}{total:>8}")
    if failed:
        say("E", f"测试未通过：{', '.join(failed)}")
    else:
        print("  全部通过 ✓")


def check_links(quick: bool) -> None:
    rule("链接与坏图（check_links）")
    if quick:
        say("I", "已跳过（--quick）")
        return
    script = ROOT / "scripts" / "check_links.py"
    if not script.exists():
        say("E", "scripts/check_links.py 不存在")
        return
    r = subprocess.run(
        [sys.executable, str(script), "--strict"], cwd=ROOT, capture_output=True, text=True
    )
    tail = [ln for ln in r.stdout.strip().split("\n") if ln.strip()][-2:]
    for ln in tail:
        print(f"  {ln}")
    if r.returncode != 0:
        say("E", "check_links 未通过")


# ---------------------------------------------------------------- 主流程


def main() -> int:
    ap = argparse.ArgumentParser(description="仓库健康体检")
    ap.add_argument("--quick", action="store_true", help="跳过 check_links（较慢）")
    ap.add_argument("--tests", action="store_true", help="额外实跑全部项目测试（很慢）")
    args = ap.parse_args()

    print("=" * WIDTH)
    print("  仓库健康体检 · ai-engineer-journey")
    print("=" * WIDTH)

    files = tracked_files()
    check_scale(files)
    check_projects(files)
    check_evidence(files)
    check_images(files)
    check_progress_drift(files)
    check_cross_refs(files)
    check_keys(files)
    check_links(args.quick)
    if args.tests:
        run_all_tests(files)

    print("\n" + "=" * WIDTH)
    print(f"  结论：ERROR {len(errors)} · WARN {len(warnings)} · INFO {len(infos)}")
    print("=" * WIDTH)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
