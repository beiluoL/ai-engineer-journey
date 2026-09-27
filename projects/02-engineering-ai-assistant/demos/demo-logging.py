"""Milestone 06 实验：日志。

看五件事：
1. print 打出来的「日志」缺了什么；
2. 文本格式给人看，JSON 格式给机器看（一行一个对象）；
3. **坑**：标准 `extra={"k": v}` 不会进 JSON —— JsonFormatter 只认 extra_fields；
4. 敏感头必须脱敏后再记；
5. 异常堆栈要能进日志（exc_info）。
"""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from assistant.logging_setup import JsonFormatter, redact_headers, setup_logging  # noqa: E402


def capture(fn) -> str:
    """把日志抓成字符串，方便并排对照。"""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("demo.json")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fn(logger)
    handler.flush()
    return buf.getvalue()


def main() -> None:
    print("===== 1. print() 打出来的「日志」缺了什么 =====")
    print("请求发出 model=deepseek-chat")
    print("  → 没有时间、级别、模块名，也没法按级别关掉；生产环境不可接受")

    print("\n===== 2. 文本格式（给人看）=====")
    text_logger = logging.getLogger("demo.text")
    text_logger.handlers = [logging.StreamHandler(sys.stdout)]
    text_logger.setLevel(logging.DEBUG)
    text_logger.propagate = False
    for h in text_logger.handlers:
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
    text_logger.info("请求发出")
    text_logger.warning("重试第 1 次")
    print("  → 本地开发看这个；一行到底发生了什么，肉眼可读")

    print("\n===== 3. JSON 格式（给机器看，一行一个对象）=====")
    out = capture(lambda lg: (
        lg.info("请求发出"),
        lg.warning("重试第 1 次", extra={"extra_fields": {"retry": 1, "reason": "timeout"}}),
    ))
    for line in out.strip().splitlines():
        print("  " + line)
    print("  → 一行一个 JSON，可被 Filebeat / Loki 直接采集并按字段过滤")

    print("\n===== 4. 坑：标准 extra= 不会进 JSON =====")
    plain = capture(lambda lg: lg.info("请求发出", extra={"model": "deepseek-chat"}))
    print("  写法 A  logger.info(..., extra={'model': 'deepseek-chat'})")
    print("  结果    " + plain.strip())
    print("  → model 不见了，而且不报错（静默丢失）")
    right = capture(lambda lg: lg.info(
        "请求发出", extra={"extra_fields": {"model": "deepseek-chat", "tokens": 128}}))
    print("  写法 B  logger.info(..., extra={'extra_fields': {'model': ..., 'tokens': ...}})")
    print("  结果    " + right.strip())
    print("  → JsonFormatter 只读 record.extra_fields；想结构化就显式传这个键")

    print("\n===== 5. 异常堆栈要进日志 =====")
    exc_out = capture(lambda lg: (
        lg.error("请求失败", exc_info=True) if False else
        _raise_and_log(lg)
    ))
    print("  " + exc_out.strip().splitlines()[0][:150] + " ...")
    print("  → JsonFormatter 把堆栈放进 exc 字段，一行 JSON 也能带完整上下文")

    print("\n===== 6. 敏感头必须脱敏后再记 =====")
    headers = {
        "Authorization": "Bearer sk-real-key-must-not-leak",
        "Content-Type": "application/json",
        "X-Request-Id": "req-7f3a",
    }
    print("  原始:", headers)
    print("  脱敏:", redact_headers(headers))
    print("  → 直接 logger.info(headers) 等于把 Key 写进日志文件")

    print("\n===== 7. setup_logging(json_format=True) 的真实效果 =====")
    setup_logging(level="INFO", json_format=True)
    logging.getLogger("assistant.demo").info(
        "服务启动完成", extra={"extra_fields": {"model": "deepseek-chat", "port": 8000}})
    print("  → 上面这行就是标准输出里的 JSON，可直接被采集")


def _raise_and_log(logger: logging.Logger) -> None:
    try:
        raise ValueError("上游返回 500")
    except ValueError:
        logger.error("请求最终失败", exc_info=True)


if __name__ == "__main__":
    main()
