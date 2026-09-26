"""命令行入口（接入层之一，与 api.py 共用同一个 service）。

用法：
    ai-app "用一句话解释 GIL"
    ai-app -i                      # 多轮交互
    ai-app "讲讲线程池" --stream
    ai-app "我叫小明，会 Java 和 MySQL，干了 6 年" --structured skill
    ai-app "128 乘以 37 是多少" --agent
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import replace

from assistant.errors import LLMConfigError, LLMError
from assistant.logging_setup import setup_logging
from assistant.models import REGISTRY as MODEL_REGISTRY
from assistant.prompts import DEFAULT_SYSTEM
from assistant.service import build_service
from assistant.settings import PROFILES, Settings

logger = logging.getLogger(__name__)

BANNER = """AI Application v0.1（Project 03）
命令：/reset 清空历史    /usage 查看消耗    /quit 退出"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai-app", description="Project 03 — AI Application")
    p.add_argument("question", nargs="?", help="要问的问题")
    p.add_argument("-i", "--interactive", action="store_true", help="多轮交互")
    p.add_argument("--stream", action="store_true", help="流式输出")
    p.add_argument("--structured", metavar="SCHEMA", choices=sorted(MODEL_REGISTRY),
                   help=f"结构化输出，可选: {sorted(MODEL_REGISTRY)}")
    p.add_argument("--agent", action="store_true", help="启用工具调用（Function Calling）")
    p.add_argument("--profile", choices=sorted(PROFILES), help="场景参数预设")
    p.add_argument("--temperature", type=float, help="覆盖 temperature")
    p.add_argument("--max-tokens", type=int, help="覆盖 max_tokens")
    p.add_argument("--json-logs", action="store_true", help="JSON 格式日志")
    p.add_argument("--log-level", help="日志级别 DEBUG/INFO/WARNING")
    p.add_argument("--fake", action="store_true", help="离线冒烟（不联网）")
    return p


def make_settings(args: argparse.Namespace) -> Settings:
    """构建配置：场景 Profile → 命令行覆盖 → 校验。"""
    settings = Settings(api_key="fake-key") if args.fake else Settings.from_env()

    if args.profile:
        settings = replace(settings, **PROFILES[args.profile])
    if args.temperature is not None:
        settings = replace(settings, temperature=args.temperature)
    if args.max_tokens is not None:
        settings = replace(settings, max_tokens=args.max_tokens)

    settings.validate()
    return settings


async def run_interactive(service, use_stream: bool) -> int:
    print(BANNER)
    loop = asyncio.get_running_loop()
    while True:
        try:
            text = await loop.run_in_executor(None, input, "\n你 > ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        text = text.strip()
        if not text:
            continue
        if text == "/quit":
            return 0
        if text == "/reset":
            service.reset()
            print("（历史已清空）")
            continue
        if text == "/usage":
            print(service.usage.as_dict())
            continue

        try:
            if use_stream:
                print("AI > ", end="", flush=True)
                async for delta in service.astream(text):
                    print(delta, end="", flush=True)
                print()
            else:
                print(f"AI > {await service.ask(text)}")
        except LLMError as e:
            print(f"[错误] {e}")


async def run_once(service, args: argparse.Namespace) -> int:
    text = args.question or ""
    try:
        if args.structured:
            model_cls = MODEL_REGISTRY[args.structured]
            result = await service.ask_structured(text, model_cls)
            print(result.model_dump_json(indent=2, ensure_ascii=False))
        elif args.agent:
            print(await service.run_agent(text))
        elif args.stream:
            async for delta in service.astream(text):
                print(delta, end="", flush=True)
            print()
        else:
            print(await service.ask(text))
    except LLMError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    return 0


async def amain(argv: list[str] | None = None) -> int:
    """整个程序只跑一次事件循环（P02 踩过的坑：两次 asyncio.run 会关错连接池）。"""
    args = build_parser().parse_args(argv)
    try:
        settings = make_settings(args)
    except LLMConfigError as e:
        print(f"[配置错误] {e}", file=sys.stderr)
        return 2

    setup_logging(args.log_level or settings.log_level, args.json_logs or settings.json_logs)

    # system prompt 也走模板，不在这里写裸字符串
    settings = replace(settings, system_prompt=DEFAULT_SYSTEM.render(max_sentences=3))

    from assistant.client import FakeClient

    client = FakeClient(reply="（离线冒烟）FakeClient 的固定回答") if args.fake else None
    service = build_service(settings, client)

    try:
        if args.interactive or not args.question:
            code = await run_interactive(service, args.stream)
        else:
            code = await run_once(service, args)
        logger.info("本次会话消耗", extra={"extra_fields": {
            **service.usage.as_dict(),
            "cost_cny": round(service.cost_so_far(), 4),
        }})
        return code
    finally:
        await service.client.aclose()


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    sys.exit(main())
