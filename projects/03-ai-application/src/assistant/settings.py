"""集中式配置（对应 milestones/05、06）。

三条铁律（沿用 Project 02）：

1. 配置集中在一处 —— 想知道「这个项目要配什么」只看这个文件
2. frozen —— 启动时读一次，之后谁也改不了；要改就用 `replace()` 生成新对象
3. 不在模块顶层执行 from_env() —— 否则 import 就崩，连 pytest 都跑不起来

优先级（低 → 高）：代码默认值 → .env 文件 → 真实环境变量

Project 03 新增：temperature / top_p / max_tokens 与场景 Profile（Chapter 06）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

from assistant.errors import LLMConfigError

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

# 场景 Profile：不同任务该用不同口味（Chapter 06 的核心表）
PROFILES: dict[str, dict[str, float | int]] = {
    "extract":  {"temperature": 0.0, "max_tokens": 512},    # 抽取 / 分类：要稳
    "code":     {"temperature": 0.2, "max_tokens": 1024},   # 代码：正确性优先
    "chat":     {"temperature": 0.7, "max_tokens": 1024},   # 日常对话：自然
    "creative": {"temperature": 1.0, "max_tokens": 2048},   # 创意：发散
}

_TRUTHY = {"1", "true", "yes", "on"}


def load_dotenv(path: str = ".env") -> None:
    """把 .env 里的键值灌进 os.environ，且**不覆盖已有环境变量**。

    手写实现（约 20 行），讲清楚 python-dotenv 到底做了什么。
    关键在 setdefault：保证「真实环境变量优先于 .env」。
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key:
                continue
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def _get_str(key: str, default: str) -> str:
    return os.getenv(key, default).strip()


def _get_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as e:
        raise LLMConfigError(f"{key} 必须是数字，当前值: {raw!r}") from e


def _get_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise LLMConfigError(f"{key} 必须是整数，当前值: {raw!r}") from e


@dataclass(frozen=True)
class Settings:
    """全部配置项。frozen=True 表示不可变。"""

    api_key: str = field(repr=False)  # repr 时不打印，防泄露
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = 30.0
    max_retries: int = 2
    log_level: str = "INFO"
    json_logs: bool = False
    system_prompt: str = "你是一个简洁、耐心的中文 AI 助手。"

    # ---- Chapter 06：模型参数 ----
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 1024

    # ---- Chapter 07：预算 ----
    context_window: int = 64_000

    def for_profile(self, profile: str) -> "Settings":
        """按场景返回一份新配置（不改原对象——frozen 的好处）。"""
        if profile not in PROFILES:
            raise LLMConfigError(
                f"未知场景 {profile!r}，可选: {sorted(PROFILES)}"
            )
        return replace(self, **PROFILES[profile])

    def validate(self) -> None:
        """校验配置合法性。"""
        if not self.api_key:
            raise LLMConfigError("api_key 不能为空")
        if not self.base_url.startswith(("http://", "https://")):
            raise LLMConfigError(f"base_url 必须以 http:// 或 https:// 开头，当前: {self.base_url}")
        if self.timeout <= 0:
            raise LLMConfigError(f"timeout 必须 > 0，当前: {self.timeout}")
        if self.max_retries < 0:
            raise LLMConfigError(f"max_retries 不能为负，当前: {self.max_retries}")
        if not 0.0 <= self.temperature <= 2.0:
            raise LLMConfigError(f"temperature 必须在 0~2 之间，当前: {self.temperature}")
        if not 0.0 < self.top_p <= 1.0:
            raise LLMConfigError(f"top_p 必须在 (0, 1] 之间，当前: {self.top_p}")
        if self.max_tokens <= 0:
            raise LLMConfigError(f"max_tokens 必须 > 0，当前: {self.max_tokens}")

    @classmethod
    def from_env(cls, dotenv_path: str | None = ".env") -> "Settings":
        """从 .env + 环境变量构建配置。只在程序入口调用一次。"""
        if dotenv_path:
            load_dotenv(dotenv_path)

        api_key = _get_str("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise LLMConfigError(
                "未设置 DEEPSEEK_API_KEY。\n"
                "请复制 .env.example 为 .env 并填入你的 Key：\n"
                "    cp .env.example .env"
            )

        settings = cls(
            api_key=api_key,
            base_url=_get_str("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
            model=_get_str("DEEPSEEK_MODEL", DEFAULT_MODEL),
            timeout=_get_float("DEEPSEEK_TIMEOUT", 30.0),
            max_retries=_get_int("DEEPSEEK_MAX_RETRIES", 2),
            log_level=_get_str("LOG_LEVEL", "INFO").upper(),
            json_logs=_get_str("LOG_FORMAT", "text").lower() == "json",
            system_prompt=_get_str("SYSTEM_PROMPT", "你是一个简洁、耐心的中文 AI 助手。"),
            temperature=_get_float("DEEPSEEK_TEMPERATURE", 0.7),
            top_p=_get_float("DEEPSEEK_TOP_P", 1.0),
            max_tokens=_get_int("DEEPSEEK_MAX_TOKENS", 1024),
            context_window=_get_int("DEEPSEEK_CONTEXT_WINDOW", 64_000),
        )
        settings.validate()
        return settings
