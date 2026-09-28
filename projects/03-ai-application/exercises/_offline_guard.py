#!/usr/bin/env python3
"""Project 03 练习的离线哨兵。

判卷时先在 socket 层拦截连接，再用 runpy 运行 answers.py。这样既允许构造
DeepSeekClient 检查 payload 或 headers，又能阻止参考答案真正访问外网、内网或真实 LLM。
"""

from __future__ import annotations

import ipaddress
import os
import runpy
import socket
import sys


class NetworkAccessDenied(RuntimeError):
    """离线判卷期间尝试建立非回环网络连接。"""


_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_REAL_CREATE_CONNECTION = socket.create_connection


def _host_from(address: object) -> str:
    if isinstance(address, (tuple, list)) and address:
        return str(address[0])
    if isinstance(address, str):
        return address
    return ""


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check(address: object) -> None:
    host = _host_from(address)
    if _is_loopback(host):
        return
    raise NetworkAccessDenied(
        f"Project 03 离线判卷不允许连接 {host!r}；"
        "参考答案不得调用真实 LLM、访问外部网络或依赖真实 API Key。"
    )


def _guarded_connect(self, address):
    _check(address)
    return _REAL_CONNECT(self, address)


def _guarded_connect_ex(self, address):
    _check(address)
    return _REAL_CONNECT_EX(self, address)


def _guarded_create_connection(address, *args, **kwargs):
    _check(address)
    return _REAL_CREATE_CONNECTION(address, *args, **kwargs)


def install() -> None:
    """把三处 socket 连接入口替换为只允许回环地址的版本。"""
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.create_connection = _guarded_create_connection


def run_guarded(script: str) -> None:
    """安装哨兵并以 __main__ 运行脚本；非 0 的 SystemExit 原样上抛。"""
    install()
    target = os.path.abspath(script)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(project_root, "src")
    if os.path.isdir(src) and src not in sys.path:
        sys.path.insert(0, src)
    try:
        runpy.run_path(target, run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python exercises/_offline_guard.py <answers.py>", file=sys.stderr)
        raise SystemExit(2)
    run_guarded(sys.argv[1])
