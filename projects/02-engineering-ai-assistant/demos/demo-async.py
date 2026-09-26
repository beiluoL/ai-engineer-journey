"""Chapter 01 演示 —— asyncio 串行 vs 并发、异常处理、事件循环陷阱（真实运行）。

对应 milestones/01-async-await.md：

    串行 vs 并发耗时对比     → 等 I/O 时事件循环去干别的
    asyncio.gather           → 一次await多个协程，结果顺序与传入顺序一致
    异常处理                 → gather 默认「一失败就抛出」，return_exceptions=True 才全量返回
    事件循环复用陷阱          → 在事件循环内部再调 asyncio.run() 会直接 RuntimeError

运行：

    python3 demos/demo-async.py
"""

from __future__ import annotations

import asyncio
import time

# 假装一次 LLM 请求要 0.3 秒（真实场景是等网络 + 等模型）
LATENCY = 0.3
QUESTIONS = ("A", "B", "C")


async def fake_call(tag: str) -> str:
    """模拟一次 I/O：等待期间当前协程会让出执行权。"""
    await asyncio.sleep(LATENCY)
    return f"{tag}-done"


async def serial() -> float:
    """串行：一个等待完，才轮到下一个。"""
    t0 = time.perf_counter()
    for q in QUESTIONS:
        await fake_call(q)
    return time.perf_counter() - t0


async def concurrent() -> float:
    """并发：gather 把三个协程交给同一个事件循环。"""
    t0 = time.perf_counter()
    await asyncio.gather(*(fake_call(q) for q in QUESTIONS))
    return time.perf_counter() - t0


async def flaky() -> str:
    """一个会失败的任务，用来演示异常传播。"""
    await asyncio.sleep(0.1)
    raise ValueError("模型返回 500")


async def nested_run(tag: str) -> None:
    """陷阱：在事件循环「内部」又开了一个 asyncio.run()。"""
    coro = fake_call(tag)
    try:
        asyncio.run(coro)   # ← 这里必然炸
    except RuntimeError as e:
        coro.close()        # 协程没被 await 过，手动关掉免得刷 RuntimeWarning
        raise


async def main() -> None:
    # ---- 1. 串行 vs 并发 ----
    print("=" * 62)
    print(f"1. 串行 vs 并发（每次假 I/O {LATENCY}s，共 {len(QUESTIONS)} 个请求）")
    print("=" * 62)
    t_serial = await serial()
    print(f"  串行 for + await : {t_serial:.3f}s")
    t_concurrent = await concurrent()
    print(f"  并发 asyncio.gather: {t_concurrent:.3f}s")
    print(f"  提速: {t_serial / t_concurrent:.2f}x   —— 单个请求并没变快，省掉的是等待")

    # ---- 2. 异常处理 ----
    print()
    print("=" * 62)
    print("2. 异常处理：gather 默认一失败就整体抛出")
    print("=" * 62)
    try:
        await asyncio.gather(fake_call("A"), flaky(), fake_call("C"))
    except ValueError as e:
        print(f"  try 里捕获: {type(e).__name__}: {e}")
        print("  → A 和 C 的时间白等了，gather 直接把异常抛给调用方")

    results = await asyncio.gather(
        fake_call("A"), flaky(), fake_call("C"), return_exceptions=True
    )
    print(f"  return_exceptions=True → {results}")
    print("  → 结果顺序 = 传入顺序；失败项变成异常对象而不是中断整个 gather")

    # ---- 3. 事件循环复用陷阱 ----
    print()
    print("=" * 62)
    print("3. 陷阱：事件循环内部再调 asyncio.run()")
    print("=" * 62)
    try:
        await nested_run("X")
    except RuntimeError as e:
        print(f"  RuntimeError: {e}")
    print("  src/assistant/cli.py 的 main() 就是「整个程序只 asyncio.run() 一次」的原因")


if __name__ == "__main__":
    asyncio.run(main())
