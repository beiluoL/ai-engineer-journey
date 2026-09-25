"""命令行入口（对应 milestones/08-packaging.md 的 [project.scripts]）。

装包后可直接执行：

    ai-assistant "用一句话解释 GIL"
    ai-assistant --interactive
    ai-assistant --stream "讲个笑话"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from assistant.errors import LLMError
from assistant.logging_setup import setup_logging
from assistant.service import AssistantService, build_service
from assistant.settings import Settings

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-assistant",
        description="工程化的 Python AI 助手（异步 / 类型安全 / 可测试）",
    )
    p.add_argument("question", nargs="?", help="要问的问题；不给则进入交互模式")
    p.add_argument("-i", "--interactive", action="store_true", help="多轮对话模式")
    p.add_argument("-s", "--stream", action="store_true", help="流式输出（逐字打印）")
    p.add_argument("--fake", action="store_true", help="用 FakeClient 跑通流程，不联网不花钱")
    p.add_argument("--log-level", default=None, help="DEBUG / INFO / WARNING / ERROR")
    p.add_argument("--json-logs", action="store_true", help="输出 JSON 格式日志")
    return p


async def run_interactive(service: AssistantService, stream: bool) -> None:
    print("进入交互模式（输入 /reset 清空历史，/quit 或 Ctrl-D 退出）\n")
    while True:
        try:
            text = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return
        if not text:
            continue
        if text in ("/quit", "/exit"):
            print("再见。")
            return
        if text == "/reset":
            service.reset()
            print("（历史已清空）")
            continue

        try:
            if stream:
                print("助手> ", end="", flush=True)
                async for chunk in service.stream(text):
                    print(chunk, end="", flush=True)
                print("\n")
            else:
                answer = await service.ask(text)
                print(f"助手> {answer}\n")
        except LLMError as e:
            print(f"[错误] {e}\n")


async def run_once(service: AssistantService, question: str, stream: bool) -> int:
    try:
        if stream:
            async for chunk in service.stream(question):
                print(chunk, end="", flush=True)
            print()
        else:
            print(await service.ask(question))
        return 0
    except LLMError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1


async def _run(args: argparse.Namespace, service: AssistantService) -> int:
    """整个程序只在一个事件循环里跑。

    这点很关键：asyncio.run() 每次都会新建并**关闭**一个事件循环。
    如果业务用一个 run、关闭 client 又用另一个 run，httpx 的连接池
    属于已关闭的那个循环，aclose() 会抛 RuntimeError: Event loop is closed。
    """
    try:
        if args.interactive or not args.question:
            await run_interactive(service, args.stream)
            return 0
        return await run_once(service, args.question, args.stream)
    finally:
        await service.aclose()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        settings = Settings(api_key="fake-key") if args.fake else Settings.from_env()
    except LLMError as e:
        # 配置错误要友好提示，而不是甩一屏 traceback
        print(f"[配置错误] {e}", file=sys.stderr)
        return 2

    setup_logging(args.log_level or settings.log_level, args.json_logs or settings.json_logs)

    service = build_service(settings, fake=args.fake)

    try:
        return asyncio.run(_run(args, service))
    except LLMError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
