#!/usr/bin/env python3
"""托管 fixture 站点的本地 HTTP 服务 —— python-practice/03-web-crawler

任务卡：python-practice/03-web-crawler/README.md

它就是在标准库 `http.server` 上加了一层「**故障注入**」：
对 `/page-2.html` 的第 1 次请求返回 503。这样爬虫里的重试逻辑
不是摆设 —— 你能在日志里真的看到 `503 → 等 0.5s → 重试 → 200`。

手动起服务（方便你自己用浏览器或 curl 摸）：
    python3 serve.py                 # 默认 127.0.0.1:8123
    python3 serve.py --port 9000

被 demo.py 调用（端口交给系统分配，避免撞端口）：
    server, port = create_server()   # 然后 server.shutdown()
"""
from __future__ import annotations

import argparse
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_ROOT = ROOT / ".site"

# 故意对哪个路径限流、失败几次
FLAKY_PATH = "/page-2.html"
FLAKY_FAIL_TIMES = 1


class FixtureHandler(SimpleHTTPRequestHandler):
    """带故障注入的静态文件服务器。"""

    hits: dict[str, int] = {}  # 类变量：记录每个路径被请求了几次

    def do_GET(self) -> None:  # noqa: N802 - 标准库要求的驼峰命名
        seen = FixtureHandler.hits.get(self.path, 0)
        FixtureHandler.hits[self.path] = seen + 1

        if self.path == FLAKY_PATH and seen < FLAKY_FAIL_TIMES:
            body = "503 模拟限流：请稍后重试".encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Retry-After", "1")
            self.end_headers()
            self.wfile.write(body)
            return

        super().do_GET()

    def log_message(self, fmt: str, *args: object) -> None:
        """静音：默认实现会把每个请求打到 stderr，演示输出会很乱。"""
        return


def create_server(
    root: Path = DEFAULT_ROOT, port: int = 0
) -> tuple[ThreadingHTTPServer, int]:
    """起一个服务并返回 (server, 实际端口)。port=0 表示让系统随便挑一个空闲端口。"""
    if not (Path(root) / "index.html").exists():
        raise SystemExit(f"{root} 下没有 index.html，请先跑 `python3 make_fixture_site.py`")

    FixtureHandler.hits.clear()  # 每次新建服务都重置计数，保证可复现
    handler = partial(FixtureHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    return server, server.server_address[1]


def serve_in_background(
    root: Path = DEFAULT_ROOT, port: int = 0
) -> tuple[ThreadingHTTPServer, int, threading.Thread]:
    """把服务跑在后台线程里 —— demo.py 用这个，跑完 shutdown 即可。"""
    server, real_port = create_server(root, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, real_port, thread


def main() -> int:
    parser = argparse.ArgumentParser(description="托管 fixture 站点")
    parser.add_argument("--port", type=int, default=8123, help="监听端口（默认 8123）")
    args = parser.parse_args()

    server, port = create_server(port=args.port)
    print(f"fixture 站点已就绪：http://127.0.0.1:{port}/")
    print("注意 /page-2.html 的第一次访问会返回 503（模拟限流），这是故意的。")
    print("Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
