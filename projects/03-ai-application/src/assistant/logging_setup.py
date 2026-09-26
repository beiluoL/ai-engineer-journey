"""日志配置（对应 milestones/06-logging.md）。

唯一原则：

- **只有程序入口调用 setup_logging()**
- 库模块只写 `logger = logging.getLogger(__name__)`，绝不配置 handler

否则会污染使用者的输出，或导致每条日志打两遍。
"""

from __future__ import annotations

import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    """结构化日志：给 ELK / Loki / 云日志服务用。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """人类可读日志：本地开发用。"""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
            datefmt="%H:%M:%S",
        )


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """配置根 logger。只在 main() / lifespan 里调用一次。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_format else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()   # 防止重复输出（坑 2）
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 第三方库的 INFO 日志太吵（每条请求一行），默认压到 WARNING，
    # 想看 HTTP 细节时把 LOG_LEVEL 调到 DEBUG 即可。
    if level.upper() != "DEBUG":
        for noisy in ("httpx", "httpcore"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """日志脱敏：把 Authorization / api-key 打码（坑 4）。"""
    sensitive = {"authorization", "api-key", "x-api-key"}
    return {
        k: ("***" if k.lower() in sensitive else v)
        for k, v in headers.items()
    }
