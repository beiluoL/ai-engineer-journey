"""配置加载：环境变量 + 本地 .env 文件（对应 milestones/08-venv-pip.md 的环境变量部分）。

安全约定：
- 真实 Key 只存在于环境变量或本地 .env（已被 .gitignore 排除）；
- 本模块绝不打印完整 Key。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from assistant.errors import LLMConfigError

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60.0


@dataclass
class Config:
    """一次 LLM 调用所需的全部配置。"""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT


def _read_dotenv(path: str | Path = ".env") -> dict[str, str]:
    """极简 .env 解析器（零依赖版）。

    支持 "KEY=VALUE" 与可选的 export 前缀；# 开头的行视为注释。
    不做取值优先级覆盖：已存在的环境变量优先于 .env 文件中的值。
    """
    env_file = Path(path)
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def load_config(env_file: str | Path = ".env") -> Config:
    """加载配置。缺失 API Key 时抛出带修复指引的 LLMConfigError。"""
    dotenv = _read_dotenv(env_file)

    def get(name: str) -> str | None:
        # 真实环境变量优先，.env 兜底
        return os.environ.get(name) or dotenv.get(name)

    api_key = get("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMConfigError(
            "未找到 DEEPSEEK_API_KEY。请任选其一：\n"
            "  1. 设置环境变量: export DEEPSEEK_API_KEY='sk-...'\n"
            "  2. 复制 .env.example 为 .env，并填入真实 Key"
        )

    base_url = get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL
    model = get("DEFAULT_MODEL") or DEFAULT_MODEL
    timeout_raw = get("LLM_TIMEOUT")
    timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT

    return Config(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
