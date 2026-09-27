"""Milestone 09 实验：用标准库起一个本地 HTTP 服务，真实发出 GET / POST。

不依赖外网：服务端和客户端都在本机回环地址上，全部请求真实发生。
看三件事：
1. GET 成功（200）与资源不存在（404）的响应差异；
2. 响应头、状态码、响应体分别从哪里读；
3. POST 发 JSON、服务端 JSON 应答 —— 这就是调用大模型 API 的同一套动作。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8765
BASE = f"http://{HOST}:{PORT}"

CATALOG = {
    "python": {"name": "Python", "year": 1991, "author": "Guido van Rossum"},
    "java": {"name": "Java", "year": 1995, "author": "James Gosling"},
}


class Handler(BaseHTTPRequestHandler):
    """一个最小的 JSON API：GET 查目录，POST 回显。"""

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        key = self.path.lstrip("/")
        if key in CATALOG:
            self._send(200, {"ok": True, "data": CATALOG[key]})
        else:
            self._send(404, {"ok": False, "error": f"没有这门语言: {key}"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._send(400, {"ok": False, "error": f"JSON 解析失败: {exc}"})
            return
        self._send(200, {"ok": True, "echo": payload,
                         "received_bytes": len(raw)})

    def log_message(self, *args) -> None:
        pass  # 安静一点，输出里只留客户端视角


def request(method: str, path: str = "", body: dict | None = None) -> None:
    """发一次真实请求，把状态码 / 响应头 / 响应体都打印出来。"""
    url = f"{BASE}/{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    print(f"\n--- {method} {url} ---")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print("状态码        :", resp.status)
            print("Content-Type  :", resp.headers.get("Content-Type"))
            text = resp.read().decode("utf-8")
            print("响应体        :", text)
            print("解析成 dict   :", json.loads(text))
    except urllib.error.HTTPError as exc:
        print("状态码        :", exc.code, "（HTTPError 不是崩溃，是服务端的正常应答）")
        print("响应体        :", exc.read().decode("utf-8"))


def main() -> None:
    server = HTTPServer((HOST, PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"本地服务已启动：{BASE}（标准库 http.server，进程内线程）")

    print("\n===== 1. GET 命中：200 =====")
    request("GET", "python")

    print("\n===== 2. GET 没命中：404（用 HTTPError 接住，不是崩溃）=====")
    request("GET", "rust")

    print("\n===== 3. POST 发 JSON，服务端回 JSON =====")
    request("POST", "", {"model": "deepseek-chat",
                         "messages": [{"role": "user", "content": "你好"}]})

    print("\n===== 4. POST 一段坏 JSON：400 =====")
    req = urllib.request.Request(f"{BASE}/", data=b"{not json",
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print("状态码:", resp.status)
    except urllib.error.HTTPError as exc:
        print("状态码        :", exc.code)
        print("响应体        :", exc.read().decode("utf-8"))

    print("\n===== 5. 连一个没人监听的端口：连接被拒绝 =====")
    # 必须显式绕过环境里的 http_proxy，否则请求会被代理接走，
    # 拿回来的是代理的 502 Bad Gateway，而不是真正的「连接被拒绝」。
    no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        no_proxy_opener.open("http://127.0.0.1:9/", timeout=2)
    except urllib.error.URLError as exc:
        print("URLError      :", exc.reason)
        print("→ 这是「服务没起来」，和 404「服务起来了但没这个资源」是两类错误")

    server.shutdown()
    print("\n服务已关闭")


if __name__ == "__main__":
    main()
