#!/usr/bin/env python3
"""离线哨兵 —— 判卷时套在每个 answers.py 外面跑，让「参考答案不许联网」变成硬约束。

符号黑名单为什么不够：
    静态扫到 `DeepSeekClient(` 就说它联网，是**假阳性**——
    构造一个客户端对象不发任何请求，拿它的 headers 去验证脱敏是正当操作。
    反过来，静态扫描也拦不住「偷偷 requests.get 一个内网地址」。

真的能拦住的做法是**在 socket 层熔断**：
    把 `socket.socket.connect` / `socket.socket.connect_ex` / `socket.create_connection`
    换成只允许本机回环地址的版本，其余一律抛 `NetworkAccessDenied`。
    进程没能连出去 = 这份答案确实离线。

用法（grade.py 内部调用，不用手动）：

    python -m runpy 路径见 grade.py —— 先 import 本模块 install()，再 runpy.run_path 目标脚本
"""

from __future__ import annotations

import os
import runpy
import socket
import sys


class NetworkAccessDenied(RuntimeError):
    """离线判卷期间尝试建立真实网络连接。"""


LOOPBACK = ("127.0.0.1", "::1", "localhost", "")

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_create_connection = socket.create_connection


def _check(address) -> None:
    """address 形态可能是 (host, port) 元组，也可能是别的，统一取第 0 项判断。"""
    host = ""
    if isinstance(address, (tuple, list)) and address:
        host = str(address[0])
    elif isinstance(address, str):
        host = address
    if host in LOOPBACK:
        return
    raise NetworkAccessDenied(
        f"离线判卷：不允许连接 {host!r}。"
        "参考答案必须既不调真实 LLM，也不读真实 Key —— 这条限制由 exercises/_offline_guard.py 在 socket 层强制。"
    )


def _guarded_connect(self, address):
    _check(address)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    _check(address)
    return _real_connect_ex(self, address)


def _guarded_create_connection(address, *args, **kwargs):
    _check(address)
    return _real_create_connection(address, *args, **kwargs)


def install() -> None:
    """把 socket 层的连接方法换成带阈值的版本。"""
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.create_connection = _guarded_create_connection


def run_guarded(script: str) -> None:
    """装上哨兵后以 __main__ 身份跑目标脚本；脚本自身的 SystemExit 原样往外传。"""
    install()
    target = os.path.abspath(script)
    # 让脚本 import 仓库里的 assistant 包（P02 是 editable 安装，一般已生效，这里是双保险）
    src = str(os.path.join(os.getcwd(), "src"))
    if src not in sys.path and os.path.isdir(src):
        sys.path.insert(0, src)
    try:
        runpy.run_path(target, run_name="__main__")
    except SystemExit as exc:
        # 脚本正常 return 0 时不带 code；非 0 要透出去给判卷脚本
        if exc.code not in (None, 0):
            raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python -m _offline_guard <answers.py>", file=sys.stderr)
        sys.exit(2)
    run_guarded(sys.argv[1])
