"""Milestone 05 实验：配置与环境变量。

真实跑 Settings.from_env()，看四件事：
1. 缺 Key 时报的是「人能照着做」的错，不是 KeyError；
2. api_key 字段 repr=False，日志里不会泄露；
3. 环境变量能覆盖默认值；
4. 非法值在 validate() 里被拦下。

注意：脚本里用的是占位 Key（sk-demo-...），不会读取真实凭据，
     也不会打印任何真实 Key —— 只打印长度和前缀。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from assistant.errors import LLMConfigError  # noqa: E402
from assistant.settings import Settings  # noqa: E402

PLACEHOLDER = "sk-demo-0123456789abcdef"


def show(label: str, text: str) -> None:
    print(f"\n===== {label} =====")
    print(text)


def main() -> None:
    print("当前工作目录:", Path.cwd().name)

    show("1. 缺 Key：报错要能照着做", "")
    saved = os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        Settings.from_env()
    except LLMConfigError as exc:
        print("LLMConfigError:")
        for line in str(exc).splitlines():
            print("   ", line)
    print("  → 不是 KeyError('DEEPSEEK_API_KEY')，而是告诉你下一步该敲什么命令")

    show("2. 有 Key：正常构建，且 repr 里看不到 api_key", "")
    os.environ["DEEPSEEK_API_KEY"] = PLACEHOLDER
    s = Settings.from_env()
    print("  repr(settings) :", s)
    print("  'sk-' 出现在 repr 里吗 :", "sk-" in repr(s))
    print(f"  api_key 长度/前缀      : {len(s.api_key)} / {s.api_key[:7]}...")
    print("  → repr=False 挡住了日志泄露，但字段本身照常可用")

    show("3. 环境变量覆盖默认值", "")
    os.environ["DEEPSEEK_MODEL"] = "deepseek-reasoner"
    os.environ["DEEPSEEK_TIMEOUT"] = "12.5"
    os.environ["LOG_FORMAT"] = "json"
    s2 = Settings.from_env()
    print(f"  默认 model / timeout / json_logs : {Settings.model.__class__.__name__} / 30.0 / False")
    print(f"  覆盖后 model / timeout / json_logs : {s2.model} / {s2.timeout} / {s2.json_logs}")
    print("  → 改配置不改动代码：Docker / K8s 里靠的就是这个")

    show("4. 非法值：validate() 拦下来", "")
    bad = Settings(api_key="x", base_url="api.deepseek.com")  # 少了 scheme
    try:
        bad.validate()
    except LLMConfigError as exc:
        print("  LLMConfigError:", exc)
    bad2 = Settings(api_key="x", timeout=0)
    try:
        bad2.validate()
    except LLMConfigError as exc:
        print("  LLMConfigError:", exc)
    print("  → 起步就校验，别等第一次请求才发现配置是坏的")

    # 还原现场
    for key in ("DEEPSEEK_MODEL", "DEEPSEEK_TIMEOUT", "LOG_FORMAT"):
        os.environ.pop(key, None)
    if saved:
        os.environ["DEEPSEEK_API_KEY"] = saved
    else:
        os.environ.pop("DEEPSEEK_API_KEY", None)


if __name__ == "__main__":
    main()
