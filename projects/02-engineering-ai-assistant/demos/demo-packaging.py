"""Chapter 08 演示 —— 打包：pyproject.toml 解析 / 元数据 / 真的打一个 wheel / 入口点。

对应 milestones/08-packaging.md 的 3.1 / 3.4 / 3.5 / 4 / 挑战 1 & 3：

    pyproject.toml         → 用标准库 tomllib 读出来看看每个字段
    importlib.metadata     → 已安装包里读到的元数据（version / requires / entry point）
    真的构建 wheel          → python -m pip wheel .，再打开 zip 看装进去的是什么
    入口点                  → python -m assistant.cli 能用 = [project.scripts] 生效

运行：

    python3 demos/demo-packaging.py
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
import zipfile
import importlib.util
from importlib.metadata import entry_points, metadata, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / ".tmp" / "demo-dist"          # 产物放这里，跑完可删；.tmp/ 已在 .gitignore


def main() -> None:
    # ---- 1. pyproject.toml 长什么样 ----
    print("=" * 62)
    print("1. pyproject.toml（PEP 621 元数据，取代 setup.py）")
    print("=" * 62)
    with open(ROOT / "pyproject.toml", "rb") as f:
        meta = tomllib.load(f)
    project = meta["project"]
    print(f"  name            : {project['name']}")
    print(f"  version         : {project['version']}")
    print(f"  requires-python : {project['requires-python']}")
    print(f"  dependencies    : {project['dependencies']}")
    for group, deps in project["optional-dependencies"].items():
        print(f"  optional[{group}]  : {deps}")
    print(f"  [project.scripts] : {project['scripts']}")
    print(f"  packages.find     : {meta['tool']['setuptools']['packages']['find']}")

    # ---- 2. 已安装包的元数据 ----
    print()
    print("=" * 62)
    print("2. importlib.metadata：从已安装状态读回元数据")
    print("=" * 62)
    print(f"  importlib.metadata.version('engineering-ai-assistant') = {version('engineering-ai-assistant')}")
    dist_meta = metadata("engineering-ai-assistant")
    print(f"  Summary         : {dist_meta['Summary']}")
    print(f"  Requires-Python : {dist_meta['Requires-Python']}")
    print("  Requires-Dist   :")
    for req in dist_meta.get_all("Requires-Dist") or []:
        print(f"    - {req}")
    eps = [ep.name for ep in entry_points(group="console_scripts") if ep.value.startswith("assistant")]
    print(f"  控制台入口点     : {eps}  → 装完就能在任意目录敲 ai-assistant")

    spec = importlib.util.find_spec("assistant")
    print(f"  import assistant → {spec.origin}")
    print("  （src layout + editable 安装：import 到的是源码目录，不是副本）")

    # ---- 3. 真的构建一个 wheel ----
    print()
    print("=" * 62)
    print("3. 真的打一个 wheel：python -m pip wheel . --no-deps -w .tmp/demo-dist")
    print("=" * 62)
    DIST.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(DIST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    for line in (proc.stdout + proc.stderr).splitlines():
        if "Created wheel" in line and "filename=" in line:
            print("  " + line.split("filename=")[1].split()[0])
        elif "Successfully built" in line:
            print("  " + line.strip())
    wheel = sorted(DIST.glob("*.whl"))[-1]
    print(f"\n  wheel 文件: {wheel.name}  ({wheel.stat().st_size / 1024:.1f} KB)")
    print("  里面装了什么：")
    for name in zipfile.ZipFile(wheel).namelist():
        if name.endswith((".py", "entry_points.txt")):
            print(f"    - {name}")

    # ---- 4. 入口点真的能用 ----
    print()
    print("=" * 62)
    print("4. 入口点：[project.scripts] 的效果")
    print("=" * 62)
    print("$ python3 -m assistant.cli --help")
    cli = subprocess.run(
        [sys.executable, "-m", "assistant.cli", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    for line in cli.stdout.splitlines()[:5]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
