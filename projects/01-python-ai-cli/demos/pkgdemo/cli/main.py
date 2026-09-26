"""pkgdemo 的 CLI 入口。

这个文件同时支持两种运行方式：
    python3 pkgdemo/cli/main.py         # 直接当脚本跑
    python3 -m pkgdemo.cli.main         # 当模块跑
两种方式的效果完全一样，都靠下面这行判断。
"""

from pkgdemo.llm import chat, count_messages
from pkgdemo.utils import now, show


def run():
    print("[cli.main] 开始跑 CLI 了")
    print("[cli.main] 当前时间：", now())

    messages = [
        {"role": "system", "content": "你是一个 Python 老师"},
        {"role": "user", "content": "什么是列表推导式？"},
    ]
    print("[cli.main] 提问记录：")
    show(messages)

    reply = chat(messages)
    messages.append(reply)

    print("[cli.main] 模型回复：", reply["content"])
    print("[cli.main] 现在 messages 里有：", count_messages(messages))
    print("[cli.main] 结束，用时：", now())


if __name__ == "__main__":
    # 只有「真的在跑这个脚本」的时候才执行 run()
    # 被 import 的时候 __name__ 是模块名，不会执行
    print(f"[cli.main] __name__ = {__name__!r}，所以这一段会被执行")
    run()
