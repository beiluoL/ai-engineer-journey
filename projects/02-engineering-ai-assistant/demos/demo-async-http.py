"""Milestone 02 实验：异步 HTTP 客户端（httpx.AsyncClient）。

不依赖外网：本机起一个 http.server，用 httpx 真发请求，对比串行与并发。
看三件事：
1. 串行 await 与 asyncio.gather 的耗时差（省掉的是等待，不是单次请求）；
2. Client 必须复用（连接池），不能每个请求 new 一个；
3. 超时 / 连接失败是两类不同的异常，要分开处理。
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

HOST = "127.0.0.1"
PORT = 8771
BASE = f"http://{HOST}:{PORT}"


class SlowHandler(BaseHTTPRequestHandler):
    """每个请求固定睡 0.3 秒，模拟真实的网络往返。"""

    def do_GET(self) -> None:  # noqa: N802
        time.sleep(0.3)
        name = self.path.lstrip("/") or "anon"
        body = json.dumps({"hello": name}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


async def serial(client: httpx.AsyncClient) -> float:
    t0 = time.perf_counter()
    for name in ("a", "b", "c"):
        resp = await client.get(f"{BASE}/{name}")
        resp.raise_for_status()
    return time.perf_counter() - t0


async def concurrent(client: httpx.AsyncClient) -> float:
    t0 = time.perf_counter()
    resps = await asyncio.gather(*[client.get(f"{BASE}/{n}") for n in ("a", "b", "c")])
    for r in resps:
        r.raise_for_status()
    return time.perf_counter() - t0


async def main() -> None:
    # 注意：必须用 ThreadingHTTPServer。单线程的 HTTPServer 一次只处理一个请求，
    # 会把并发压回串行，测出来的「提速」会是 1.0x —— 这个坑我踩过一次。
    server = ThreadingHTTPServer((HOST, PORT), SlowHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"本机测试服务已启动：{BASE}（每个请求睡 0.3s，多线程）")

    print("\n===== 1. 串行 vs 并发（同一个 AsyncClient，3 个请求）=====")
    # 关键：client 只建一次，连接池复用；每个请求新建 client 会丢掉 keep-alive。
    async with httpx.AsyncClient(timeout=10.0) as client:
        t_serial = await serial(client)
        t_concurrent = await concurrent(client)
    print(f"  串行 for + await     : {t_serial:.3f}s")
    print(f"  并发 asyncio.gather  : {t_concurrent:.3f}s")
    print(f"  提速                 : {t_serial / t_concurrent:.2f}x")
    print("  → 单个请求没有变快，省掉的是「等第一个回来才发第二个」的等待")

    print("\n===== 2. AsyncClient 的生命周期：async with 负责关连接池 =====")
    client = httpx.AsyncClient(timeout=10.0)
    print("  刚创建，还没退出 async with：is_closed =", client.is_closed)
    async with client:
        await client.get(f"{BASE}/a")
        print("  在 async with 里发完请求 ：is_closed =", client.is_closed)
    print("  退出 async with 之后      ：is_closed =", client.is_closed)
    print("  → 不关 = 连接池和 TCP 连接泄漏；每个请求 new 一个 = 反复握手的额外开销")

    print("\n===== 3. 两类错误要分开接 =====")
    # trust_env=False：不读环境里的 http_proxy。否则连 127.0.0.1:9 会被代理接走，
    # 拿回来的是代理的 502（一个正常响应，根本不抛异常），演示就假了。
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        # (a) 超时：服务起来了，但太慢
        try:
            await client.get(f"{BASE}/slow", timeout=0.01)
        except httpx.TimeoutException as exc:
            print(f"  (a) 超时   → httpx.TimeoutException: {type(exc).__name__}")
        # (b) 连接被拒：服务根本没起来（绕过本机代理，否则拿到的是代理的 502）
        try:
            await client.get("http://127.0.0.1:9/", timeout=2)
        except httpx.ConnectError as exc:
            print(f"  (b) 连不上 → httpx.ConnectError: {exc}")
    print("  → 超时要重试，连不上要告警；混成一句 except Exception 就没法分别处理")

    server.shutdown()
    print("\n服务已关闭")


if __name__ == "__main__":
    asyncio.run(main())
